"""
Look Out - Intake Guardrail
Validates user prompts to ensure they are actionable, single-intent monitoring requests.
"""
import os
import json
from groq import Groq
import sys

# Ensure config is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def validate_and_format_intent(user_prompt: str) -> dict:
    """
    Evaluates if a user's request is a valid monitoring task.
    If valid, it extracts the core intent and suggests a search query to find the URL.
    """
    if not config.GROQ_API_KEY:
        print("Error: Groq API key not configured.")
        return {"is_valid": False, "reason": "System offline.", "formatted_intent": "", "suggested_url_search": ""}

    client = Groq(api_key=config.GROQ_API_KEY)

    system_prompt = (
        "You are the intake gatekeeper for Look Out, a background web monitoring daemon. "
        "The user will give you a raw text prompt. You must determine if it is a valid, actionable monitoring request "
        "(e.g., 'watch for flipkart grid registrations', 'let me know when the ps5 is in stock', 'watch this laptop for price changes').\n\n"
        "RULES FOR EVALUATION:\n"
        "1. RELATIVE PRONOUNS ARE VALID: If the user uses terms like 'this laptop', 'this product', 'here', or 'this page', you MUST approve it (is_valid: true). The specific URL context will be provided in a separate step. Do not reject a request just because it lacks a specific product name.\n"
        "2. REJECT CONVERSATIONAL: Reject chat, trivia, or general questions (e.g., 'who is Elon Musk?', 'hello').\n"
        "3. REJECT MULTI-INTENT: The user can only track ONE thing at a time (e.g., 'watch for hackathons AND track stock prices' -> REJECT).\n\n"
        "You MUST respond with a valid JSON object matching this schema exactly:\n"
        "{\n"
        '  "is_valid": true or false,\n'
        '  "reason": "If false, a brief friendly explanation of why to the user. If true, empty string.",\n'
        '  "formatted_intent": "If true, a highly polished, clean version of what to watch for (e.g., \'monitor the target product for price changes\'). If false, empty string.",\n'
        '  "suggested_url_search": "If true, the exact Google search query you would use to find the best official page to monitor for this request. If false, empty string."\n'
        "}"
    )

    try:
        # Using openai/gpt-oss-20b for fast, strict JSON formatting
        response = client.chat.completions.create(
            model=config.FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        result_content = response.choices[0].message.content
        return json.loads(result_content)

    except Exception as e:
        print(f"Guardrail Error: {e}")
        return {"is_valid": False,
                "reason": "I'm having a technical problem right now. Please try again in a few minutes.",
                "formatted_intent": "", "suggested_url_search": ""}