"""
Look Out - Central Configuration
Stores all application limits, constants, and settings.
"""
import os
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Force load_dotenv to look exactly in this folder for the .env file
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=ENV_PATH)

# 2. Pull the API keys into variables so other files can use them
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Product Constraints ---
# The absolute maximum number of active watches a single user can have at one time.
MAX_ACTIVE_WATCHES_PER_USER = 1

# --- Database ---
# Define the local testing path using your bulletproof BASE_DIR logic
DEFAULT_LOCAL_DB = os.path.join(BASE_DIR, "database", "lookout.db")

# In the cloud, this pulls the DB_PATH environment variable (the Persistent Volume).
# If the variable doesn't exist (like on your laptop), it safely defaults to your local path.
DB_PATH = os.getenv("DB_PATH", DEFAULT_LOCAL_DB)