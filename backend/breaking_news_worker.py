# /backend/breaking_news_worker.py
import os
import requests
import time
import json
from slugify import slugify
from groq import Groq
from app import app, db, Article, Category
import feedparser 

## --- CONFIGURATION ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
NEWS_API_URL = "https://newsapi.org/v2/top-headlines"
ARTICLES_TO_GENERATE = 2
groq_client = Groq(api_key=os.getenv("GROQ_APISec_KEY"))


## --- STEP 1: NEWS DISCOVERY (USING NEWSAPI) ---
def fetch_headlines_from_rss():
    """Fetches and combines headlines from a list of RSS feeds."""
    # List of RSS feeds you want to check
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
            # The 'entries' key contains the list of articles
            for entry in feed.entries:
                # We add the title to our list
                all_headlines.append(entry.title)
        except Exception as e:
            print(f"Could not parse RSS feed {url}. Error: {e}")
            
    if not all_headlines:
        print("No headlines found from any RSS feed.")
        return []

    # Remove duplicates and shuffle to get a variety
    unique_headlines = list(set(all_headlines))
    print(f"Found {len(unique_headlines)} unique headlines.")
    return unique_headlines

## --- STEP 2: DEDICATED NEWS GENERATION (USING "GROQ API 2") ---

def get_news_generation_prompt(headline):
    """Creates a specialized prompt for generating a news article."""
    category_list = "['Technology', 'Health', 'Science', 'Business', 'Culture', 'World News', 'Travel', 'Food', 'Finance', 'Education', 'Lifestyle', 'Entertainment']"

    return f"""
    You are a professional journalist for a major international news outlet. Your writing is objective, factual, and follows the "inverted pyramid" structure.

    **Headline:** "{headline}"

    **Your Task:**
    Write a comprehensive, well-structured news article of at least 1000 words based on this headline.

    **CRITICAL REQUIREMENTS:**
    1.  **Structure:**
        -   Start with a strong lead paragraph (dateline included, e.g., "PATNA, India –") that summarizes the most crucial information (who, what, when, where, why).
        -   Use subsequent paragraphs to provide details, context, background information, and quotes (real or plausible hypothetical quotes from experts or officials).
        -   Use Markdown for formatting, including H3 (`###`) subheadings for different sections of the article.
    2.  **Tone:** Maintain a neutral, professional, and journalistic tone. Avoid speculation or personal opinion.
    3.  **Content:** The information must be plausible and well-researched based on your training data.
    4.  **Image Placeholders:** Include exactly **two** `[IMAGE: A detailed, journalistic prompt for a relevant news photo]` placeholders at appropriate points.

    **JSON Output Structure:**
    You MUST generate a single, valid JSON object with these exact keys:
    -   `"title"`: The original headline.
    -   `"meta_description"`: A concise, SEO-friendly summary of the article (under 155 characters).
    -   `"category"`: The single most relevant news category (e.g., "Technology", "Politics", "Business", "World News").
    -   `"authorName"`: A plausible journalist's name.
    -   `"authorBio"`: A one-sentence bio for the journalist (e.g., "A staff writer covering technology and finance.").
    -   `"content"`: The full news article in Markdown format.
    """

def generate_article_with_groq_v2(headline):
    """
    Generates and saves a news article using a dedicated Groq model and prompt.
    """
    print(f"Generating article with 'Groq V2' for: '{headline}'")
    prompt = get_news_generation_prompt(headline)
    try:
        chat_completion = groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            # Using a more powerful model for higher quality news writing
            model="llama-3.1-70b-versatile",
            temperature=0.6, # Lower temperature for more factual, less creative writing
            response_format={"type": "json_object"},
        )
        response_content = chat_completion.choices[0].message.content
        data = json.loads(response_content)

        # Save the new article directly to the database
        slug = slugify(data['title'])
        
        # Check if an article with this slug already exists
        existing_article = Article.query.filter_by(slug=slug, lang='en').first()
        if existing_article:
            print(f"  -> Article with slug '{slug}' already exists. Skipping database save.")
            return None

        new_article = Article(
            slug=slug,
            title=data['title'],
            meta_description=data['meta_description'],
            content=data['content'],
            author_name=data.get('authorName'),
            author_bio=data.get('authorBio'),
            is_published=True,
            is_breaking_news=True # Flag this as breaking news
        )
        
        # Handle Category
        category_name = data.get('category')
        if category_name:
            category = Category.query.filter_by(name=category_name).first()
            if not category:
                category = Category(name=category_name, slug=slugify(category_name))
                db.session.add(category)
            new_article.categories.append(category)
        
        db.session.add(new_article)
        db.session.commit()
        print(f"  -> Successfully generated and saved article: '{new_article.title}'")
        return new_article

    except Exception as e:
        print(f"  -> A critical error occurred during Groq V2 generation or DB save: {e}")
        return None

## --- STEP 3: MAIN JOB ORCHESTRATION ---

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