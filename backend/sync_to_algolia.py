# /backend/sync_to_algolia.py
import os
from dotenv import load_dotenv
from algoliasearch.search_client import SearchClient

# This script needs access to your Flask app and models
from app import app, Article

# Load environment variables from .env file
load_dotenv()

# --- SETUP ---
ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")
ALGOLIA_ADMIN_API_KEY = os.getenv("ALGOLIA_ADMIN_API_KEY")
ALGOLIA_INDEX_NAME = "articles" # The name of the index you created

def sync_articles():
    """
    Fetches all published articles from the database and syncs them with Algolia.
    """
    # This function must be run within the Flask application context
    with app.app_context():
        print("Connecting to Algolia...")
        client = SearchClient.create(ALGOLIA_APP_ID, ALGOLIA_ADMIN_API_KEY)
        index = client.init_index(ALGOLIA_INDEX_NAME)

        print("Fetching published articles from the database...")
        articles_to_index = []
        published_articles = Article.query.filter_by(is_published=True).all()

        for article in published_articles:
            # We format the data exactly how we want it for searching
            record = {
                'objectID': article.id, # Algolia requires a unique 'objectID'
                'title': article.title,
                'slug': article.slug,
                'meta_description': article.meta_description,
                'authorName': article.author_name,
                'image_url': article.image_url,
                # We can even index categories to make them searchable
                'categories': [cat.name for cat in article.categories]
            }
            articles_to_index.append(record)

        if not articles_to_index:
            print("No published articles to index.")
            return

        print(f"Found {len(articles_to_index)} articles. Pushing to Algolia...")
        
        # This replaces all existing records in the index with the new ones
        index.save_objects(articles_to_index, {'autoGenerateObjectIDIfNotExist': False})
        
        print("✅ Successfully synced articles to Algolia!")

if __name__ == '__main__':
    sync_articles()
    