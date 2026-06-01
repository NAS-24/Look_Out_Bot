#!/bin/bash
# 1. The fake web server to satisfy Render's free tier health check!
python -m http.server $PORT &

# 2. Boot up your bot and engine normally
echo "Starting Look Out Telegram Receptionist..."
python bot.py &

echo "Starting Look Out Background Engine..."
python main.py