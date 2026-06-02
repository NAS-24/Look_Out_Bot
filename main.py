"""
Look Out - Core Engine Loop (Phase 3 Complete)
Integrates state management, Groq LLM diff evaluation, and Telegram notifications.
"""
import psycopg2
import requests
import config
import time
from database.manager import get_active_prompts, get_latest_hash, save_scrape_history
from scraper.engine import fetch_html
from scraper.cleaner import sanitize_html
from utils.hasher import generate_hash
from intelligence.evaluator import evaluate_diff

def get_previous_text(prompt_id: int) -> str:
    """Helper to fetch the actual raw text from the last scrape event."""
    conn = psycopg2.connect(config.DATABASE_URL)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sanitized_text FROM scrape_history 
        WHERE prompt_id = %s 
        ORDER BY scraped_at DESC LIMIT 1
    """, (prompt_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else ""

def send_telegram_message(chat_id: int, text: str):
    """Pushes the LLM summary directly to the user's phone."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"  -> ERROR: Failed to send Telegram message: {e}")

# --- SCHEDULER CONFIG ---
CHECK_INTERVAL = 3600  # 60 minutes (in seconds)
LOOP_TICK = 10         # How often the daemon wakes up to check the DB (in seconds)
last_checked_times = {} # Memory cache: {prompt_id: timestamp}
# ------------------------

def run_diff_loop():
    active_prompts = get_active_prompts()
    
    if not active_prompts:
        # We fail silently here so we don't spam the terminal with "Sleeping..." every 10 seconds
        return

    current_time = time.time()

    for prompt in active_prompts:
        prompt_id = prompt['id']
        
        # 1. PER-PROMPT SCHEDULING CHECK
        last_check = last_checked_times.get(prompt_id, 0)
        
        # If it has been less than 60 minutes since this specific prompt was checked, skip it.
        if current_time - last_check < CHECK_INTERVAL:
            continue 

        # If we made it here, it's either a brand new prompt, or 60 minutes have passed!
        target_url = prompt['target_url']
        intent = prompt['intent']
        telegram_id = prompt['telegram_id'] 
        
        print(f"\n[Prompt {prompt_id}] Intent: '{intent}'")
        
        # 2. Fetch current content
        raw_html = fetch_html(target_url)
        clean_text = sanitize_html(raw_html)
        
        if not clean_text:
            print("  -> ERROR: Failed to extract text.")
            # Update timer anyway so we don't spam a broken link every 10 seconds
            last_checked_times[prompt_id] = time.time()
            continue
            
        current_hash = generate_hash(clean_text)
        last_hash = get_latest_hash(prompt_id)
        
        # 3. Check physical match
        if last_hash == current_hash:
            print("  -> Result: HASH IDENTICAL. Page structure has not changed.")
            last_checked_times[prompt_id] = time.time() # Reset this prompt's 60-min timer
            continue
            
        # --- UPGRADE 1: THE DAY ZERO SCAN ---
        if last_hash is None:
            print("  -> Result: FIRST RUN. Checking if target information is already present...")
            dummy_old = "This is the very first scan. There is no old text. Just tell me if the NEW text already fulfills the user's intent."
            evaluation = evaluate_diff(intent, dummy_old, clean_text)
            
            if evaluation.get("is_meaningful"):
                print("  -> [!!!] TARGET ALREADY MET ON FIRST SCAN [!!!]")
                summary = evaluation.get('summary')
                
                message_body = (
                    f"🚨 *Look Out Update (Found on Initial Scan!)*\n\n"
                    f"🔗 {target_url}\n\n"
                    f"📝 {summary}\n\n"
                    f"⏸️ *This watch has been auto-paused to free up your limit.*"
                )
                send_telegram_message(telegram_id, message_body)
                
                # Auto-Kill Switch
                conn = psycopg2.connect(config.DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute("UPDATE prompts SET is_active = 0 WHERE id = %s", (prompt_id,))
                conn.commit()
                conn.close()
                print("  -> Watch auto-paused. Removing from active queue.")
                continue # Skip saving hash/timer; mission accomplished!
            else:
                print("  -> Target info not present yet. Establishing baseline memory cache.")
                save_scrape_history(prompt_id, current_hash, clean_text)
                last_checked_times[prompt_id] = time.time() # Reset this prompt's 60-min timer
                continue

        # 4. THE STANDARD DIFF SCAN (Days 1+)
        print("  -> Physical change detected. Fetching previous data for LLM evaluation...")
        old_text = get_previous_text(prompt_id)
        
        print("  -> Sending diff window to Groq API...")
        evaluation = evaluate_diff(intent, old_text, clean_text)
        
        if evaluation.get("is_meaningful"):
            print("  -> [!!!] MEANINGFUL CHANGE CONFIRMED BY LLM [!!!]")
            summary = evaluation.get('summary')
            
            # Push formatted notification to Telegram
            message_body = (
                f"🚨 *Look Out Update*\n\n"
                f"🔗 {target_url}\n\n"
                f"📝 {summary}\n\n"
                f"⏸️ *This watch has been auto-paused to free up your limit.*"
            )
            send_telegram_message(telegram_id, message_body)
            print("  -> Notification pushed to Telegram successfully.")
            
            # --- UPGRADE 2: THE AUTO-KILL SWITCH ---
            conn = psycopg2.connect(config.DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("UPDATE prompts SET is_active = 0 WHERE id = %s", (prompt_id,))
            conn.commit()
            conn.close()
            print("  -> Watch auto-paused. Removing from active queue.")
            continue # Skip saving hash/timer; mission accomplished!
            
        else:
            print("  -> Result: Change categorized as superficial noise by LLM. Staying silent.")
            # It was just noise, so we DO save the new hash to update the baseline memory
            save_scrape_history(prompt_id, current_hash, clean_text)
            print("  -> System state cache updated.")
            last_checked_times[prompt_id] = time.time()

if __name__ == "__main__":
    print("Starting Look Out Daemon Autopilot. Press Ctrl+C to stop.")
    while True:
        try:
            run_diff_loop()
            time.sleep(LOOP_TICK) # Sleep for 10 seconds, NOT 60 minutes!
        except Exception as e:
            print(f"Engine Loop Error: {e}")
            time.sleep(LOOP_TICK) # Keep the loop alive even if a random error occurs