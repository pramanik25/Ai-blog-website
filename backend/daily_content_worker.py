# /backend/daily_content_worker.py
import os
import requests
import time # We need this for the rate-limiting delay
from pytrends.request import TrendReq
from slugify import slugify
# --- The 'google.cloud' import is no longer needed ---

# --- CONFIGURATION ---
TARGET_LANGUAGES = ['es', 'hi', 'fr', 'de', 'pt'] # Spanish, Hindi, French, German, Portuguese
NUMBER_OF_ARTICLES = 10
GENERATION_API_URL = os.getenv("GENERATION_API_URL") # Get URL from environment

# --- NEW: LibreTranslate API Details ---
LIBRETRANSLATE_API_URL = "https://libretranslate.de/translate" # A popular public instance

# --- SETUP ---
# No special setup or credential files needed for LibreTranslate

# --- FUNCTIONS ---

def get_trending_keywords():
    """Fetches the top trending keywords worldwide."""
    print("Fetching trending keywords from Google Trends...")
    pytrends = TrendReq(hl='en-US', tz=360)
    trending_df = pytrends.trending_searches(pn='p1') # p1 = worldwide
    keywords = trending_df[0].tolist()[:NUMBER_OF_ARTICLES]
    print(f"Found keywords: {keywords}")
    return keywords

def generate_article_in_english(keyword):
    """Calls our own API to generate the base English article."""
    print(f"Generating English article for keyword: '{keyword}'...")
    try:
        response = requests.post(GENERATION_API_URL, json={'query': keyword}, timeout=300) # Long timeout
        response.raise_for_status() # Raise an error for bad status codes
        print("English article generated successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error generating English article: {e}")
        return None

def translate_text(text, target_language, source_language='en'):
    """Translates a piece of text using a public LibreTranslate API."""
    if not text:
        return text
    
    payload = {
        'q': text,
        'source': source_language,
        'target': target_language,
        'format': 'text'
    }
    
    try:
        response = requests.post(LIBRETRANSLATE_API_URL, json=payload)
        response.raise_for_status()
        translated_text = response.json().get('translatedText', text)
        return translated_text
    except requests.exceptions.RequestException as e:
        print(f"  - Translation API error: {e}. Returning original text.")
        return text # Return original text on failure

def run_daily_job():
    """The main function to orchestrate the entire process."""
    print("--- Starting Daily Content Generation Job ---")
    
    keywords = get_trending_keywords()
    
    for keyword in keywords:
        english_article = generate_article_in_english(keyword)
        
        if not english_article:
            print(f"Skipping translations for failed article: '{keyword}'")
            continue

        print(f"--- Translating article '{english_article['title']}' ---")
        for lang_code in TARGET_LANGUAGES:
            try:
                print(f"Translating to '{lang_code}'...")
                
                # To be polite to the public API, we add a small delay
                time.sleep(10) # Wait 2 seconds between each language
                
                translated_title = translate_text(english_article['title'], lang_code)
                time.sleep(10)
                translated_desc = translate_text(english_article['meta_description'], lang_code)
                time.sleep(10)
                # Translating large content blocks can be slow
                translated_content = translate_text(english_article['content'], lang_code)
                
                translated_slug = slugify(translated_title)

                # This is where you would save the translated article to your database.
                # This part of the logic remains the same.
                print(f"  - Title: {translated_title}")
                print(f"  - Slug: {translated_slug}")
                print(f"  - Successfully prepared translation for '{lang_code}'.")
                
                # --- DATABASE SAVING LOGIC WOULD GO HERE ---
                # from app import app, db, Article
                # with app.app_context():
                #   original_article = Article.query.get(english_article['id'])
                #   new_translation = Article(...)
                #   db.session.add(new_translation)
                #   db.session.commit()
                # -------------------------------------------

            except Exception as e:
                print(f"An unexpected error occurred while translating to '{lang_code}': {e}")

    print("--- Daily Content Generation Job Finished ---")


if __name__ == '__main__':
    run_daily_job()