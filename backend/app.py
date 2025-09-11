import time
import os
import json
import re
# import google.generativeai as genai # <--- We don't need this anymore
from groq import Groq # <--- Import the new library
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from models import db, Article
from prompts import get_combined_prompt # We still use our great prompt!
import firebase_admin
from firebase_admin import credentials, storage
from models import db, Article, Category 
import requests
import random
import base64
from slugify import slugify

# Load environment variables
load_dotenv()

# Configure Flask App
app = Flask(__name__)

frontend_url = os.getenv("FRONTEND_URL") 
allowed_origins = ["http://localhost:3000"]

if frontend_url:
    allowed_origins.append(frontend_url)

# Apply the CORS configuration.
# The 'origins' parameter directly accepts our list of allowed domains.
CORS(app, origins=allowed_origins, supports_credentials=True)

# --- Ensure your Firebase setup is present ---
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-credentials.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET")
    })

    
# Configure Database (this stays the same)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300, 
}
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    db.create_all()


client = Groq(
    api_key=os.getenv("GROQ_API_KEY"),
)

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
FIREWORKS_API_URL = "https://api.fireworks.ai/inference/v1/workflows/accounts/fireworks/models/flux-1-schnell-fp8/text_to_image"
FIREWORKS_MODEL_ID = "stable-diffusion-xl-lightning-4step"

def get_random_fallback_image():
    """
    Fetches the list of all images from Firebase Storage
    and returns the public URL of a random one.
    """
    try:
        print("--- Initiating fallback: fetching existing images from Firebase Storage ---")
        bucket = storage.bucket()
        # List all blobs in the 'images/' directory
        blobs = bucket.list_blobs(prefix='images/')
        
        # Collect all public URLs into a list, skipping the folder itself
        image_urls = [blob.public_url for blob in blobs if blob.name != 'images/']
        
        if not image_urls:
            print("--- Fallback failed: No existing images found in Firebase Storage. ---")
            return None

        # Select one URL at random
        random_url = random.choice(image_urls)
        print(f"--- Fallback successful. Selected random image: {random_url} ---")
        return random_url
    except Exception as e:
        print(f"--- Fallback failed with an error: {e} ---")
        return None


# --- API ROUTES ---
@app.route('/api/health', methods=['GET'])
def health_check():
    """A simple endpoint to verify the service is up and running."""
    return jsonify({"status": "ok"}), 200

@app.route('/api/generate-content', methods=['POST'])
def generate_content_text_only():
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "Query is required"}), 400

    response_content = None
    data = {}
    try:
        # --- Stage 1: Get AI Response (Unified Logic) ---
        print("Attempting API call for text generation...")
        combined_prompt = get_combined_prompt(query)
        try:
            # First, try the fast, clean JSON mode
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": combined_prompt}],
                model="llama-3.1-8b-instant", # Use the correct, active model from Groq playground
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            response_content = chat_completion.choices[0].message.content
            print("JSON mode successful.")
        except Exception as e:
            # If it fails, fall back to text mode
            print(f"JSON mode failed: {e}. Retrying in text mode...")
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": combined_prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.7,
            )
            response_content = chat_completion.choices[0].message.content
            print("Text mode fallback successful.")
        
        # --- Stage 2: Clean and Parse the Response (Unified Logic) ---
        print("Cleaning and parsing AI response...")
        # Fix the multi-line string """content""" issue if it exists
        # The lambda function takes the captured content, escapes it for JSON, and wraps it in standard double quotes.
        cleaned_response = re.sub(
            r'"content":\s*"""(.*?)"""',
            lambda match: f'"content": {json.dumps(match.group(1))}',
            response_content,
            flags=re.DOTALL
        )
        
        # Find and extract the JSON object from the potentially messy string
        json_start = cleaned_response.find('{')
        json_end = cleaned_response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_string = cleaned_response[json_start:json_end]
            data = json.loads(json_string, strict=False)
            print("Parsing successful.")
        else:
            raise ValueError("No valid JSON object found in the AI response after cleaning.")
        
        if data.get("title") == "Invalid Topic Request":
            return jsonify({"error": "The requested topic could not be generated."}), 422

        # --- Stage 3: Save to Database ---
        slug = data['slug']
        existing_article = Article.query.filter_by(slug=slug, lang='en').first()
        if existing_article:
            return jsonify(existing_article.to_dict()), 200

        new_article = Article(
            slug=slug,
            title=data['title'],
            meta_description=data['meta_description'],
            content=data['content'],
            is_published=True, # Save as draft
            author_name=data.get('authorName'),
            author_bio=data.get('authorBio'),
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

        print("Text-only article saved successfully.")
        return jsonify(new_article.to_dict()), 201

    except Exception as e:
        print(f"A critical error occurred in generate_content_text_only: {e}")
        if response_content:
            print(f"---AI TEXT RESPONSE THAT CAUSED FAILURE---\n{response_content}")
        return jsonify({"error": "A critical error occurred."}), 500
    
    
    
def get_random_fallback_image():
    """
    Fetches the list of all images from Firebase Storage
    and returns the public URL of a random one.
    """
    try:
        print("--- Initiating fallback: fetching existing images from Firebase Storage ---")
        bucket = storage.bucket()
        # List all blobs in the 'images/' directory
        blobs = bucket.list_blobs(prefix='images/')
        
        # Collect all public URLs into a list, skipping the folder itself
        image_urls = [blob.public_url for blob in blobs if blob.name != 'images/']
        
        if not image_urls:
            print("--- Fallback failed: No existing images found in Firebase Storage. ---")
            return None

        # Select one URL at random
        random_url = random.choice(image_urls)
        print(f"--- Fallback successful. Selected random image: {random_url} ---")
        return random_url
    except Exception as e:
        print(f"--- Fallback failed with an error: {e} ---")
        return None

@app.route('/api/generate-image', methods=['POST'])
def generate_image_for_placeholder():
    """
    Final, robust image generation with a Firebase Storage fallback.
    """
    data = request.json
    prompt = data.get('prompt')
    article_slug = data.get('slug')
    placeholder_index = data.get('index')

    if not all([prompt, article_slug, placeholder_index is not None]):
        return jsonify({"error": "Prompt, slug, and index are required"}), 400

    image_url = None
    try:
        # This is your primary image generation logic (e.g., with Fireworks.ai)
        # We will wrap it in a try...except block.
        print(f"Requesting image from Fireworks.ai for prompt: '{prompt}'")
        
        headers = {
            "Accept": "image/png",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {FIREWORKS_API_KEY}"
        }
        payload = {"prompt": f"{prompt}, cinematic, masterpiece, 8k"}
        
        response = requests.post(FIREWORKS_API_URL, headers=headers, json=payload, timeout=90)
        response.raise_for_status()
        
        image_bytes = response.content
        if not image_bytes:
            raise ValueError("Live API did not return an image.")

        print("Image generated by live API successfully.")
        
        # Upload the NEWLY generated image to Firebase
        bucket = storage.bucket()
        destination_blob_name = f"images/{article_slug}-{placeholder_index + 1}.png"
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(image_bytes, content_type='image/png')
        blob.make_public()
        image_url = blob.public_url
        print(f"Image uploaded to Firebase: {image_url}")

    except Exception as e:
        print(f"!!! Live image generation failed: {e}. Attempting to use fallback image. !!!")
        # --- THIS IS THE NEW FALLBACK LOGIC ---
        image_url = get_random_fallback_image()
        # --- END OF NEW LOGIC ---

    # --- This part now runs for BOTH successful generation AND successful fallback ---
    if image_url:
        # --- THIS IS THE DEFINITIVE FIX ---
        try:
            # You MUST use the app context for database operations in a background/async task
            with app.app_context():
                article_to_update = Article.query.filter_by(slug=article_slug).first()
                if article_to_update:
                    placeholder_full_tag = f"[IMAGE: {prompt}]"
                    if placeholder_full_tag in article_to_update.content:
                        markdown_image_tag = f"![{prompt}]({image_url})"
                        
                        # Set hero image if it's the first one
                        if article_to_update.image_url is None:
                            article_to_update.image_url = image_url
                        
                        # Replace placeholder and commit
                        article_to_update.content = article_to_update.content.replace(placeholder_full_tag, markdown_image_tag, 1)
                        db.session.commit()
                        print(f"SUCCESS: Database updated for article '{article_slug}'.")
                    else:
                        print(f"WARNING: Placeholder already processed for '{prompt}'.")
                else:
                    print(f"ERROR: Could not find article with slug '{article_slug}' to update.")

            return jsonify({"imageUrl": image_url})
        except Exception as db_error:
            print(f"A critical error occurred during database update: {db_error}")
            return jsonify({"error": "Failed to update article with image."}), 500
        # --- END OF DEFINITIVE FIX --
    else:
        # This only happens if BOTH live generation AND the fallback fail
        print("CRITICAL: Both live generation and fallback failed. No image will be used.")
        return jsonify({"error": "Failed to generate or find a fallback image."}), 500
    
# The get_article route remains exactly the same
@app.route('/api/get-article/<slug>', methods=['GET'])
def get_article(slug):
    article = Article.query.filter_by(slug=slug, is_published=True).first()
    if article:
        return jsonify(article.to_dict())
    return jsonify({"error": "Article not found"}), 404

@app.route('/api/articles', methods=['GET'])
def get_all_articles():
    # Get query parameters
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    exclude_slug = request.args.get('exclude', None, type=str)
    # --- THIS IS THE NEW LOGIC ---
    fetch_all = request.args.get('all', 'false', type=str).lower() == 'true'

    try:
        query = Article.query.filter_by(is_published=True)

        if exclude_slug:
            query = query.filter(Article.slug != exclude_slug)

        query = query.order_by(Article.id.desc())
        
        # --- AND THIS IS THE CONDITIONAL LOGIC ---
        if fetch_all:
            # If the client asks for all, skip pagination.
            articles = query.all()
            has_more = False
        else:
            # Otherwise, use the standard pagination for components like RecentPosts.
            paginated_articles = query.paginate(page=page, per_page=limit, error_out=False)
            articles = paginated_articles.items
            has_more = paginated_articles.has_next
        
        # We need to return the ID for React keys
        article_list = [
            {"id": article.id, "slug": article.slug, "title": article.title,"meta_description": article.meta_description,
                "image_url": article.image_url}
            for article in articles
        ]
        
        return jsonify({
            "articles": article_list,
            "has_more": has_more
        })

    except Exception as e:
        print(f"An error occurred while fetching articles: {e}")
        return jsonify({"error": "Failed to fetch articles"}), 500
    
@app.route('/api/categories', methods=['GET'])
def get_all_categories():
    """Fetches a list of all unique categories."""
    try:
        # Query the database for all categories, ordered by name
        categories = Category.query.order_by(Category.name.asc()).all()
        category_list = [category.to_dict() for category in categories]
        print(f"Found {len(category_list)} categories to return.")
        return jsonify(category_list)
    except Exception as e:
        print(f"An error occurred while fetching categories: {e}")
        return jsonify({"error": "Failed to fetch categories"}), 500
    
@app.route('/api/articles/category/<string:category_slug>', methods=['GET'])
def get_articles_by_category(category_slug):
    """Fetches all published articles for a specific category."""
    try:
        category = Category.query.filter_by(slug=category_slug).first_or_404()
        published_articles = [
            article.to_dict() 
            for article in category.articles 
            if article.is_published
        ]
        
        return jsonify({
            "category": category.to_dict(),
            "articles": published_articles
        })
    except Exception as e:
        print(f"An error occurred while fetching articles for category {category_slug}: {e}")
        return jsonify({"error": "Failed to fetch articles for this category"}), 500
    

    # --- ADMIN API ROUTES ---

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

# A helper function to check the secret key
def is_admin():
    return request.headers.get('x-admin-secret-key') == ADMIN_SECRET_KEY

@app.route('/api/admin/articles', methods=['GET'])
def admin_get_all_articles():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    
    articles = Article.query.order_by(Article.id.desc()).all()    
    article_list = [article.to_admin_dict() for article in articles]

    return jsonify(article_list)

@app.route('/api/admin/article/<int:article_id>/toggle', methods=['POST'])
def admin_toggle_publish(article_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    # Flip the boolean status
    article.is_published = not article.is_published
    db.session.commit()
    return jsonify(article.to_dict())

@app.route('/api/admin/article/<int:article_id>', methods=['DELETE'])
def admin_delete_article(article_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
        
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
        
    db.session.delete(article)
    db.session.commit()
    return jsonify({"message": "Article deleted successfully"})

@app.route('/api/admin/article/<int:article_id>/edit', methods=['PUT'])
def admin_edit_article(article_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    # Get the new content from the request body
    data = request.json
    new_content = data.get('content')
    
    if new_content is None:
        return jsonify({"error": "Content is required"}), 400
        
    article.content = new_content
    db.session.commit()
    
    print(f"Article {article_id} updated successfully.")
    return jsonify(article.to_dict())


@app.route('/api/admin/article/<int:article_id>', methods=['GET'])
def admin_get_article(article_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    return jsonify(article.to_dict()) # Use the full to_dict()

@app.route('/api/admin/article/<int:article_id>/regenerate-image', methods=['POST'])
def admin_regenerate_image(article_id):
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    
    article = Article.query.get(article_id)
    if not article:
        return jsonify({"error": "Article not found"}), 404
        
    data = request.json
    prompt = data.get('prompt')
    placeholder_full_tag = data.get('placeholder') # e.g., "[IMAGE: a description]"
    
    if not prompt or not placeholder_full_tag:
        return jsonify({"error": "Prompt and placeholder are required"}), 400

    try:
        print(f"Regenerating image for article {article_id} with prompt: '{prompt}'")
        
        # --- (This is the same trusted image generation logic from before) ---
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        payload = {"inputs": prompt}
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        image_bytes = response.content
        
        if not image_bytes:
            raise ValueError("Hugging Face API returned no image data.")
            
        # --- Upload to Firebase ---
        # We create a new unique name to avoid browser caching issues
        timestamp = int(time.time())
        bucket = storage.bucket()
        destination_blob_name = f"images/{article.slug}-{timestamp}.png"
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(image_bytes, content_type='image/png')
        blob.make_public()
        new_image_url = blob.public_url
        print(f"Image regenerated and uploaded: {new_image_url}")
        
        # --- Update the Article Content in the Database ---
        new_markdown_tag = f"![{prompt}]({new_image_url})"
        
        # Replace the specific old placeholder/image tag with the new one
        # We need to find the old URL to replace it
        old_content = article.content
        # Simple replacement for now. A more robust solution might parse Markdown.
        # This assumes the prompt is unique enough to identify the image tag.
        
        # Find the old markdown tag to replace
        # This is a simplification; a real app might need a more robust way to find the old tag
        # For now, we'll just replace the placeholder text
        article.content = old_content.replace(placeholder_full_tag, new_markdown_tag, 1)

        # Update the main hero image if it was the first one
        if article.image_url is None or article.image_url in old_content:
             article.image_url = new_image_url

        db.session.commit()

        return jsonify({"newImageUrl": new_image_url, "newContent": article.content})

    except Exception as e:
        print(f"A critical error occurred in admin_regenerate_image: {e}")
        return jsonify({"error": "Failed to regenerate image."}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)