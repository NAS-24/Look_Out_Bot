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
    # Update Prompt 1 for Google Internships
    cursor.execute("""
        UPDATE prompts 
        SET intent = 'Watch for any new software engineering internship openings or application deadlines',
            target_url = 'https://www.google.com/about/careers/applications/jobs/results/?employment_type=INTERN'
        WHERE id = 1
    """)

    # Clear out the old memory so we start fresh
    cursor.execute("DELETE FROM scrape_history WHERE prompt_id = 1")

    conn.commit()
    print("Prompt updated to Google Careers successfully!")
except Exception as e:
    print(f"An error occurred: {e}")
finally:
    conn.close()
