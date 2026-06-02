import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys

# Add the parent directory to the path so we can import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

def get_connection():
    """Establishes a connection to the PostgreSQL database."""
    if not config.DATABASE_URL:
        raise ValueError("DATABASE_URL is not set in config/environment!")
    return psycopg2.connect(config.DATABASE_URL)

def init_db():
    """Creates the tables if they don't exist. Uses Postgres syntax."""
    print("Initializing PostgreSQL database...")
    conn = get_connection()
    cursor = conn.cursor()
    
    # We write the Postgres schema directly here so you can delete schema.sql!
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prompts (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            intent TEXT NOT NULL,
            target_url TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_history (
            id SERIAL PRIMARY KEY,
            prompt_id INTEGER REFERENCES prompts(id) ON DELETE CASCADE,
            content_hash TEXT NOT NULL,
            sanitized_text TEXT NOT NULL,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    conn.commit()
    conn.close()
    print("Database schema loaded successfully.")


def get_active_prompts():
    """Fetches all active watches and their associated user's Telegram ID."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT prompts.id, prompts.target_url, prompts.intent, users.telegram_id 
        FROM prompts 
        JOIN users ON prompts.user_id = users.id 
        WHERE prompts.is_active = 1
    """)
    rows = cursor.fetchall()
    
    conn.close()
    return [dict(row) for row in rows]

def get_latest_hash(prompt_id: int) -> str:
    """Gets the most recent SHA-256 hash for a specific prompt."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT content_hash FROM scrape_history 
        WHERE prompt_id = %s 
        ORDER BY scraped_at DESC LIMIT 1
    """, (prompt_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

def save_scrape_history(prompt_id: int, content_hash: str, sanitized_text: str):
    """Saves a new scrape event to the memory bank."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO scrape_history (prompt_id, content_hash, sanitized_text)
        VALUES (%s, %s, %s)
    """, (prompt_id, content_hash, sanitized_text))
    
    conn.commit()
    conn.close()

def check_user_limit(user_id: int) -> bool:     
    """Checks if a user has reached their maximum allowed active watches."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM prompts WHERE user_id = %s AND is_active = 1", (user_id,))
    active_count = cursor.fetchone()[0]
    
    conn.close()
    
    return active_count < config.MAX_ACTIVE_WATCHES_PER_USER

def get_or_create_user(telegram_id: int) -> int:
    """Ensures the user exists in our database and returns their internal ID."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
    user = cursor.fetchone()
    
    if user:
        user_id = user['id']
    else:
        # Postgres uses RETURNING id to instantly give back the generated ID
        cursor.execute(
            "INSERT INTO users (telegram_id) VALUES (%s) RETURNING id", 
            (telegram_id,)
        )
        user_id = cursor.fetchone()['id']
        
    conn.commit()
    conn.close()
    return user_id

def add_new_watch(user_id: int, intent: str, target_url: str):
    """Inserts a new active watch into the database."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO prompts (user_id, intent, target_url, is_active)
        VALUES (%s, %s, %s, 1)
    """, (user_id, intent, target_url))
    
    conn.commit()
    conn.close()

def pause_all_user_watches(user_id: int):
    """Sets is_active to 0 for all of a user's watches."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("UPDATE prompts SET is_active = 0 WHERE user_id = %s", (user_id,))
    
    conn.commit()
    conn.close()

def get_user_prompts(user_id: int):
    """Fetches all prompts (active and paused) for a specific user."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT id, intent, target_url, is_active 
        FROM prompts WHERE user_id = %s ORDER BY id ASC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def resume_prompt(user_id: int, prompt_id: int) -> bool:
    """Sets a specific watch to active. Returns True if successful."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE prompts SET is_active = 1 
        WHERE id = %s AND user_id = %s
    """, (prompt_id, user_id))
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_affected > 0

def delete_all_user_watches(user_id: int):
    """Permanently deletes all of a user's watches."""
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        DELETE FROM scrape_history 
        WHERE prompt_id IN (SELECT id FROM prompts WHERE user_id = %s)
    """, (user_id,))
    
    cursor.execute("DELETE FROM prompts WHERE user_id = %s", (user_id,))
    
    conn.commit()
    conn.close()

# --- MISSING FUNCTION ADDED FOR MAIN.PY ---
def get_previous_text(prompt_id: int):
    """Fetches the last sanitized text to send to Groq for diffing."""
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        SELECT sanitized_text FROM scrape_history 
        WHERE prompt_id = %s 
        ORDER BY scraped_at DESC LIMIT 1
    """, (prompt_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return row['sanitized_text']
    return ""

if __name__ == "__main__":
    init_db()