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

def evaluate_diff(intent: str, old_text: str, new_text: str) -> dict:
    """
    Asks Groq to analyze the difference between old and new text 
    relative to what the user actually wants tracked.
    """
    if not config.GROQ_API_KEY:
        print("Error: Groq API key not configured.")
        return {"is_meaningful": False, "summary": ""}

    client = Groq(api_key=config.GROQ_API_KEY)

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
            model="llama-3.3-70b-versatile",
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