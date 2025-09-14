# /backend/breaking_news_worker.py
import os
import requests
import time
import json
import re
from slugify import slugify
from groq import Groq
from app import app, db, Article, Category
import feedparser
from prompts import get_keyword_prompt
import random
from firebase_admin import storage

## --- CONFIGURATION ---
ARTICLES_TO_GENERATE = 2
# --- FIX #1: Corrected the API key variable name ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- IMAGE GENERATION CONFIG ---
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
FIREWORKS_API_URL = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-schnell-fp8/text_to_image"

## --- STEP 1: NEWS DISCOVERY ---
def fetch_headlines_from_rss():
    """Fetches and combines headlines from a list of RSS feeds."""
    RSS_FEEDS = [
        'http://feeds.bbci.co.uk/news/world/rss.xml',
        'https://timesofindia.indiatimes.com/rssfeedstopstories.cms',
        'https://news.google.com/rss?gl=IN&hl=en-IN&ceid=IN:en'
    ]
    all_headlines = []
    print("Fetching headlines from RSS feeds...")
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                all_headlines.append(entry.title)
        except Exception as e:
            print(f"Could not parse RSS feed {url}. Error: {e}")
    
    unique_headlines = list(set(all_headlines))
    print(f"Found {len(unique_headlines)} unique headlines.")
    return unique_headlines

## --- IMAGE GENERATION & UPLOAD FUNCTIONS ---
def generate_image(prompt):
    """Calls the Fireworks.ai API to create an image."""
    print(f"  -> Sending image generation request for: '{prompt}'")
    try:
        headers = {
            "Accept": "image/jpeg",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKS_API_KEY}"
        }
        payload = {"prompt": f"{prompt}, cinematic, masterpiece, 8k", "height": 512, "width": 1024}
        response = requests.post(FIREWORKS_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        image_bytes = response.content
        if image_bytes:
            print("  -> Image generation successful.")
            return image_bytes
        return None
    except requests.exceptions.RequestException as e:
        print(f"  -> Image generation API call failed: {e}")
        return None

def upload_image_to_firebase(image_bytes, filename):
    """Uploads image bytes to Firebase Storage."""
    try:
        bucket = storage.bucket()
        blob = bucket.blob(f"images/{filename}")
        blob.upload_from_string(image_bytes, content_type='image/jpeg')
        blob.make_public()
        print(f"  -> Image uploaded to Firebase: {blob.public_url}")
        return blob.public_url
    except Exception as e:
        print(f"  -> Error uploading image to Firebase: {e}")
        return None

def get_random_fallback_image():
    """Fetches a random image from Firebase Storage as a fallback."""
    try:
        print("--- Initiating fallback image search ---")
        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix='images/')
        image_urls = [blob.public_url for blob in blobs if blob.name != 'images/']
        if not image_urls:
            return None
        return random.choice(image_urls)
    except Exception as e:
        print(f"--- Fallback failed with an error: {e} ---")
        return None

## --- STEP 2: DEDICATED NEWS GENERATION ---
def get_news_generation_prompt(headline, keywords=None):
    """Creates a specialized prompt for generating a news article."""
    category_list = "['Technology', 'Health', 'Science', 'Business', 'Culture', 'World News', 'Travel', 'Food', 'Finance', 'Education', 'Lifestyle', 'Entertainment']"
    keyword_instruction = ""
    if keywords:
        keyword_list_str = ", ".join(f'"{k}"' for k in keywords)
        keyword_instruction = f"""
**SEO Keyword Integration:**
You MUST naturally weave the following keywords into the article, especially in the H2 and H3 headings: {keyword_list_str}."""

    # --- FIX #2: Restored the full, detailed prompt requirements ---
    return f"""
    You are a professional journalist for a major international news outlet. Your writing is objective, factual, and follows the "inverted pyramid" structure.

    **Headline:** "{headline}"
    {keyword_instruction}
    **Your Task:**
    Write a comprehensive, well-structured news article of at least 2000 words based on this headline.

    **CRITICAL REQUIREMENTS:**
    - **Structure:**
        - Start with a strong lead paragraph (dateline included, e.g., "PATNA, India –") that summarizes the most crucial information.
        - Use subsequent paragraphs for details, context, background information, and quotes.
        - Use Markdown with H3 (`###`) subheadings.
    - **Tone:** Maintain a neutral, professional, journalistic tone.
    - **Image Placeholders:** Include exactly **two** `[IMAGE: A detailed, journalistic prompt for a relevant news photo]` placeholders.

    **JSON Output Structure:**
    You MUST generate a single, valid JSON object with these exact keys:
    -   "title": The original headline.
    -   "meta_description": A concise, SEO-friendly summary (under 155 characters).
    -   "category": The single most relevant news category from this list: {category_list}.
    -   "authorName": A plausible journalist's name.
    -   "authorBio": A one-sentence bio for the journalist.
    -   "content": The full news article in Markdown format.
    """

def generate_article_with_groq_v2(headline):
    """
    Generates and saves a news article using a dedicated, two-step Groq process.
    """
    print(f"Initiating 2-step generation for: '{headline}'")
    try:
        # STEP 2.1: Generate Keywords
        print(" -> Step 1: Generating SEO keywords...")
        keyword_prompt = get_keyword_prompt(headline)
        keyword_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": keyword_prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        keyword_data = json.loads(keyword_completion.choices[0].message.content)
        seo_keywords = keyword_data.get("keywords", [])
        print(f" -> Found Keywords: {seo_keywords}")

        # STEP 2.2: Generate Article
        print(" -> Step 2: Generating full article with keywords...")
        prompt = get_news_generation_prompt(headline, seo_keywords)
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-70b-versatile",
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        data = json.loads(chat_completion.choices[0].message.content)
        
        # STEP 2.3: Process Images
        content_with_images = data['content']
        main_image_url = None
        image_placeholders = re.findall(r'\[IMAGE: (.*?)\]', content_with_images)
        print(f" -> Found {len(image_placeholders)} image placeholders to process.")

        for i, img_prompt in enumerate(image_placeholders):
            image_url = None
            image_bytes = generate_image(img_prompt)
            if image_bytes:
                filename = f"{slugify(data['title'])}-{time.time_ns()}-{i}.jpg"
                image_url = upload_image_to_firebase(image_bytes, filename)
            
            if not image_url:
                print(f" -> Live generation failed for '{img_prompt}'. Attempting fallback.")
                image_url = get_random_fallback_image()
            
            if image_url:
                if main_image_url is None: main_image_url = image_url
                content_with_images = content_with_images.replace(f"[IMAGE: {img_prompt}]", f"![{img_prompt}]({image_url})", 1)
                print(f" -> Replaced placeholder {i+1} with URL.")
            else:
                print(f" -> CRITICAL: Both live generation and fallback failed for '{img_prompt}'.")
            time.sleep(5)
        
        # STEP 2.4: Save to Database
        slug = slugify(data['title'])
        if Article.query.filter_by(slug=slug, lang='en').first():
            print(f"  -> Article with slug '{slug}' already exists. Skipping.")
            return None

        new_article = Article(
            slug=slug, title=data['title'], meta_description=data['meta_description'],
            content=content_with_images, image_url=main_image_url,
            author_name=data.get('authorName'), author_bio=data.get('authorBio'),
            is_published=True, is_breaking_news=True
        )
        
        category_name = data.get('category')
        if category_name:
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name, slug=slugify(category_name))
                db.session.add(category)
            new_article.categories.append(category)
        
        db.session.add(new_article)
        db.session.commit()
        print(f" -> Successfully generated and saved article: '{new_article.title}'")
        return new_article

    except Exception as e:
        print(f" -> A critical error occurred during generation or DB save: {e}")
        return None

## --- MAIN JOB ORCHESTRATION ---
def run_breaking_news_job():
    print("--- Starting Breaking News Job (RSS + Groq V2 + Images) ---")
    with app.app_context():
        headlines = fetch_headlines_from_rss()
        if not headlines:
            print("No headlines found. Exiting job.")
            return

        generated_count = 0
        random.shuffle(headlines)
        for headline in headlines:
            if generated_count >= ARTICLES_TO_GENERATE:
                break
            
            if Article.query.filter(Article.title.like(f"%{headline[:50]}%")).first():
                print(f"Skipping headline as a similar article already exists: '{headline}'")
                continue

            if generate_article_with_groq_v2(headline):
                generated_count += 1
                time.sleep(20)
            else:
                time.sleep(5)
    print(f"--- Breaking News Job Finished. Generated {generated_count} articles. ---")
    
if __name__ == '__main__':
    run_breaking_news_job()