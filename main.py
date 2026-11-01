"""
Look Out - Core Engine Loop (Phase 4.1: Bugfixes & Stability)
Event-driven scheduler that sleeps securely to preserve DB compute.
"""
import psycopg2
import requests
import time
import datetime
import os
import pytz 
import sys

# Ensure config is accessible
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from database.manager import (
    get_due_prompts, get_next_scrape_deadline, update_next_scrape_time, 
    get_latest_hash, save_scrape_history, increment_failure, reset_failure 
)
from scraper.engine import fetch_html
from scraper.cleaner import sanitize_html
from utils.hasher import generate_hash
from intelligence.evaluator import evaluate_diff, evaluate_first_scan

FLAG_FILE = "wake_daemon.flag"

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

def send_telegram_message(chat_id: int, text: str) -> bool:
    """Pushes the LLM summary directly to the user's phone. Returns True if successful."""
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status() # This explicitly checks if Telegram replied with a success code
        return True
    except Exception as e:
        print(f"  -> ERROR: Failed to send Telegram message: {e}")
        return False

def calculate_next_scrape_time(source_timezone, start_time, end_time) -> datetime.datetime:
    """Calculates dynamic intervals based on active business hours."""
    tz_name = source_timezone or 'UTC'
    try:
        tz = pytz.timezone(tz_name)
    except pytz.UnknownTimeZoneError:
        tz = pytz.UTC
        
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_local = now_utc.astimezone(tz)
    current_local_time = now_local.time()
    
    interval_hours = 1 # Default tight polling
    
    if start_time and end_time:
        # Handle conversion if Postgres returned strings instead of datetime.time
        if isinstance(start_time, str):
            start_time = datetime.datetime.strptime(start_time, "%H:%M:%S").time()
        if isinstance(end_time, str):
            end_time = datetime.datetime.strptime(end_time, "%H:%M:%S").time()
            
        # Determine if current time falls within the active window (handling overnight wraps)
        if start_time < end_time:
            is_active = start_time <= current_local_time <= end_time
        else:
            is_active = current_local_time >= start_time or current_local_time <= end_time
            
        # FIX (L-19): 1 hour inside business hours, stretched to 3 hours in the dead zone
        interval_hours = 1 if is_active else 3
        
    # Postgres CURRENT_TIMESTAMP on Neon defaults to UTC. We return naive UTC time for the DB.
    next_scrape = (now_utc + datetime.timedelta(hours=interval_hours)).replace(tzinfo=None)
    return next_scrape

def interruptible_sleep(duration_seconds: float):
    """
    Sleeps for the required time but checks the local disk for a wake flag every 2 seconds.
    This uses ZERO database compute while remaining instantly responsive to Telegram.
    """
    if duration_seconds <= 0:
        return

    print(f"Going into deep sleep for {int(duration_seconds)} seconds...")
    cycles = int(duration_seconds / 2)
    
    for _ in range(max(1, cycles)):
        if os.path.exists(FLAG_FILE):
            print("\n[!] Interrupt flag detected! Waking daemon early to recalculate min-heap.")
            try:
                os.remove(FLAG_FILE)
            except OSError:
                pass
            return # Break sleep early
        time.sleep(2)

def process_prompt(prompt):
    """Handles the scrape, diff, and evaluation for a single active watch."""
    prompt_id = prompt['id']
    target_url = prompt['target_url']
    intent = prompt['intent']
    telegram_id = prompt['telegram_id'] 
    
    print(f"\n[Prompt {prompt_id}] Intent: '{intent}'")
    
    raw_html = fetch_html(target_url)
    clean_text = sanitize_html(raw_html)
    
    if not clean_text:
        print("  -> ERROR: Failed to extract text.")
        
        # CIRCUIT BREAKER LOGIC
        fail_count = increment_failure(prompt_id)
        print(f"  -> Consecutive failures for Watch {prompt_id}: {fail_count}/3")
        
        if fail_count >= 3:
            print("  -> [!!!] CIRCUIT BREAKER TRIPPED. Pausing watch.")
            msg = (f"⚠️ *Look Out Alert*\n\nI couldn't read your target page the last 3 times I checked it. "
                   f"The site might be blocking me or permanently offline.\n\n"
                   f"🔗 {target_url}\n\n⏸️ *I have paused this watch.* Use `/resume {prompt_id}` if you want me to try again later.")
            send_telegram_message(telegram_id, msg)
            
            # Auto-pause it in DB
            conn = psycopg2.connect(config.DATABASE_URL)
            cursor = conn.cursor()
            cursor.execute("UPDATE prompts SET is_active = 0 WHERE id = %s", (prompt_id,))
            conn.commit()
            conn.close()
            
        return # Reschedule anyway so it moves down the queue
        
    
    reset_failure(prompt_id)
        
    current_hash = generate_hash(clean_text)
    last_hash = get_latest_hash(prompt_id)
    
    # 1. Check physical match
    if last_hash == current_hash:
        print("  -> Result: HASH IDENTICAL. Page structure has not changed.")
        return
        
    # 2. THE DAY ZERO SCAN (First Run)
    if last_hash is None:
        print("  -> Result: FIRST RUN. Checking if target information is already present...")
        evaluation = evaluate_first_scan(intent, clean_text)
        
        if evaluation.get("error"):
            print("  -> LLM Error on first scan. Skipping baseline save to retry later.")
            return
        
        if evaluation.get("is_meaningful"):
            print("  -> [!!!] TARGET ALREADY MET ON FIRST SCAN [!!!]")
            summary = evaluation.get('summary')
            
            message_body = (
                f"🚨 *Look Out Update (Found on Initial Scan!)*\n\n🔗 {target_url}\n\n"
                f"📝 {summary}\n\n⏸️ *This watch has been auto-paused.*"
            )
            # send_telegram_message(telegram_id, message_body)

            msg_sent = send_telegram_message(telegram_id, message_body)
            # FIX (L-12): Save the new text so if the user resumes this watch, the baseline is accurate
            save_scrape_history(prompt_id, current_hash, clean_text)
            
            if msg_sent:
                    # Telegram successfully delivered it. Safe to run the Auto-Kill Switch.
                    conn = psycopg2.connect(config.DATABASE_URL)
                    cursor = conn.cursor()
                    cursor.execute("UPDATE prompts SET is_active = 0 WHERE id = %s", (prompt_id,))
                    conn.commit()
                    conn.close()
            else:
                    # Telegram failed! Don't pause it, let the bot try again next cycle.
                    print("  -> Telegram delivery failed! Keeping watch active to retry next cycle.")
                    
            return
        else:
            print("  -> Target info not present yet. Establishing baseline memory cache.")
            save_scrape_history(prompt_id, current_hash, clean_text)
            return

    # 3. THE STANDARD DIFF SCAN
    print("  -> Physical change detected. Fetching previous data for LLM evaluation...")
    old_text = get_previous_text(prompt_id)
    evaluation = evaluate_diff(intent, old_text, clean_text)
    
    if evaluation.get("error"):
        print("  -> LLM Error. Keeping old baseline and retrying later.")
        return
    
    if evaluation.get("is_meaningful"):
        print("  -> [!!!] MEANINGFUL CHANGE CONFIRMED BY LLM [!!!]")
        summary = evaluation.get('summary')
        
        message_body = (
            f"🚨 *Look Out Update*\n\n🔗 {target_url}\n\n📝 {summary}\n\n"
            f"⏸️ *This watch has been auto-paused.*"
        )
        msg_sent=send_telegram_message(telegram_id, message_body)
        
        # FIX (L-12): Save the new text so if the user resumes this watch, the baseline is accurate
        save_scrape_history(prompt_id, current_hash, clean_text)
        
        if msg_sent:
                # Telegram successfully delivered it. Safe to run the Auto-Kill Switch.
                conn = psycopg2.connect(config.DATABASE_URL)
                cursor = conn.cursor()
                cursor.execute("UPDATE prompts SET is_active = 0 WHERE id = %s", (prompt_id,))
                conn.commit()
                conn.close()
        else:
                # Telegram failed! Don't pause it, let the bot try again next cycle.
                print("  -> Telegram delivery failed! Keeping watch active to retry next cycle.")
                
        return
    else:
        print("  -> Result: Change categorized as superficial noise by LLM. Staying silent.")
        save_scrape_history(prompt_id, current_hash, clean_text)

def run_daemon():
    """Main min-heap loop."""
    print("Starting Look Out Daemon Autopilot (Min-Heap Scheduler). Press Ctrl+C to stop.")
    
    while True:
        try:
            # 1. Fetch anything strictly overdue
            due_prompts = get_due_prompts()
            
            # 2. Process all due prompts
            for prompt in due_prompts:
                # FIX (L-08): Wrap process_prompt in a try-except block so a crash in one URL 
                # doesn't break the entire loop and skip the rescheduling step.
                try:
                    process_prompt(prompt)
                except Exception as process_error:
                    print(f"  -> Critical Error processing prompt {prompt['id']}: {process_error}")
                    # We catch it here, print it, and ALLOW the code to continue to step 3!
                
                # 3. Calculate dynamic next interval and update database (GUARANTEED TO RUN NOW)
                next_time = calculate_next_scrape_time(
                    prompt['source_timezone'], 
                    prompt['active_window_start'], 
                    prompt['active_window_end']
                )
                update_next_scrape_time(prompt['id'], next_time)
                print(f"  -> Next scrape scheduled for: {next_time} UTC")

            # 4. Find the absolute soonest deadline across all active prompts
            next_deadline = get_next_scrape_deadline()
            
            if next_deadline is None:
                # Queue is completely empty. Sleep for a long time but wait for Telegram interrupt.
                interruptible_sleep(3600) 
            else:
                now_utc = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
                sleep_seconds = (next_deadline - now_utc).total_seconds()
                
                if sleep_seconds > 0:
                    interruptible_sleep(sleep_seconds)
                else:
                    # If we fell behind, yield briefly before attacking the backlog
                    time.sleep(1)

        except Exception as e:
            print(f"Daemon Loop Error: {e}")
            time.sleep(10) # Fallback sleep to prevent infinite error spamming

if __name__ == "__main__":
    run_daemon()