import os
from openai import OpenAI
import logging

logger = logging.getLogger(__name__)

import random
from duckduckgo_search import DDGS

def draft_email_with_deepseek(company_name: str, website_text: str, is_follow_up: bool = False, original_email_text: str = "", campaign_name: str = None) -> tuple[str, str, str]:
    """
    Uses DeepSeek V4 Pro to draft a personalized cold email pitching AI automation services.
    Returns a tuple containing: (subject, body, campaign_used).
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        return "", "", ""
        
    client = OpenAI(
        api_key=api_key, 
        base_url="https://api.deepseek.com/v1"
    )
    
    # 1. Fetch recent news via DuckDuckGo
    recent_news = ""
    try:
        results = DDGS().text(f"{company_name} recent news OR announcement", max_results=2)
        if results:
            news_snippets = [f"- {r['title']}: {r['body']}" for r in results]
            recent_news = "Recent News/Updates about the company found via search:\n" + "\n".join(news_snippets) + "\n\nUse this information to write a highly personalized icebreaker if relevant."
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed for {company_name}: {e}")

    # 2. Load custom instructions from config file & handle A/B Campaigns
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent_config.json")
    custom_instructions = ""
    used_campaign = campaign_name or "Default"
    
    if os.path.exists(config_path):
        try:
            import json
            with open(config_path, "r") as f:
                config_data = json.load(f)
                
                # Check if it's the multi-campaign format (dict of dicts)
                if isinstance(config_data, dict) and any(isinstance(v, dict) for v in config_data.values()):
                    if campaign_name and campaign_name in config_data:
                        config = config_data[campaign_name]
                        used_campaign = campaign_name
                    else:
                        # Randomly pick a campaign for A/B testing
                        used_campaign = random.choice(list(config_data.keys()))
                        config = config_data[used_campaign]
                else:
                    config = config_data # Old format
                    
                sender_name = config.get("sender_name", "").strip()
                tone = config.get("tone", "").strip()
                value_prop = config.get("value_proposition", "").strip()
                extra = config.get("extra_instructions", "").strip()
                
                custom_instructions_parts = []
                if sender_name:
                    custom_instructions_parts.append(f"- Sign off the email as: Regards, {sender_name}")
                if tone:
                    custom_instructions_parts.append(f"- Tone and Style: {tone}")
                if value_prop:
                    custom_instructions_parts.append(f"- Core Value Proposition to focus on: {value_prop}")
                if extra:
                    custom_instructions_parts.append(f"- Additional Rules: {extra}")
                
                if custom_instructions_parts:
                    custom_instructions = (
                        "CRITICAL USER INSTRUCTIONS (THESE OVERRIDE ALL OTHER RULES):\n" 
                        + "\n".join(custom_instructions_parts) 
                        + "\n\n"
                    )
        except Exception as e:
            logger.error(f"Failed to load agent_config.json: {e}")

    if is_follow_up:
        original_context = f"\nHere is the previous email you sent them for context:\n{original_email_text}\n" if original_email_text else ""
        prompt = f"""
You are an expert sales representative for an AI agency.
Your goal is to pitch services to a company named '{company_name}'. You have previously sent them an initial cold email and are now writing a short, polite follow-up.
{original_context}
Based on the following scraped text from their website, write a highly personalized follow-up cold email.

{recent_news}

{custom_instructions}
STRICT DEFAULT RULES:
1. Short and Concise: This is a follow-up, so keep it extremely brief (2-3 sentences max). Politely reference that you previously reached out.
2. Greeting: Always use a proper greeting (e.g., 'Hi Team' or 'Hi [Company Name]'). Never use bracketed placeholders like [Name].
3. Email Structure & Flow:
   - Ask if they saw the previous email or politely bump the conversation.
   - Reiterate one key value proposition tailored to their business based on their website text. Make sure to mention it will save time, cash, and help the business grow revenue.
   - Signal Credibility: Briefly show our company's credibility.
4. Consistent Signature & Branding: Always include both websites at the bottom of the signature block:
   Company: https://weautomate.sonictch.com
   Personal: https://erfanhassan.sonictch.com
   No AI disclaimers.
5. Prefix Subject: Start the subject line with "Re: " followed by a brief relevant subject to indicate it's a follow-up.
6. Formatting: Do NOT use any HTML tags, <br>, or markdown formatting. Write in pure plain text only.

Website Text Summary:
{website_text[:3000]}

Return the response in the exact following format, with no extra text:
SUBJECT: Your Subject Line
BODY: Your Email Body in plain text
"""
    else:
        prompt = f"""
You are an expert sales representative for an AI agency.
Your goal is to pitch services to a company named '{company_name}'.

Based on the following scraped text from their website, write a highly personalized cold email.

{custom_instructions}
STRICT DEFAULT RULES (NON-NEGOTIABLE):
1. Greeting: You MUST start with a proper greeting (e.g., "Hi Team" or "Hi [Company Name]").
2. Length & Scannability: The email MUST be under 150 words and instantly scannable for enterprise executives on phones.
3. The Subject Line: Keep it to 2–4 words. Make it look like an internal memo.
4. Structure (Problem -> AI Solution): First, mention a specific problem or bottleneck they likely face based on their website. Then, explain the solution we can provide through AI in very simple language.
5. The Value Hypothesis: You MUST explicitly mention that our AI solutions will save them time, save cash, and help their business grow revenue.
6. The Credibility Marker: Prove technical depth to handle enterprise risk. Lean on engineering chops. Mention building, deploying, and scaling complex AI systems handling clinical work for thousands of active professional users (like Ava).
7. The Soft CTA: NEVER ask for a 15-minute or 30-minute call in a first email. Ask for interest (e.g., "Open to a brief overview of how this would look for [Company]?").
8. Zero AI Buzzwords: Do not mention "ChatGPT" or specific LLMs. Focus on outcomes.
9. Formatting & Links: Do NOT use any HTML tags, <br>, or markdown formatting. Write in pure plain text only. Always include the websites at the bottom of the signature block:
   Company: https://weautomate.sonictch.com
   Personal: https://erfanhassan.sonictch.com

Website Text Summary:
{website_text[:3000]}

{recent_news}

Return the response in the exact following format, with no extra text:
SUBJECT: Your Subject Line
BODY: Your Email Body in plain text
"""
    
    try:
        # DeepSeek currently uses 'deepseek-chat' as the model name for V3/V4
        response = client.chat.completions.create(
            model="deepseek-v4-pro", 
            messages=[
                {"role": "system", "content": "You are a professional B2B cold outreach expert."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.7
        )
        
        content = response.choices[0].message.content.strip()
        
        # Parse the subject and body from the specific format requested
        subject = ""
        body = ""
        
        if "SUBJECT:" in content and "BODY:" in content:
            parts = content.split("BODY:")
            subject = parts[0].replace("SUBJECT:", "").strip()
            body = parts[1].strip()
        else:
            # Fallback parsing if the model diverges slightly from the format
            lines = content.split("\n")
            if len(lines) >= 2:
                subject = lines[0].replace("Subject:", "").replace("SUBJECT:", "").strip()
                body = "\n".join(lines[1:]).strip()
            else:
                body = content
                
        return subject, body, used_campaign
        
    except Exception as e:
        logger.error(f"Error calling DeepSeek API: {e}")
        return "", "", ""

import json

def parse_natural_language_command(user_prompt: str) -> dict:
    """
    Uses DeepSeek to classify a natural language command into an actionable intent.
    Returns a dictionary with 'action' (e.g., 'draft', 'send', 'add_lead', 'update_status', 'delete_lead', 'delete_by_status', 'clear_all', 'unknown') 
    and optional parameters like 'limit', 'company', 'website', 'status'.
    """
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        logger.error("DEEPSEEK_API_KEY is not set.")
        return {"action": "unknown", "limit": 0}
        
    client = OpenAI(
        api_key=api_key, 
        base_url="https://api.deepseek.com/v1"
    )
    
    prompt = f"""
You are an intelligent routing assistant for a cold email automation dashboard.
The user will give you a natural language command. You need to map it to one of the following actions:
1. "draft": If the user wants to bulk draft emails for new leads. Extract 'limit' (default 5).
2. "interactive_draft": If the user wants to draft an email for a specific single company right now (e.g. "Draft an email for Apple at apple.com"). Extract 'company' and 'website'.
3. "send": If the user wants to send approved emails. Extract 'limit' (default 5).
4. "delete_by_status": If the user wants to delete leads with a specific status. Extract 'status' (e.g., "Rejected", "Pending Review").
5. "add_lead": If the user wants to add a new lead. Extract 'company' and 'website'.
6. "update_status": If the user wants to update a lead's status. Extract 'company' and 'status' (e.g., "Approved", "Rejected").
7. "delete_lead": If the user wants to delete a specific lead by name. Extract 'company'.
8. "clear_all": If the user wants to clear or delete all leads from the sheet.
9. "unknown": If the command doesn't match the above.

Respond ONLY with a valid JSON object. No markdown formatting, no backticks.
Format: {{"action": "action_name", "limit": int, "company": "str", "website": "str", "status": "str"}}
(Include only the fields relevant to the action)

User Command: "{user_prompt}"
"""
    
    try:
        response = client.chat.completions.create(
            model="deepseek-v4-pro", 
            messages=[
                {"role": "system", "content": "You are a JSON-only API router."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=150,
            temperature=0.1
        )
        
        content = response.choices[0].message.content.strip()
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()
            
        return json.loads(content)
        
    except Exception as e:
        logger.error(f"Error parsing command: {e}")
        return {"action": "unknown", "limit": 0}

