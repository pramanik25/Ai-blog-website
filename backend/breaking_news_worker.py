# /backend/breaking_news_worker.py
import os
import requests
import time
import json
from slugify import slugify
from groq import Groq
from app import app, db, Article, Category
import feedparser
# --- 1. IMPORT THE KEYWORD PROMPT ---
from prompts import get_keyword_prompt

## --- CONFIGURATION ---
ARTICLES_TO_GENERATE = 2
groq_client = Groq(api_key=os.getenv("GROQ_APISEC_KEY"))


## --- STEP 1: NEWS DISCOVERY (USING RSS FEEDS) ---
def fetch_headlines_from_rss():
    """Fetches and combines headlines from a list of RSS feeds."""
    RSS_FEEDS = [
        'http://feeds.bbci.co.uk/news/world/rss.xml',
         'http://rss.cnn.com/rss/edition.rss',
        'https://www.aljazeera.com/xml/rss/all.xml',
        'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
        'https://www.reuters.com/tools/rss',
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
    
    if not all_headlines:
        print("No headlines found from any RSS feed.")
        return []

    unique_headlines = list(set(all_headlines))
    print(f"Found {len(unique_headlines)} unique headlines.")
    return unique_headlines


# --- 3. UPDATED PROMPT TO ACCEPT AND USE KEYWORDS ---
def get_news_generation_prompt(headline, keywords=None):
    """Creates a specialized prompt for generating a news article."""
    category_list = "['Technology', 'Health', 'Science', 'Business', 'Culture', 'World News', 'Travel', 'Food', 'Finance', 'Education', 'Lifestyle', 'Entertainment']"

    keyword_instruction = ""
    if keywords:
        keyword_list_str = ", ".join(f'"{k}"' for k in keywords)
        keyword_instruction = f"""
**SEO Keyword Integration:**
You MUST naturally weave the following keywords into the article, especially in the H2 and H3 headings: {keyword_list_str}.
"""

    return f"""
    You are a professional journalist for a major international news outlet. Your writing is objective, factual, and follows the "inverted pyramid" structure.

    **Headline:** "{headline}"
    {keyword_instruction}
    **Your Task:**
    Write a comprehensive, well-structured news article of at least 2000 words based on this headline.
    
        **JSON Output Structure:**
    You MUST generate a single, valid JSON object with these exact keys:
    -   "title": The original headline.
    -   "meta_description": A concise, SEO-friendly summary of the article (under 155 characters).
    -   "category": The single most relevant news category from this list: {category_list}.
    -   "authorName": A plausible journalist's name.
    -   "authorBio": A one-sentence bio for the journalist (e.g., "A staff writer covering technology and finance.").
    -   "content": The full news article in Markdown format.
    (The rest of the requirements for structure, tone, etc., remain the same)
    """

# --- 4. REFACTORED GENERATION FUNCTION FOR TWO-STEP PROCESS ---
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

        # STEP 2.2: Generate Article using Keywords
        print(" -> Step 2: Generating full article with keywords...")
        prompt = get_news_generation_prompt(headline, seo_keywords)
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", # Use powerful model for the article
            temperature=0.6,
            response_format={"type": "json_object"},
        )
        response_content = chat_completion.choices[0].message.content
        data = json.loads(response_content)

        # ... (Database saving logic remains the same)
        slug = slugify(data['title'])
        existing_article = Article.query.filter_by(slug=slug, lang='en').first()
        if existing_article:
            print(f"  -> Article with slug '{slug}' already exists. Skipping.")
            return None

        new_article = Article(
            slug=slug,
            title=data['title'],
            meta_description=data['meta_description'],
            content=data['content'],
            author_name=data.get('authorName'),
            author_bio=data.get('authorBio'),
            is_published=True,
            is_breaking_news=True
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
        print(f" -> A critical error occurred during Groq V2 generation or DB save: {e}")
        return None

## --- STEP 3: MAIN JOB ORCHESTRATION ---
# (This function remains the same, no changes needed)
def run_breaking_news_job():
     print("--- Starting Breaking News Job (RSS + Groq V2) ---")
     with app.app_context():
        headlines = fetch_headlines_from_rss() # <-- USE THE NEW RSS FUNCTION
        if not headlines:
            print("No headlines found. Exiting job.")
            return

        generated_count = 0
        # We only want to process the top headlines
        for headline in headlines[:10]: # Process the first 10 found headlines
            if generated_count >= ARTICLES_TO_GENERATE:
                break
            
            # Check if a similar article already exists to avoid duplicates
            exists = db.session.query(Article.id).filter(Article.title.like(f"%{headline[:50]}%")).first()
            if exists:
                print(f"Skipping headline as a similar article already exists: '{headline}'")
                continue

            new_article = generate_article_with_groq_v2(headline)

            if new_article:
                generated_count += 1
                time.sleep(20)

        print(f"--- Breaking News Job Finished. Generated {generated_count} articles. ---")


    
if __name__ == '__main__':
   
    run_breaking_news_job()