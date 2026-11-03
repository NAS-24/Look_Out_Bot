"""
Look Out - Diff Intelligence Layer
Uses Groq API to evaluate if physical text diffs have semantic meaning.
"""
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
    and logically infers the source's timezone and active window.
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
            model=config.FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"User Request: {user_message}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    except Exception as e:
        print(f"Source Discovery Error: {e}")
        return None


# --- FIRST SCAN INTELLIGENCE (Fixes L-09) ---

def evaluate_first_scan(intent: str, new_text: str) -> dict:
    """
    Evaluates 'Day Zero' scans. Differentiates between 'state' intents (which can be met immediately)
    and 'change' intents (which require a baseline and cannot be met on the first scan).
    """
    try:
        client = get_groq_client()
    except ValueError as e:
        print(e)
        return {"is_meaningful": False, "summary": "", "error": True}

    system_prompt = (
        "You are evaluating the FIRST SCAN of a webpage for a monitoring bot.\n"
        "You must determine if the user's intent is ALREADY MET by the current state of the page.\n\n"
        "CRITICAL RULES:\n"
        "1. 'CHANGE' INTENTS: If the user wants to know when something *changes* (e.g., 'tell me when the price drops', 'watch for new listings'), you CANNOT fulfill this because you have no past baseline. You MUST return is_meaningful: false.\n"
        "2. 'STATE' INTENTS: If the user wants to know if a specific state exists (e.g., 'is registration open?', 'is the item in stock?'), and the page currently shows it IS open or in stock, return is_meaningful: true.\n"
        "3. PRICE RULES: Seeing a crossed-out MRP (Maximum Retail Price) next to a lower selling price is NOT a price drop. It is a standard display. Do not alert on this.\n\n"
        "You MUST respond with a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "is_meaningful": true or false,\n'
        '  "summary": "Explanation if met, else empty.",\n'
        '  "error": false\n'
        "}\n"
    )

    user_content = f"Intent: {intent}\n\n--- PAGE TEXT ---\n{new_text[:6000]}\n"

    try:
        response = client.chat.completions.create(
            model=config.SLOW_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"First Scan Intelligence Error: {e}")
        return {"is_meaningful": False, "summary": "", "error": True}


# --- EXISTING: DIFF INTELLIGENCE (Fixes L-10, L-11) ---

def evaluate_diff(intent: str, old_text: str, new_text: str) -> dict:
    """
    Asks Groq to analyze the difference between old and new text 
    relative to what the user actually wants tracked.
    """
    try:
        client = get_groq_client()
    except ValueError as e:
        print(e)
        # Fix L-10: Explicitly return an error flag so we don't save a bad baseline
        return {"is_meaningful": False, "summary": "", "error": True}

    # Fix L-11: Explicit, strict rules to eliminate noise and false positives
    system_prompt = (
        "You are the core diff intelligence engine for Look Out.\n"
        "Your task is to compare OLD and NEW webpage scrapes and determine if a structurally meaningful change occurred that fulfills the user's intent.\n\n"
        "CRITICAL RULES:\n"
        "1. INTENT FOCUS: Judge ONLY against the user's explicit intent.\n"
        "2. NOISE REJECTION: Ignore visitor counts, timestamps, relative times, upvotes, ratings, or ad text.\n"
        "3. THE VANISHING TARGET (ERRORS): If the core subject of the user's intent (e.g., a tracked price, a stock indicator, a registration status) was clearly present in the OLD text but is suddenly missing, hidden, or unreadable in the NEW text, DO NOT evaluate this as a change. This is a page load failure. You MUST return \"error\": true.\n"
        "4. BROKEN PAGES (ERRORS): If either OLD or NEW resembles an error page (404, CAPTCHA, 'Access Denied') or completely lacks core page structure, return \"error\": true.\n"
        "5. PRICE INTENTS: Compare the final selling price only. Do not confuse crossed-out MRPs or discount percentages with a true price drop.\n"
        "6. AVAILABILITY: 'Notify me', 'Coming soon', or 'Out of stock' changing to 'Buy now', 'Add to cart', or 'Available' is meaningful.\n"
        "7. NEW LISTINGS: An item present in NEW but missing in OLD is meaningful if it matches the intent.\n"
        "8. STATUS: 'Closed' changing to 'Open' or 'Apply now' is meaningful.\n"
        "9. If unsure, default to not meaningful.\n\n"
        "You MUST respond with a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "is_meaningful": true or false,\n'
        '  "summary": "Plain-language summary of what changed and why it matters, or empty string.",\n'
        '  "error": false\n'
        "}\n"
    )

    user_content = (
        f"User Monitoring Intent: {intent}\n\n"
        f"--- OLD WEBPAGE TEXT ELEMENTS ---\n{old_text[:6000]}\n\n"
        f"--- NEW WEBPAGE TEXT ELEMENTS ---\n{new_text[:6000]}\n"
    )

    try:
        response = client.chat.completions.create(
            model=config.SLOW_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"Intelligence Layer Error: {e}")
        # Fix L-10: Safely flag the error
        return {"is_meaningful": False, "summary": "", "error": True}