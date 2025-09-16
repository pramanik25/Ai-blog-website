# /backend/utils.py
import time
import requests
import random
from slugify import slugify
from models import db, Article

# Define all your target languages in one place
ALL_TARGET_LANGUAGES = ['en', 'hi', 'fr', 'de', 'pt', 'es', 'it', 'ja', 'ko', 'ru']
LIBRETRANSLATE_API_URL = "https://libretranslate.de/translate"

def translate_text(text, target_language, source_language):
    """Translates text using LibreTranslate with a 10-second delay and retries."""
    if not text or source_language == target_language:
        return text
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # --- CHANGED ---
            # Apply a fixed 10-second wait before every attempt.
            print("      - Waiting 10 seconds before translation...")
            time.sleep(10)
            # --- END OF CHANGE ---

            print(f"      - Translating from '{source_language}' to '{target_language}' (Attempt {attempt + 1})...")
            payload = {'q': text, 'source': source_language, 'target': target_language, 'format': 'text'}
            
            response = requests.post(LIBRETRANSLATE_API_URL, json=payload, timeout=60)
            
            if response.status_code == 200:
                return response.json().get('translatedText', text)
            else:
                print(f"      - !!! TRANSLATION ATTEMPT FAILED (HTTP {response.status_code}): {response.text}")
        
        except requests.exceptions.RequestException as e:
            print(f"      - !!! TRANSLATION ATTEMPT FAILED (Request Exception): {e}")

    print(f"      - !!! FAILED all {max_retries} translation attempts. Returning original text. !!!")
    return text

def create_and_save_translations(original_article):
    """
    Takes an article object, translates it into all target languages,
    and saves them to the database.
    """
    print(f"--- Starting translation process for article ID: {original_article.id} ---")
    source_lang = original_article.lang

    for lang_code in ALL_TARGET_LANGUAGES:
        if lang_code == source_lang:
            continue

        # Check if a translation already exists for this language
        if Article.query.filter_by(original_article_id=original_article.id, lang=lang_code).first():
            print(f"  -> Translation for '{lang_code}' already exists. Skipping.")
            continue

        try:
            translated_title = translate_text(original_article.title, lang_code, source_lang)
            translated_slug = slugify(translated_title)
            
            # If the translated slug is empty, skip this translation
            if not translated_slug:
                print(f"  -> Skipping translation for '{lang_code}' due to empty slug from title: '{translated_title}'")
                continue

            translated_meta = translate_text(original_article.meta_description, lang_code, source_lang)
            translated_content = translate_text(original_article.content, lang_code, source_lang)

            new_translation = Article(
                slug=translated_slug,
                lang=lang_code,
                title=translated_title,
                meta_description=translated_meta,
                content=translated_content,
                image_url=original_article.image_url,
                is_published=True,
                is_breaking_news=original_article.is_breaking_news,
                author_name=original_article.author_name,
                author_bio=original_article.author_bio,
                original_article_id=original_article.id
            )
            
            for category in original_article.categories:
                new_translation.categories.append(category)
                
            db.session.add(new_translation)
            db.session.commit()
            print(f"  -> Successfully created and saved translation for '{lang_code}'.")

        except Exception as e:
            print(f"  -> A critical error occurred while creating translation for '{lang_code}': {e}")
            db.session.rollback() # Rollback the session in case of an error