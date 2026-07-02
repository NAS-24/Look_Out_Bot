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
MAX_ACTIVE_WATCHES_PER_USER = 2

# --- Database ---
# The connection string to your PostgreSQL database.
DATABASE_URL = os.getenv("DATABASE_URL")

