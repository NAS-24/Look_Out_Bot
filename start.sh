#!/bin/bash
echo "Starting Look Out Telegram Receptionist..."
python bot.py &

echo "Starting Look Out Background Engine..."
python main.py