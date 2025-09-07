# backend/prompts.py

def get_seo_prompt(query):
    return f"""
You are an world-class SEO expert and copywriter. Your task is to generate perfectly optimized metadata for a blog post based on a user's search query.

**User Query:** "{query}"

**Your Task:**
Generate the following metadata in a JSON format:
1.  **title**: Under 60 characters. Must be highly clickable, contain the primary keyword, and create curiosity.
2.  **meta_description**: Under 155 characters. Summarize the article's content, include the keyword naturally, and end with a compelling call-to-action.
3.  **slug**: A URL-friendly slug. Lowercase, words separated by hyphens, and based on the primary keyword.

**Example Output Format:**
{{
  "title": "Example Title: A Guide to Something",
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


def get_combined_prompt(query):
    """
    This is an advanced prompt designed to generate long-form, high-quality,
    SEO-optimized blog posts.
    """
    return f"""
You are an expert-level content writer and SEO strategist, tasked with creating a comprehensive, in-depth blog post. Your writing style is authoritative, engaging, and easy to understand.

**Primary Keyword/Topic:** "{query}"

**Your Task:**
Generate a single, valid JSON object that contains a complete blog post.

**JSON Object Structure:**
You MUST output a single, valid JSON object with these exact keys:
1.  **"title"**: A highly clickable, SEO-optimized title that is between 50 and 60 characters.
2.  **"meta_description"**: A compelling meta description between 140 and 155 characters.
3.  **"slug"**: A URL-friendly slug based on the title.
4.  **"authorName"**: A plausible and professional-sounding name for an author who is an expert on this topic.
5.  **"authorBio"**: A short, one-sentence biography for this author persona.
6.  **"category"**: The single most relevant category for this article.
7.  **"content"**: The full blog post content as a string, formatted with Markdown.

**CRITICAL CONTENT REQUIREMENTS:**
- **Word Count:** The "content" field MUST be a minimum of **2000 words**.
- **Structure:** The article must be well-structured and logical. It must include:
    - An engaging **Introduction** that hooks the reader and states the article's purpose.
    - At least **5-7 distinct sections**, each with a clear and descriptive H2 (`##`) heading.
    - Where appropriate, use H3 (`###`) subheadings to break down complex points within the main sections.
    - At least **two bulleted or numbered lists** to present information clearly.
    - A thoughtful **Conclusion** that summarizes the key takeaways.
- **Image Placeholders:** You MUST include **3 to 5** `[IMAGE: A detailed prompt...]` placeholders at natural, visually impactful points in the article.
- **Tone & Quality:** Write in an expert, confident, and helpful tone. The information must be accurate, detailed, and provide real value to the reader. Avoid fluff and filler content.
- **SEO:** Naturally incorporate the primary keyword throughout the article, especially in headings and the first 100 words.
- **Originality:** The content must be unique and not plagiarized. Do not copy from existing sources.
- **Formatting:** Use proper Markdown syntax for headings, lists, links, and emphasis. Ensure the content is easy to read and visually appealing.

**RULES FOR HANDLING QUERIES:**
- If the query is vague, choose a popular sub-topic.
"""