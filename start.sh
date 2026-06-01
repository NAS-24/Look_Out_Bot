#!/bin/bash
echo "Starting Look Out Telegram Receptionist..."
python Bot.py &

echo "Starting Look Out Background Engine..."
python main.py