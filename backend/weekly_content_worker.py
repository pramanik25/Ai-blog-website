# /backend/weekly_content_worker.py
import os
import json
import requests
import time
from datetime import date
from groq import Groq

# This script needs to interact with your database models and app context
# This is a common pattern for standalone Flask scripts
from app import app, db, Article, Category
from prompts import get_weekly_theme_prompt
from slugify import slugify

# --- CONFIGURATION ---
WEEKLY_PLAN_FILE = "weekly_plan.json" # A simple file to store the week's plan
GENERATION_API_URL = os.getenv("GENERATION_API_URL")
# ... (Add LibreTranslate and other constants if needed for translation)

# --- SETUP ---
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- FUNCTIONS ---

def get_or_create_weekly_plan():
    """Loads this week's plan from a file, or generates a new one if it's a new week."""
    current_week = date.today().isocalendar()[1] # Get the current week number
    
    plan = {}
    if os.path.exists(WEEKLY_PLAN_FILE):
        with open(WEEKLY_PLAN_FILE, 'r') as f:
            plan = json.load(f)

    # If the plan is empty or for a previous week, generate a new one
    if not plan or plan.get("week_number") != current_week:
        print("No valid plan found for this week. Generating a new one...")
        try:
            prompt = get_weekly_theme_prompt()
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.1-8b-instant",
                response_format={"type": "json_object"},
            )
            response_content = chat_completion.choices[0].message.content
            new_plan = json.loads(response_content)
            new_plan["week_number"] = current_week
            new_plan["completed_topics"] = [] # Track completed articles

            with open(WEEKLY_PLAN_FILE, 'w') as f:
                json.dump(new_plan, f, indent=2)
            print(f"Successfully generated new plan for week {current_week}. Pillar: '{new_plan['pillar_topic']}'")
            return new_plan
        except Exception as e:
            print(f"FATAL: Could not generate a new weekly plan. Error: {e}")
            return None
    
    print(f"Loaded existing plan for week {current_week}.")
    return plan

def get_next_topic_from_plan(plan):
    """Finds the next un-published topic from the weekly plan."""
    all_topics = plan.get("cluster_topics", [])
    completed_topics = plan.get("completed_topics", [])
    
    for topic in all_topics:
        if topic not in completed_topics:
            return topic
    return None # All topics for the week are completed

def mark_topic_as_completed(plan, topic):
    """Updates the plan file to mark a topic as done."""
    plan.setdefault("completed_topics", []).append(topic)
    with open(WEEKLY_PLAN_FILE, 'w') as f:
        json.dump(plan, f, indent=2)
    print(f"Marked topic as completed: '{topic}'")

def generate_article(keyword, category_name):
    """Calls our main backend API to generate the article."""
    print(f"Requesting article generation for: '{keyword}'")
    try:
        # We add the category to the query to guide the AI
        query_with_category = f"{keyword} (category: {category_name})"
        response = requests.post(GENERATION_API_URL, json={'query': query_with_category}, timeout=300)
        response.raise_for_status()
        print("  - Article generated and saved via API successfully.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  - Error calling generation API: {e}")
        return None

def run_weekly_job():
    print("--- Starting Weekly Content Cluster Job ---")
    
    # This job needs to run inside the Flask application context to access the database
    with app.app_context():
        # 1. Get the plan for the week
        plan = get_or_create_weekly_plan()
        if not plan:
            return # Exit if we couldn't get a plan

        # 2. Get the next topic to write about
        topic_to_generate = get_next_topic_from_plan(plan)
        
        if not topic_to_generate:
            print("All topics for this week have been completed. Job finished.")
            return

        # 3. Generate the article in English
        # We can add translation logic here later if needed
        article_data = generate_article(topic_to_generate, plan.get("category", "General"))
        
        if article_data:
            # 4. Mark the topic as completed in our plan file
            mark_topic_as_completed(plan, topic_to_generate)
            # You could add translation logic here, calling the LibreTranslate function
        else:
            print("Article generation failed. Will retry on the next run.")

    print("--- Weekly Content Cluster Job Finished ---")

if __name__ == '__main__':
    run_weekly_job()