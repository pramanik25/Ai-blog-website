# backend/app.py
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
import replicate # For image generation
import requests # To download the generated image

# Load environment variables
load_dotenv()

# Configure Flask App
app = Flask(__name__)
frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
CORS(app, resources={r"/api/*": {"origins": frontend_url}})

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

HF_API_URL = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
HF_API_TOKEN = os.getenv("HUGGINGFACE_API_TOKEN")


# --- API ROUTES ---
@app.route('/api/generate-content', methods=['POST'])
def generate_content_text_only():
    """
    This endpoint is now super fast. It ONLY generates the text content
    with placeholders and saves it as a draft.
    """
    query = request.json.get('query')
    if not query:
        return jsonify({"error": "Query is required"}), 400

    response_content = None # Initialize for logging
    data = {} # Initialize data
    try:
        # --- Stage 1: Generate Text Content with Placeholders ---
        try:
            print("Attempting API call for text generation...")
            combined_prompt = get_combined_prompt(query)
            
            # --- FIX #1: Use the correct variable name 'client' ---
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": combined_prompt}],
                model="llama-3.1-8b-instant", # Use correct model from Groq playground
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            response_content = chat_completion.choices[0].message.content
            data = json.loads(response_content)
            print("Text generation successful.")
        except Exception as e:
            print(f"JSON mode failed: {e}. Retrying in text mode...")
            
            # --- FIX #2: Restore the complete fallback logic ---
            combined_prompt = get_combined_prompt(query) # Re-get prompt
            # --- Use the correct variable name 'client' here too ---
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": combined_prompt}],
                model="llama-3.1-8b-instant",
                temperature=0.7,
            )
            response_content = chat_completion.choices[0].message.content
            json_start = response_content.find('{')
            json_end = response_content.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                json_string = response_content[json_start:json_end]
                data = json.loads(json_string, strict=False)
                print("Text mode fallback successful.")
            else:
                raise ValueError("No valid JSON object found in the AI response even after fallback.")
        
        if data.get("title") == "Invalid Topic Request":
            return jsonify({"error": "The requested topic could not be generated."}), 422

        # --- Stage 2: Save Text-Only Article to Database ---
        slug = data['slug']
        existing_article = Article.query.filter_by(slug=slug).first()
        if existing_article:
            return jsonify(existing_article.to_dict()), 200

        new_article = Article(
            slug=slug,
            title=data['title'],
            meta_description=data['meta_description'],
            content=data['content'],
            is_published=True
        )
        db.session.add(new_article)
        db.session.commit()

        print("Text-only article saved successfully.")
        return jsonify(new_article.to_dict()), 201

    except Exception as e:
        print(f"A critical error occurred in generate_content_text_only: {e}")
        if response_content:
            print(f"---AI TEXT RESPONSE THAT CAUSED FAILURE---\n{response_content}")
        return jsonify({"error": "A critical error occurred during text generation."}), 500

@app.route('/api/generate-image', methods=['POST'])
def generate_image_for_placeholder():
    """
    This new, dedicated endpoint handles generating one image at a time.
    It's called by the frontend after the page has already loaded.
    """
    data = request.json
    prompt = data.get('prompt')
    article_slug = data.get('slug')
    placeholder_index = data.get('index')

    if not all([prompt, article_slug, placeholder_index is not None]):
        return jsonify({"error": "Prompt, slug, and index are required"}), 400

    try:
        # --- Generate Image with Hugging Face ---
        print(f"Generating image for slug '{article_slug}' with prompt: '{prompt}'")
        headers = {"Authorization": f"Bearer {HF_API_TOKEN}"}
        payload = {"inputs": prompt}
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        image_bytes = response.content
        
        if not image_bytes:
            raise ValueError("Hugging Face API returned no image data.")
            
        # --- Upload to Firebase ---
        bucket = storage.bucket()
        destination_blob_name = f"images/{article_slug}-{placeholder_index + 1}.png"
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_string(image_bytes, content_type='image/png')
        blob.make_public()
        image_url = blob.public_url
        print(f"Image uploaded successfully: {image_url}")
        
        # --- Update the Article in the Database ---
        # Find the article and replace the placeholder with the final URL
        article = Article.query.filter_by(slug=article_slug).first()
        if article:
            placeholder_full_tag = f"[IMAGE: {prompt}]"
            markdown_image_tag = f"![{prompt}]({image_url})"
            
            # Update hero image if it's the first one
            if article.image_url is None:
                article.image_url = image_url
            
            article.content = article.content.replace(placeholder_full_tag, markdown_image_tag, 1)
            db.session.commit()

        return jsonify({"imageUrl": image_url})

    except Exception as e:
        print(f"A critical error occurred in generate_image_for_placeholder: {e}")
        return jsonify({"error": "Failed to generate image."}), 500

    
# The get_article route remains exactly the same
@app.route('/api/get-article/<slug>', methods=['GET'])
def get_article(slug):
    article = Article.query.filter_by(slug=slug, is_published=True).first()
    if article:
        return jsonify(article.to_dict())
    return jsonify({"error": "Article not found"}), 404

@app.route('/api/articles', methods=['GET'])
def get_all_articles():
    # Get query parameters for pagination, with defaults
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int) # Default limit is 10, but we'll ask for 2 from the frontend
    exclude_slug = request.args.get('exclude', None, type=str)

    try:
        # Start building the query
        query = Article.query.filter_by(is_published=True)

        # If an exclude_slug is provided, filter it out
        if exclude_slug:
            query = query.filter(Article.slug != exclude_slug)

        # Order by the newest first
        query = query.order_by(Article.id.desc())
        
        # Paginate the results
        paginated_articles = query.paginate(page=page, per_page=limit, error_out=False)
        
        articles = paginated_articles.items
        
        article_list = [
            {"id": article.id, "slug": article.slug, "title": article.title}
            for article in articles
        ]
        
        return jsonify({
            "articles": article_list,
            "has_more": paginated_articles.has_next # Tell the frontend if there are more pages
        })

    except Exception as e:
        print(f"An error occurred while fetching articles: {e}")
        return jsonify({"error": "Failed to fetch articles"}), 500
    

    # --- ADMIN API ROUTES ---

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")

# A helper function to check the secret key
def is_admin():
    return request.headers.get('x-admin-secret-key') == ADMIN_SECRET_KEY

@app.route('/api/admin/articles', methods=['GET'])
def admin_get_all_articles():
    if not is_admin():
        return jsonify({"error": "Unauthorized"}), 401
    
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

if __name__ == '__main__':
    app.run(debug=True, port=5001)