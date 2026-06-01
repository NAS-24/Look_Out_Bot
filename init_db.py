"""
Look Out - Database Initializer
Wipes the old database and builds a fresh one using schema.sql.
"""
import sqlite3
import os
import sys

# Load our config
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import config

print(f"Targeting database at {config.DB_PATH}")

# 1. Nuke the old, mismatched database
if os.path.exists(config.DB_PATH):
    os.remove(config.DB_PATH)
    print("Deleted old corrupted database file.")

# 2. Read your shiny new schema.sql
schema_path = os.path.join(config.BASE_DIR, 'database', 'schema.sql')
with open(schema_path, 'r') as f:
    schema = f.read()

# 3. Build the fresh database
conn = sqlite3.connect(config.DB_PATH)
conn.executescript(schema)
conn.commit()
conn.close()

print("Success! A pristine, perfectly formatted database has been created.")