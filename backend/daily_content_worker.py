# /backend/daily_content_worker.py
import os
import requests
import time
import json
from slugify import slugify
import random
from groq import Groq

# --- CONFIGURATION ---

# Define our target regions and the primary language for each.
TARGET_REGIONS = {
    'India':      {'lang': 'hi'}, # Hindi
    'United States': {'lang': 'en'}, # English
    'France':     {'lang': 'fr'}, # French
    'Germany':    {'lang': 'de'}, # German
    'Brazil':     {'lang': 'pt'}, # Portuguese
}

# The list of all languages we want articles to be available in.
ALL_TARGET_LANGUAGES = ['en', 'hi', 'fr', 'de', 'pt', 'es']

# How many top trending articles to generate per country
TOPICS_PER_REGION = 3

# The public URL of your live Render backend's generation endpoint
GENERATION_API_URL = os.getenv("GENERATION_API_URL")
LIBRETRANSLATE_API_URL = "https://libretranslate.de/translate"

# --- SETUP ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- FUNCTIONS ---

def get_ai_generated_topics_for_region(country_name):
    """Asks the Groq AI to act as a local SEO expert for a specific country."""
    print(f"Generating SEO-friendly topics for: {country_name.upper()}...")
    try:
        prompt = f"""
        You are an expert SEO strategist and content planner specializing in the country of {country_name}.
        Generate a list of the top {TOPICS_PER_REGION} interesting and highly searchable blog post topics that are trending in {country_name} right now.
        The topics should be diverse and relevant to the local culture and interests.
        Focus on creating "long-tail" keywords that a user in {country_name} is likely to type into a search engine.

        You MUST respond with ONLY a valid JSON array of {TOPICS_PER_REGION} strings and nothing else.
        Example format: ["Topic 1", "Topic 2", "Topic 3"]
        """
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama-3.1-8b-instant", # Use the correct, active model name
            temperature=1.2,
            response_format={"type": "json_object"},
        )
        response_content = chat_completion.choices[0].message.content
        topics_data = json.loads(response_content)

         # --- THIS IS THE NEW, SMARTER PARSING LOGIC ---
        raw_topics = topics_data if isinstance(topics_data, list) else topics_data.get('topics', [])
        
        # Flatten the list in case the AI returns a list within a list
        topics = []
        for item in raw_topics:
            if isinstance(item, list):
                topics.extend(item)
            else:
                topics.append(item)

        # Clean up any non-string items (like the '***')
        cleaned_topics = [str(topic) for topic in topics if isinstance(topic, str)]
        
        if cleaned_topics:
            print(f"  - Found and cleaned topics: {cleaned_topics[:TOPICS_PER_REGION]}")
            return cleaned_topics[:TOPICS_PER_REGION]
        else:
            print("  - AI did not return a valid list of topics.")
            return []
        # --- END OF NEW LOGIC ---
        
        # Handle both list and dict responses from the AI
        topics = topics_data if isinstance(topics_data, list) else topics_data.get('topics', [])
        
        if topics:
            print(f"  - Found topics: {topics}")
            return topics
        else:
            print("  - AI did not return a valid list of topics.")
            return []
    except Exception as e:
        print(f"  - AI topic generation failed: {e}")
        return []

def generate_initial_article(keyword, language_code):
    """Calls our own API to generate the base article in a specific language."""
    print(f"  - Generating article for: '{keyword}' in language '{language_code}'...")
    try:
        query_with_lang = f"{keyword} (write in {language_code})"
        response = requests.post(GENERATION_API_URL, json={'query': query_with_lang}, timeout=300)
        response.raise_for_status()
        print("    - Article generated successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"    - Error generating article: {e}")
        return None

def translate_text(text, target_language, source_language):
    """Translates text using LibreTranslate with a polite delay."""
    if not text or source_language == target_language:
        return text
    
    time.sleep(1 + random.random()) # Polite 1-2 second delay
    
    print(f"      - Translating from '{source_language}' to '{target_language}'...")
    payload = {'q': text, 'source': source_language, 'target': target_language, 'format': 'text'}
    
    try:
        response = requests.post(LIBRETRANSLATE_API_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get('translatedText', text)
    except requests.exceptions.RequestException:
        return text # Return original on failure

def run_daily_job():
    """The main function to orchestrate the multi-region, multi-lingual process."""
    print("--- Starting Daily Multi-Region AI-Topic Content Job ---")
    
    for country_name, region_data in TARGET_REGIONS.items():
        primary_lang = region_data['lang']
        print(f"\n--- Processing Region: {country_name.upper()} ---")

        # 1. Get AI-generated topics for the specific country
        keywords = get_ai_generated_topics_for_region(country_name)
        
        for keyword in keywords:
            # --- POLITENESS TIMER ---
            # Wait 20 seconds before generating the next article
            print("\nWaiting 20 seconds before next generation...")
            time.sleep(20)

            # 2. Generate the base article in the country's primary language
            initial_article = generate_initial_article(keyword, primary_lang)
            
            if not initial_article:
                continue

            print(f"    --- Processing translations for article: '{initial_article['title']}' ---")
            
            # --- DATABASE SAVING LOGIC FOR INITIAL ARTICLE ---
            # You would implement your database saving logic here, e.g.:
            # from app import app, db, Article
            # with app.app_context():
            #   original_article = Article.query.get(initial_article['id'])
            #   ...

            # 3. Translate the initial article into all other target languages
            for lang_code in ALL_TARGET_LANGUAGES:
                if lang_code == primary_lang:
                    continue

                try:
                    translated_title = translate_text(initial_article['title'], lang_code, primary_lang)
                    translated_desc = translate_text(initial_article['meta_description'], lang_code, primary_lang)
                    translated_content = translate_text(initial_article['content'], lang_code, primary_lang)
                    translated_slug = slugify(translated_title)

                    print(f"    - Successfully prepared translation for '{lang_code}'.")
                    
                    # --- DATABASE SAVING LOGIC FOR TRANSLATION ---
                    # ...

                except Exception as e:
                    print(f"    - An unexpected error occurred while translating to '{lang_code}': {e}")

    print("\n--- Daily Content Generation Job Finished ---")


if __name__ == '__main__':
    run_daily_job()