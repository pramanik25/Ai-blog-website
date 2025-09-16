import os
import json
import requests
import time
from datetime import date
from groq import Groq
import subprocess
from app import app, db, Article
from prompts import get_ebook_outline_prompt
from slugify import slugify
from utils import create_and_save_translations

# --- CONFIGURATION ---
WEEKLY_PLAN_FILE = "weekly_plan.json"
GENERATION_API_URL = os.getenv("GENERATION_API_URL")
GUMROAD_ACCESS_TOKEN = os.getenv("GUMROAD_ACCESS_TOKEN")
groq_client = Groq(api_key=os.getenv("GROQ_APISEC_KEY"))

# --- EBOOK PLANNING ---
def get_or_create_ebook_plan():
    """Loads this week's ebook plan from a file, or generates a new one."""
    current_week = date.today().isocalendar()[1]
    plan = {}
    if os.path.exists(WEEKLY_PLAN_FILE):
        with open(WEEKLY_PLAN_FILE, 'r', encoding='utf-8') as f:
            plan = json.load(f)

    if not plan or plan.get("week_number") != current_week:
        print("No valid ebook plan for this week. Generating a new one...")
        try:
            prompt = get_ebook_outline_prompt()
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"},
            )
            new_plan = json.loads(chat_completion.choices[0].message.content)
            new_plan["week_number"] = current_week
            for chapter in new_plan["chapters"]:
                chapter["status"] = "pending"
                chapter["slug"] = ""
            
            with open(WEEKLY_PLAN_FILE, 'w', encoding='utf-8') as f:
                json.dump(new_plan, f, indent=2)
            print(f"Successfully generated new ebook plan: '{new_plan['ebook_title']}'")
            return new_plan
        except Exception as e:
            print(f"FATAL: Could not generate a new ebook plan. Error: {e}")
            return None
    
    print(f"Loaded existing ebook plan for week {current_week}: '{plan.get('ebook_title')}'")
    return plan

def get_next_chapter_to_write(plan):
    """Finds the next pending chapter and provides context."""
    chapters = plan.get("chapters", [])
    for i, chapter in enumerate(chapters):
        if chapter["status"] == "pending":
            return {
                "current_chapter_index": i,
                "current_chapter_title": chapter["title"],
                "ebook_title": plan.get("ebook_title"),
                "previous_chapter_title": chapters[i-1]["title"] if i > 0 else None,
                "next_chapter_title": chapters[i+1]["title"] if i < len(chapters) - 1 else None
            }
    return None

def mark_chapter_as_completed(plan, chapter_index, generated_slug):
    """Updates the plan file to mark a chapter as done."""
    plan["chapters"][chapter_index]["status"] = "completed"
    plan["chapters"][chapter_index]["slug"] = generated_slug
    with open(WEEKLY_PLAN_FILE, 'w', encoding='utf-8') as f:
        json.dump(plan, f, indent=2)
    print(f"Marked chapter as completed: '{plan['chapters'][chapter_index]['title']}'")

def generate_chapter_article(context, category_name):
    """Calls the main backend API to generate the article with full context."""
    title = context["current_chapter_title"]
    print(f"Requesting article generation for: '{title}'")
    
    context_query = f"""
    Write a blog post for the following chapter of an ebook.
    Ebook Title: "{context['ebook_title']}"
    Chapter Title: "{title}"
    Previous Chapter: "{context.get('previous_chapter_title', 'N/A')}"
    Next Chapter: "{context.get('next_chapter_title', 'N/A')}"
    Ensure the content flows logically from the previous chapter and sets the stage for the next. The tone should be consistent with a comprehensive guide for beginners.
    """
    
    try:
        response = requests.post(GENERATION_API_URL, json={'query': context_query}, timeout=300)
        response.raise_for_status()
        
        article_data = response.json()
        print("  - Chapter generated and saved via API successfully.")
    
        original_article = Article.query.get(article_data['id'])

        if original_article:
            create_and_save_translations(original_article)

        return article_data 
    except requests.exceptions.RequestException as e:
        print(f"  - Error calling generation API: {e}")
        return None

# --- EBOOK COMPILATION & PUBLISHING ---
def convert_md_to_pdf(md_path, pdf_path, metadata):
    """Converts a Markdown file to a professional PDF using Pandoc."""
    print(f"  -> Converting {md_path} to {pdf_path} using Pandoc...")
    try:
        command = [
            "pandoc", md_path,
            "-o", pdf_path,
            "--template", "templates/ebook_template.tex",
            "--toc",
            "-V", f"title={metadata['title']}",
            "-V", f"subtitle={metadata['subtitle']}",
            "-V", "author=Pramanik",
            "-V", f"date={date.today().strftime('%B %Y')}"
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        print("  -> PDF conversion successful.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  -> ERROR: PDF conversion failed. Pandoc stderr: {e.stderr}")
        return False
    except FileNotFoundError:
        print("  -> ERROR: Pandoc command not found. Is it installed in the environment?")
        return False

def publish_to_gumroad(pdf_path, plan):
    """Creates a new product on Gumroad and uploads the PDF."""
    if not GUMROAD_ACCESS_TOKEN:
        print("  -> GUMROAD_ACCESS_TOKEN not found. Skipping upload.")
        return None
    
    print(f"  -> Publishing {pdf_path} to Gumroad...")
    try:
        with open(pdf_path, 'rb') as f:
            files = {'files[]': (os.path.basename(pdf_path), f, 'application/pdf')}
            data = {
                'access_token': GUMROAD_ACCESS_TOKEN,
                'name': plan['ebook_title'],
                'price': '49',
                'description': f"A comprehensive guide on {plan['ebook_title']}. This ebook contains in-depth chapters covering everything you need to know to get started.",
            }
            response = requests.post("https://api.gumroad.com/v2/products", data=data, files=files)
            response.raise_for_status()
            product_data = response.json()
            if product_data.get('success'):
                product_url = product_data['product']['short_url']
                print(f"  -> Successfully published to Gumroad! URL: {product_url}")
                return product_url
            else:
                print(f"  -> Gumroad API Error: {product_data.get('message')}")
                return None
    except Exception as e:
        print(f"  -> An error occurred while publishing to Gumroad: {e}")
        return None

def compile_ebook_if_complete(plan):
    """Checks if all chapters are written, then compiles and publishes the ebook."""
    chapters = plan.get("chapters", [])
    if not all(c.get("status") == "completed" for c in chapters):
        return

    ebook_slug = slugify(plan["ebook_title"])
    md_filename = f"{ebook_slug}.md"
    pdf_filename = f"{ebook_slug}.pdf"
    
    if os.path.exists(pdf_filename):
        print(f"PDF '{pdf_filename}' already exists. Skipping compilation and publishing.")
        return

    print(f"--- All chapters complete! Compiling ebook: {md_filename} ---")
    
    full_content = f"# {plan['ebook_title']}\n\n## {plan['subtitle']}\n\n"
    
    for i, chapter in enumerate(chapters):
        article_slug = chapter.get("slug")
        if not article_slug: continue
        article = Article.query.filter_by(slug=article_slug).first()
        if article:
            chapter_header = f"Chapter {i}: {chapter['title']}" if "Chapter" not in chapter["title"] and "Introduction" not in chapter["title"] and "Conclusion" not in chapter["title"] else chapter["title"]
            full_content += f"## {chapter_header}\n\n{article.content}\n\n---\n\n"
    
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(full_content)

    pdf_success = convert_md_to_pdf(md_filename, pdf_filename, {"title": plan["ebook_title"], "subtitle": plan["subtitle"]})
    
    if pdf_success:
        product_url = publish_to_gumroad(pdf_filename, plan)
        if product_url:
            with open("published_ebooks.log", "a", encoding='utf-8') as log_file:
                log_file.write(f"{plan['ebook_title']}|{product_url}\n")

# --- MAIN JOB ORCHESTRATION ---
def run_weekly_job():
    print("--- Starting Weekly Ebook Generation Job ---")
    with app.app_context():
        plan = get_or_create_ebook_plan()
        if not plan: return

        next_chapter = get_next_chapter_to_write(plan)
        if not next_chapter:
            print("All chapters for this week's ebook have been generated.")
            compile_ebook_if_complete(plan)
            return

        article_data = generate_chapter_article(next_chapter, plan.get("category", "General"))
        
        if article_data and article_data.get("slug"):
            mark_chapter_as_completed(next_chapter["current_chapter_index"], article_data["slug"])
            # Reload plan from file to get the latest state
            with open(WEEKLY_PLAN_FILE, 'r', encoding='utf-8') as f:
                plan = json.load(f)
        else:
            print("Chapter generation failed. Will retry on the next run.")
        
        compile_ebook_if_complete(plan)
    print("--- Weekly Ebook Generation Job Finished ---")

if __name__ == '__main__':
    run_weekly_job()