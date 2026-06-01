import sqlite3
import os
import sys

# Add the parent directory to the path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def init_db():
    """Reads schema.sql and creates the SQLite database tables."""
    print(f"Initializing database at: {config.DB_PATH}")
    
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    
    with open(schema_path, 'r') as f:
        schema_script = f.read()

    # Connect to (and create if missing) the SQLite database
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Execute the SQL script
    cursor.executescript(schema_script)
    
    conn.commit()
    conn.close()
    print("Database schema loaded successfully.")

if __name__ == "__main__":
    # If this file is run directly, initialize the database
    init_db()


def get_active_prompts():
    """Fetches all active watches and their associated user's Telegram ID."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # We join the users table so we can get the correct telegram_id for the text message
    cursor.execute("""
        SELECT prompts.id, prompts.target_url, prompts.intent, users.telegram_id 
        FROM prompts 
        JOIN users ON prompts.user_id = users.id 
        WHERE prompts.is_active = 1
    """)
    rows = cursor.fetchall()
    
    # Convert rows to a list of dictionaries
    prompts = [dict(row) for row in rows]
    conn.close()
    return prompts

def get_latest_hash(prompt_id: int) -> str:
    """Gets the most recent SHA-256 hash for a specific prompt."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Order by scraped_at DESC to get the newest one
    cursor.execute("""
        SELECT content_hash FROM scrape_history 
        WHERE prompt_id = ? 
        ORDER BY scraped_at DESC LIMIT 1
    """, (prompt_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def save_scrape_history(prompt_id: int, content_hash: str, sanitized_text: str):
    """Saves a new scrape event to the memory bank."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO scrape_history (prompt_id, content_hash, sanitized_text)
        VALUES (?, ?, ?)
    """, (prompt_id, content_hash, sanitized_text))
    
    conn.commit()
    conn.close()

def check_user_limit(user_id: int) -> bool:     # GUARDRAIL 1
    """
    Checks if a user has reached their maximum allowed active watches.
    Returns True if they are allowed to add another, False if they are maxed out.
    """
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM prompts WHERE user_id = ? AND is_active = 1", (user_id,))
    active_count = cursor.fetchone()[0]
    
    conn.close()
    
    return active_count < config.MAX_ACTIVE_WATCHES_PER_USER

def get_or_create_user(telegram_id: int) -> int:
    """Ensures the user exists in our database and returns their internal ID."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE telegram_id = ?", (telegram_id,))
    result = cursor.fetchone()
    
    if result:
        user_id = result[0]
    else:
        cursor.execute("INSERT INTO users (telegram_id) VALUES (?)", (telegram_id,))
        user_id = cursor.lastrowid
        
    conn.commit()
    conn.close()
    return user_id

def add_new_watch(user_id: int, intent: str, target_url: str):
    """Inserts a new active watch into the database."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO prompts (user_id, intent, target_url, is_active)
        VALUES (?, ?, ?, 1)
    """, (user_id, intent, target_url))
    
    conn.commit()
    conn.close()

def pause_all_user_watches(user_id: int):
    """Sets is_active to 0 for all of a user's watches."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE prompts SET is_active = 0 WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()

def get_user_prompts(user_id: int):
    """Fetches all prompts (active and paused) for a specific user."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, intent, target_url, is_active 
        FROM prompts WHERE user_id = ?
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def resume_prompt(user_id: int, prompt_id: int) -> bool:
    """Sets a specific watch to active. Returns True if successful."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE prompts SET is_active = 1 
        WHERE id = ? AND user_id = ?
    """, (prompt_id, user_id))
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_affected > 0

def delete_all_user_watches(user_id: int):
    """Permanently deletes all of a user's watches."""
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()
    
    # Optional but good practice: clear the history related to these prompts first
    cursor.execute("""
        DELETE FROM scrape_history 
        WHERE prompt_id IN (SELECT id FROM prompts WHERE user_id = ?)
    """, (user_id,))
    
    cursor.execute("DELETE FROM prompts WHERE user_id = ?", (user_id,))
    
    conn.commit()
    conn.close()