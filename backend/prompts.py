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
Write a high-quality, in-depth, and engaging blog post of at least 800 words on the given topic. The article must be structured for readability and SEO.

**Requirements:**
1.  **Structure:** Use Markdown for formatting. Start with an engaging introduction. Use H2 and H3 headings to create a logical structure. End with a concluding summary.
2.  **Content:** The information must be accurate, well-researched, and provide real value to the reader. Answer the core question of the query thoroughly.
3.  **Tone:** Write in an authoritative, trustworthy, and accessible tone.
4.  **SEO:** Naturally incorporate the main topic keywords throughout the article, especially in the headings.

**Do not include a main title (H1) in your output**, as this will be handled by the "title" metadata. Start directly with the introductory paragraph.
"""


def get_combined_prompt(query):
    return f"""
You are an expert content generation system. Your task is to create a complete, engaging blog post in a structured JSON format.

**User Query:** "{query}"

**Instructions:**
You MUST output a single, valid JSON object and nothing else.

The JSON object must contain these keys:
1.  **"title"**: A highly clickable, SEO-optimized title.
2.  **"meta_description"**: A compelling meta description.
3.  **"slug"**: A URL-friendly slug based on the title.
4.  **"content"**: The full blog post content as a string, formatted with Markdown.

**CRITICAL INSTRUCTION FOR IMAGES:**
Throughout the article, where a visual would be most effective to illustrate a point, you MUST insert a special placeholder.
- The placeholder format is: `[IMAGE: A detailed, photorealistic prompt for an image generation model]`
- **Insert between 2 and 4 of these image placeholders** at natural breaks in the article (e.g., after a section heading).
- The description inside the placeholder should be rich and descriptive, as it will be used to generate the image. For example: `[IMAGE: A wide cinematic shot of the Grand Canyon at sunrise, with golden light hitting the canyon walls]`

**RULES FOR HANDLING QUERIES:**
- If the query is vague, choose a popular sub-topic.
- If the query is inappropriate or unsafe, you MUST return a valid JSON object with a 'title' of "Invalid Topic Request".
"""