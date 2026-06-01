import sqlite3
import os
import sys

# Load our config
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import config

print(f"Connecting to database at {config.DB_PATH}")
conn = sqlite3.connect(config.DB_PATH)
cursor = conn.cursor()

try:
    # Removed the UNIQUE keyword so SQLite allows the injection
    cursor.execute("ALTER TABLE users ADD COLUMN telegram_id INTEGER;")
    conn.commit()
    print("Success! The 'telegram_id' column has been added to your database.")
except sqlite3.OperationalError as e:
    print(f"Operational Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")
finally:
    conn.close()