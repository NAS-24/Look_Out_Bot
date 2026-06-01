-- Disable foreign key checks temporarily during table creation (standard SQLite practice)
PRAGMA foreign_keys = ON;

-- 1. USERS TABLE: Tracks the delivery endpoints (e.g., Telegram Chat IDs)
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. PROMPTS TABLE: The active (and paused) watches
CREATE TABLE IF NOT EXISTS prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    intent TEXT NOT NULL,          -- What the user actually typed
    target_url TEXT,               -- Discovered by Groq (NULL initially until processed)
    is_active BOOLEAN DEFAULT 1,   -- 1 = True (Watching), 0 = False (Paused/Finished)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- 3. SCRAPE HISTORY TABLE: The Memory Bank (Hash matching happens here)
CREATE TABLE IF NOT EXISTS scrape_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    content_hash TEXT NOT NULL,    -- SHA-256 fingerprint
    sanitized_text TEXT NOT NULL,  -- The actual cleaned text from BeautifulSoup
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts (id) ON DELETE CASCADE
);

-- 4. NOTIFICATION LOG TABLE: Prevents duplicate spamming
CREATE TABLE IF NOT EXISTS notification_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    summary_sent TEXT NOT NULL,    -- The exact text Groq drafted and we sent to the user
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts (id) ON DELETE CASCADE
);