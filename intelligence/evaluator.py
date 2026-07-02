import os
import json
from groq import Groq
import sys

# Ensure config is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_groq_client():
    """Helper to initialize the Groq client securely."""
    if not config.GROQ_API_KEY:
        raise ValueError("Error: Groq API key not configured in environment.")
    return Groq(api_key=config.GROQ_API_KEY)

# --- NEW: SOURCE DISCOVERY & SCHEDULING INFERENCE ---

def extract_watch_parameters(user_message: str) -> dict:
    """
    Parses the initial Telegram request to extract the target URL, monitoring intent, 
    and logically infers the source's timezone and active window for the min-heap scheduler.
    """
    try:
        client = get_groq_client()
    except ValueError as e:
        print(e)
        return None

    system_prompt = (
        "You are the Source Discovery module for Look Out, an autonomous intelligence agent. "
        "Your job is to parse a user's monitoring request, extract the target URL and intent, "
        "and infer the target source's operational schedule.\n\n"
        "Rules for Inference:\n"
        "- 'source_timezone': Infer the IANA timezone based on domain (e.g., .in, .gov.in) or context. "
        "If it is an Indian target, use 'Asia/Kolkata'. Default to 'UTC' if entirely ambiguous.\n"
        "- 'active_window_start' & 'active_window_end': Estimate when the humans or systems managing this "
        "specific page are active. Use 24-hour HH:MM:SS format. Standard business portals usually operate "
        "between 09:00:00 and 18:00:00 local time. Always-on domains (e-commerce, global news) might be 00:00:00 to 23:59:59.\n\n"
        "You MUST respond with a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "target_url": "https://...",\n'
        '  "intent": "The specific change the user wants to track",\n'
        '  "source_timezone": "Asia/Kolkata",\n'
        '  "active_window_start": "09:00:00",\n'
        '  "active_window_end": "18:00:00"\n'
        "}\n"
        "Do not include any chat formatting, conversational filler, or text outside the JSON block."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_message}"}
            ],
            temperature=0.1,  # Low temp for reliable JSON adherence and logical constraints
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    except Exception as e:
        print(f"Source Discovery Error: {e}")
        return None


# --- EXISTING: DIFF INTELLIGENCE (Untouched Logic) ---

def evaluate_diff(intent: str, old_text: str, new_text: str) -> dict:
    """
    Asks Groq to analyze the difference between old and new text 
    relative to what the user actually wants tracked.
    """
    try:
        client = get_groq_client()
    except ValueError as e:
        print(e)
        return {"is_meaningful": False, "summary": ""}

    # System instruction enforces strict JSON output and rules out background noise
    system_prompt = (
        "You are the core diff intelligence engine for Look Out, a background daemon.\n"
        "Your task is to compare an older scrape of a webpage against a newer scrape and determine "
        "if any changes are structurally meaningful relative to the user's monitoring request (intent).\n\n"
        "Ignore superficial noise such as shifting visitor counts, timestamps, relative times (e.g., '3 minutes ago'), "
        "upvote numbers, or ad text.\n\n"
        "You MUST respond with a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "is_meaningful": true or false,\n'
        '  "summary": "A friendly, plain-language message summarizing exactly what changed and why it matters to the user, or an empty string if not meaningful."\n'
        "}\n"
        "Do not include any chat formatting, conversational filler, markdown boxes, or text outside the JSON block."
    )

    user_content = (
        f"User Monitoring Intent: {intent}\n\n"
        f"--- OLD WEBPAGE TEXT ELEMENTS ---\n{old_text[:6000]}\n\n"
        f"--- NEW WEBPAGE TEXT ELEMENTS ---\n{new_text[:6000]}\n"
    )

    try:
        # Using llama-3.3-70b-versatile for nuanced structural analysis
        response = client.chat.completions.create(
            model="gpt-oss-20b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,  # Low temperature guarantees deterministic evaluation
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        return json.loads(result_content)

    except Exception as e:
        print(f"Intelligence Layer Error: {e}")
        return {"is_meaningful": False, "summary": ""}