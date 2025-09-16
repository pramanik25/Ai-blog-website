# /backend/prompts.py
import time
from datetime import date
from dateutil.relativedelta import relativedelta # You may need to install this: pip install python-dateutil

def get_future_viral_topics_prompt():
    """Asks the AI to predict topics that will trend in the NEXT MONTH from {today}"""
    """Asks the AI to predict future trending topics IN HINDI."""
    
    # Calculate next month's name and year
    today = date.today()
    next_month_date = today + relativedelta(months=1)
    next_month_name = next_month_date.strftime("%B")
    year = next_month_date.year

    return f"""
    You are an expert content strategist and cultural trend forecaster for a major news blog in India.
    It is currently {today.strftime("%B %Y")}. Your task is to plan the content calendar for **{next_month_name} {year}**.

    Identify 10 distinct topics that are **confirmed or highly likely to be trending search queries** in India and globally during **{next_month_name} {year}**.

    Focus ONLY on predictable, scheduled future events. Your instructions are:
    1.  **Analyze the calendar for {next_month_name} {year}.**
    2.  **Identify major festivals or holidays** scheduled for that month (e.g., Diwali, Christmas).
    3.  **Identify confirmed movie, TV show, or game release dates** for that month.
    4.  **Identify scheduled sporting events or tech launches.**
    5.  **DO NOT** include any events that have already happened in past month and past years (e.g., "Diwali 2023", "iPhone 16 launch"). All topics must be for the future.

    You MUST respond with ONLY a valid JSON object with a single key "future_topics", which is an array of 10 specific topic strings.
    """
def get_seo_prompt(query):
    return f"""
You are an world-class SEO expert and copywriter. Your task is to generate perfectly optimized metadata for a blog post based on a user's search query.

**User Query:** "{query}"

**Your Task:**
Generate the following metadata in a JSON format:
1.  **title**: A suspenseful, highly clickable, SEO-optimized title (50-60 characters). It MUST contain the primary keyword. Use techniques like asking a question, creating a knowledge gap (e.g., 'The One Secret About X...'), or using powerful words (e.g., 'Revealed', 'Shocking'). Example: If the topic is 'The History of AI', a good title would be 'AI's Hidden History: The Secret That Changes Everything'.
2.  **meta_description**: Under 155 characters. Summarize the article's content, include the keyword naturally, and end with a compelling call-to-action.
3.  **slug**: A URL-friendly slug. Lowercase, words separated by hyphens, and based on the primary keyword.

**Example Output Format:**
{{
  "title": "A suspenseful, highly clickable, SEO-optimized title (50-60 characters). It MUST contain the primary keyword. Use techniques like asking a question, creating a knowledge gap (e.g., 'The One Secret About X...'), or using powerful words (e.g., 'Revealed', 'Shocking'). Example: If the topic is 'The History of AI', a good title would be 'AI's Hidden History: The Secret That Changes Everything'"
  "meta_description": "Discover the best ways to do something with our expert guide. Learn more now!",
  "slug": "example-guide-to-something"
}}

**Generate the JSON for the query provided.**
"""

def get_article_prompt(query):
    return f"""
You are a leading subject matter expert and talented writer for a popular informational blog. Your audience is curious and wants clear, accurate, and comprehensive information.

**Topic:** "{query}"

**Your Task:**
Write a high-quality, in-depth, and engaging blog post of at least 1200 words on the given topic. The article must be structured for readability and SEO.

**Requirements:**
1.  **Structure:** Use Markdown for formatting. Start with an engaging introduction. Use H2 and H3 headings to create a logical structure. End with a concluding summary.
2.  **Content:** The information must be accurate, well-researched, and provide real value to the reader. Answer the core question of the query thoroughly.
3.  **Tone:** Write in an authoritative, trustworthy, and accessible tone.
4.  **SEO:** Naturally incorporate the main topic keywords throughout the article, especially in the headings.

**Do not include a main title (H1) in your output**, as this will be handled by the "title" metadata. Start directly with the introductory paragraph.
"""

def get_weekly_theme_prompt():
    return """
    You are an expert SEO and content strategist for a global blog.
    Your task is to plan a "content cluster" for the upcoming week. A content cluster consists of one main "Pillar Topic" and several supporting "Cluster Topics".

    Instructions:
    Generate a content plan for a single, popular, evergreen topic (e.g., "Personal Finance", "Fitness for Beginners", "Digital Photography").
    
    You MUST respond with ONLY a valid JSON object and nothing else.
    The JSON object must have this exact structure:
    {
      "pillar_topic": "The main, broad topic for the week",
      "cluster_topics": [
        "A highly specific, long-tail keyword related to the pillar topic",
        "Another specific, long-tail keyword",
        "Another specific, long-tail keyword",
        "Another specific, long-tail keyword",
        "Another specific, long-tail keyword",
        "Another specific, long-tail keyword",
        "Another specific, long-tail keyword"
      ],
      "category": "A single, broad category for all these articles (e.g., Finance, Health, Technology)"
    }

    Ensure there are exactly 7 cluster topics, one for each day of the week.
    """

# /backend/prompts.py

def get_keyword_prompt(query):
    return f"""
    You are an expert SEO keyword researcher.
    Your task is to generate a list of 7-10 highly relevant secondary keywords, long-tail keywords, and LSI (Latent Semantic Indexing) keywords for a main blog post topic.
    These keywords should be what users are actively searching for on Google.

    **Main Topic:** "{query}"

    You MUST respond with ONLY a valid JSON object with a single key "keywords", which is an array of strings. Do not include any other text or explanation.

    **Example Output Format:**
    {{
      "keywords": [
        "best seo practices 2025",
        "how to improve website ranking",
        "on-page seo checklist",
        "long-tail keyword strategy",
        "what are lsi keywords",
        "google search ranking factors",
        "technical seo audit"
      ]
    }}
    """

def get_combined_prompt(query, keywords=None):
    category_list = "['Technology', 'Health', 'Science', 'Business', 'Culture', 'World News', 'Travel', 'Food', 'Finance', 'Education', 'Lifestyle', 'Entertainment']"
    keyword_instruction = ""
    if keywords:
        keyword_list_str = ", ".join(f'"{k}"' for k in keywords)
        keyword_instruction = f"""

**SEO Keyword Integration:**
You MUST naturally weave the following keywords into the article, especially in the H2 and H3 headings and key paragraphs: {keyword_list_str}.
"""
    return f"""
You are a world-class subject matter expert and SEO content strategist. Your task is to write a comprehensive, authoritative, and deeply engaging blog post.

**Primary Topic:** "{query}"
{keyword_instruction} 


**Your Task:**
Generate a single, valid JSON object containing the complete blog post.

**JSON Object Structure:**
- **"title"**: A suspenseful, highly clickable, SEO-optimized title (50-60 characters). It MUST contain the primary keyword. Use techniques like asking a question, creating a knowledge gap (e.g., 'The One Secret About X...'), or using powerful words (e.g., 'Revealed', 'Shocking'). Example: If the topic is 'The History of AI', a good title would be 'AI's Hidden History: The Secret That Changes Everything'.
- **"meta_description"**: 140-155 characters, compelling summary with a call-to-action.
- **"slug"**: A URL-friendly slug.
- **"authorName"**: A plausible expert author name.
- **"authorBio"**: A short, one-sentence author bio.
- **"category"**: MUST BE ONE from this list: {category_list}.
- **"content"**: The full blog post in Markdown format.

**CRITICAL CONTENT REQUIREMENTS:**
- **Length:** Minimum **2500 words required**.
- **Structure & Quality:**
    -   Start with a captivating introduction that includes the primary keyword in the first 100 words.
    -   Include a **"Key Takeaways"** section near the beginning as a bulleted list summarizing the main points.
    -   Use at least 5-7 descriptive H2 (`##`) headings for the main sections.
    -   Use H3 (`###`) subheadings to break down complex topics.
    -   Include **3 to 5** `[IMAGE: A detailed description of the image for AI generation]` placeholders. The description should also serve as perfect alt-text.
    -   End the article with a powerful **Conclusion**.
    -   After the conclusion, add an **"Frequently Asked Questions (FAQ)"** section with 3-5 relevant questions and concise answers about the topic. This is crucial for SEO.
- **Tone:** Expert, authoritative, and trustworthy.
"""


def get_ebook_outline_prompt():
    return """
    You are an expert author and content strategist tasked with outlining a compelling, non-fiction ebook for beginners on a popular topic.

    **Your Task:**
    Generate a complete outline for an ebook. The outline must be logical, starting with an introduction, building through core concepts, and ending with a conclusion.

    You MUST respond with ONLY a valid JSON object with this exact structure:
    {
      "ebook_title": "A highly engaging and marketable title for the book.",
      "subtitle": "A clear, descriptive subtitle.",
      "category": "The single, broad category for all these articles (e.g., Finance, Health, Technology).",
      "chapters": [
        { "title": "Introduction: A hook to draw the reader in" },
        { "title": "Chapter 1: The first core concept" },
        { "title": "Chapter 2: The second core concept" },
        { "title": "Chapter 3: The third core concept" },
        { "title": "Chapter 4: A more advanced concept or case study" },
        { "title": "Conclusion: Summarizing and providing next steps" }
      ]
    }

    Ensure there are exactly 6 chapters, including the introduction and conclusion.
    """