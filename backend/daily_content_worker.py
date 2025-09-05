# /backend/daily_content_worker.py
import os
import requests
import time
from pytrends.request import TrendReq
from slugify import slugify
import random

# --- CONFIGURATION ---

# Define our target regions and the primary language for each.
# Pytrends country codes: 'IN' (India), 'US' (United States), 'FR' (France), 'DE' (Germany), 'BR' (Brazil for Portuguese)
TARGET_REGIONS = {
    'india':      {'code': 'IN', 'lang': 'hi'}, # Hindi
    'united_states': {'code': 'US', 'lang': 'en'}, # English
    'france':     {'code': 'FR', 'lang': 'fr'}, # French
    'germany':    {'code': 'DE', 'lang': 'de'}, # German
    'brazil':     {'code': 'BR', 'lang': 'pt'}, # Portuguese
}

# The list of all languages we want articles to be available in.
ALL_TARGET_LANGUAGES = ['en', 'hi', 'fr', 'de', 'pt', 'es'] # Added Spanish as a translation target

# How many top trending articles to generate per country
ARTICLES_PER_REGION = 2 # Let's do 2 from each country for a total of 10 articles

GENERATION_API_URL = os.getenv("GENERATION_API_URL")
LIBRETRANSLATE_API_URL = "https://libretranslate.de/translate"

# --- FUNCTIONS ---

def get_trending_keywords(country_name, country_code):
    """Fetches the top trending keywords for a specific country."""
    print(f"Fetching trending keywords from Google Trends for: {country_name.upper()}...")
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        trending_df = pytrends.trending_searches(pn=country_name)
        keywords = trending_df[0].tolist()[:ARTICLES_PER_REGION]
        print(f"  - Found keywords: {keywords}")
        return keywords
    except Exception as e:
        print(f"  - Could not fetch trends for {country_name}. Error: {e}")
        return []

def generate_initial_article(keyword, language_code):
    """Calls our API. Crucially, we now tell it what language to write in."""
    print(f"Generating article for keyword: '{keyword}' in language '{language_code}'...")
    try:
        # We add the language to the query to guide the AI
        query_with_lang = f"{keyword} (write in {language_code})"
        response = requests.post(GENERATION_API_URL, json={'query': query_with_lang}, timeout=300)
        response.raise_for_status()
        print("  - Article generated successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  - Error generating article: {e}")
        return None

def translate_text(text, target_language, source_language):
    """Translates text using LibreTranslate."""
    if not text or source_language == target_language:
        return text
    
    # Add a polite delay
    time.sleep(1 + random.random()) # Sleep 1-2 seconds
    
    print(f"    - Translating from '{source_language}' to '{target_language}'...")
    payload = {'q': text, 'source': source_language, 'target': target_language, 'format': 'text'}
    
    try:
        response = requests.post(LIBRETRANSLATE_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get('translatedText', text)
    except requests.exceptions.RequestException as e:
        print(f"    - Translation API error: {e}. Returning original text.")
        return text

def run_daily_job():
    """The main function to orchestrate the multi-region, multi-lingual process."""
    print("--- Starting Daily Multi-Region Content Generation Job ---")
    
    # Iterate through each of our target countries
    for country_name, region_data in TARGET_REGIONS.items():
        country_code = region_data['code']
        primary_lang = region_data['lang']

        # 1. Get trending keywords for the specific country
        keywords = get_trending_keywords(country_name, country_code)
        
        for keyword in keywords:
            # 2. Generate the base article in the country's primary language
            initial_article = generate_initial_article(keyword, primary_lang)
            
            if not initial_article:
                continue # Skip if generation failed

            print(f"--- Processing translations for article: '{initial_article['title']}' ---")
            
            # This is where you would save the initial article to your database.
            # --- DATABASE SAVING LOGIC FOR INITIAL ARTICLE ---

            # 3. Translate the initial article into all other target languages
            for lang_code in ALL_TARGET_LANGUAGES:
                if lang_code == primary_lang:
                    continue # Don't re-translate to the original language

                try:
                    translated_title = translate_text(initial_article['title'], lang_code, primary_lang)
                    translated_desc = translate_text(initial_article['meta_description'], lang_code, primary_lang)
                    translated_content = translate_text(initial_article['content'], lang_code, primary_lang)
                    translated_slug = slugify(translated_title)

                    print(f"  - Successfully prepared translation for '{lang_code}'.")
                    
                    # --- DATABASE SAVING LOGIC FOR TRANSLATION ---
                    # from app import app, db, Article
                    # with app.app_context():
                    #   original_article_db = Article.query.get(initial_article['id'])
                    #   new_translation = Article(
                    #     slug=translated_slug,
                    #     lang=lang_code,
                    #     title=translated_title,
                    #     ...
                    #     original_article_id=original_article_db.id
                    #   )
                    #   db.session.add(new_translation)
                    #   db.session.commit()
                    # -------------------------------------------

                except Exception as e:
                    print(f"An unexpected error occurred while translating to '{lang_code}': {e}")

    print("--- Daily Content Generation Job Finished ---")


if __name__ == '__main__':
    run_daily_job()
    