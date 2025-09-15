import os
import requests
import time
import json
import re
from slugify import slugify
from groq import Groq
from app import app, db, Article, Category
from prompts import get_future_viral_topics_prompt, get_keyword_prompt, get_combined_prompt
import random
import firebase_admin
from firebase_admin import credentials, storage

# --- CONFIGURATION ---
ARTICLES_TO_GENERATE = 10 # Should match the number in the prompt
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- IMAGE GENERATION CONFIG ---
FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
FIREWORKS_API_URL = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-schnell-fp8/text_to_image"

# --- ENSURE FIREBASE IS INITIALIZED ---
if not firebase_admin._apps:
    try:
        BASE_DIR = os.path.dirname(os.path.abspath(__file__))
        CRED_PATH = os.path.join(BASE_DIR, "firebase-credentials.json")
        cred = credentials.Certificate(CRED_PATH)
        firebase_admin.initialize_app(cred, {'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET")})
        print("Firebase Admin SDK initialized by worker.")
    except Exception as e:
        print(f"!!! CRITICAL: Worker failed to initialize Firebase: {e} !!!")

## --- STEP 1: AI-POWERED TREND FORECASTING ---
def get_ai_predicted_topics():
    """Asks the Groq AI to predict future trending topics with a JSON/text fallback."""
    print("Asking AI to predict future trending topics...")
    prompt = get_future_viral_topics_prompt()
    response_content = None
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        response_content = chat_completion.choices[0].message.content
    except Exception as e:
        print(f" -> JSON mode failed: {e}. Retrying in text mode.")
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant",
            temperature=0.8,
        )
        response_content = chat_completion.choices[0].message.content
    
    try:
        json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
        if json_match:
            response_data = json.loads(json_match.group(0))
            topics = response_data.get("future_topics", [])
            print(f"  -> AI predicted topics: {topics}")
            return topics
        return []
    except Exception as e:
        print(f"  -> AI topic prediction failed during parsing: {e}")
        return []

## --- IMAGE GENERATION & UPLOAD FUNCTIONS ---
def generate_image(prompt):
    """Calls the Fireworks.ai API to create an image."""
    print(f"  -> Sending image generation request for: '{prompt}'")
    try:
        headers = {
            "Accept": "image/jpeg", "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKS_API_KEY}"
        }
        payload = {"prompt": f"{prompt}, cinematic, masterpiece, 8k", "height": 512, "width": 1024}
        response = requests.post(FIREWORKS_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        if response.content: return response.content
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
        return blob.public_url
    except Exception as e:
        print(f"  -> Error uploading image to Firebase: {e}")
        return None

def get_random_fallback_image():
    """Fetches a random image from Firebase Storage as a fallback."""
    try:
        bucket = storage.bucket()
        blobs = bucket.list_blobs(prefix='images/')
        image_urls = [blob.public_url for blob in blobs if blob.name != 'images/']
        if not image_urls: return None
        return random.choice(image_urls)
    except Exception as e:
        print(f"--- Fallback failed with an error: {e} ---")
        return None

## --- STEP 2: FULL ARTICLE GENERATION PIPELINE ---
def generate_future_article_pipeline(topic):
    """A self-contained pipeline to generate an article with keywords and images."""
    print(f"\nProcessing predicted topic: '{topic}'")
    try:
        # Step A: Generate Keywords
        print(" -> Step A: Generating SEO keywords...")
        keyword_prompt = get_keyword_prompt(topic)
        keyword_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": keyword_prompt}],
            model="llama-3.1-8b-instant", temperature=0.5, response_format={"type": "json_object"}
        )
        seo_keywords = json.loads(keyword_completion.choices[0].message.content).get("keywords", [])
        print(f" -> Found Keywords: {seo_keywords}")

        future_context_query = f"""
        Write a forward-looking article about the upcoming event or topic: "{topic}".

        Your article must be written from a predictive and anticipatory perspective. Focus on what to expect, preparations for the event, its future relevance, and predictions.

        CRITICAL INSTRUCTION: Avoid using information or examples from past years (e.g., 2023, 2024). All content should be framed as if it is happening in the near future (2025 and beyond).
        """

        # Step B: Generate Article Text
        print(" -> Step B: Generating full article text...")
        combined_prompt = get_combined_prompt(future_context_query, seo_keywords)
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": combined_prompt}],
            model="llama-3.3-70b-versatile", temperature=0.7, response_format={"type": "json_object"}
        )
        data = json.loads(chat_completion.choices[0].message.content)

        # Step C: Process Images
        content_with_images, main_image_url = data['content'], None
        image_placeholders = re.findall(r'\[IMAGE: (.*?)\]', content_with_images)
        print(f" -> Step C: Found {len(image_placeholders)} image placeholders.")

        for i, img_prompt in enumerate(image_placeholders):
            image_url, image_bytes = None, generate_image(img_prompt)
            if image_bytes:
                filename = f"{slugify(data['title'])}-{time.time_ns()}-{i}.jpg"
                image_url = upload_image_to_firebase(image_bytes, filename)
            if not image_url:
                image_url = get_random_fallback_image()
            if image_url:
                if main_image_url is None: main_image_url = image_url
                content_with_images = content_with_images.replace(f"[IMAGE: {img_prompt}]", f"![{img_prompt}]({image_url})", 1)
                print(f"   -> Replaced placeholder {i+1} with URL.")
            else:
                print(f"   -> CRITICAL: Image processing failed for '{img_prompt}'.")
            time.sleep(5)
            
        # Step D: Save to Database
        print(" -> Step D: Saving final article to database...")
        slug = slugify(data['title'])
        if Article.query.filter_by(slug=slug, lang='en').first():
            print(f"  -> Article with slug '{slug}' already exists. Skipping.")
            return

        new_article = Article(
            slug=slug, title=data['title'], meta_description=data['meta_description'], content=content_with_images,
            image_url=main_image_url, author_name=data.get('authorName'), author_bio=data.get('authorBio'),lang='hi',
            is_published=True, is_breaking_news=False # This is evergreen, not breaking news
        )
        category_name = data.get('category')
        if category_name:
            category = Category.query.filter_by(name=category_name).first() or Category(name=category_name, slug=slugify(category_name))
            new_article.categories.append(category)
        
        db.session.add(new_article)
        db.session.commit()
        print(f" -> Successfully saved article: '{new_article.title}'")

    except Exception as e:
        print(f" -> A critical error occurred during the pipeline for '{topic}': {e}")

## --- MAIN JOB ORCHESTRATION ---
def run_future_content_job():
    print("--- Starting Future-Proof Content Generation Job ---")
    with app.app_context():
        topics = get_ai_predicted_topics()
        if not topics:
            print("No future topics were predicted. Exiting job.")
            return

        for topic in topics:
            generate_future_article_pipeline(topic)
            time.sleep(20)
    print("\n--- Future-Proof Content Generation Job Finished ---")

if __name__ == '__main__':
    run_future_content_job()
