"""
Look Out - Telegram Interface
Handles incoming texts, routes them through the LLM Guardrail, and saves them to the DB.
"""
import sys
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Load local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import config
from intelligence.guard import validate_and_format_intent
from intelligence.evaluator import extract_watch_parameters
from database.manager import (
    check_user_limit, get_or_create_user, add_new_watch, pause_all_user_watches,
    get_user_prompts, resume_prompt, delete_all_user_watches
)

# Define state for the conversation
WAITING_FOR_URL = 1

def trigger_daemon_wake():
    """Creates a local flag file to instantly wake the sleeping daemon."""
    try:
        open("wake_daemon.flag", "w").close()
        print("  -> Wake flag created for the background daemon.")
    except Exception as e:
        print(f"  -> Failed to create wake flag: {e}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers the /start command."""
    await update.message.reply_text(
        "Look Out Daemon is online.\n\n"
        "What do you want me to monitor for you? (e.g., 'Watch for Flipkart GRiD 8.0 registrations')"
    )
    return ConversationHandler.END

async def handle_intent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the raw intent, checks limits, and runs it through Groq."""
    telegram_id = update.message.from_user.id
    raw_text = update.message.text
    
    await update.message.reply_text("Analyzing your request...")
    
    # 1. Database level Guardrail: Check limits
    user_id = get_or_create_user(telegram_id)
    if not check_user_limit(user_id):
        await update.message.reply_text("You have reached your limit of active watches. Please pause one first.")
        return ConversationHandler.END

    # 2. Intelligence level Guardrail: Check intent validity
    eval_result = validate_and_format_intent(raw_text)
    
    if not eval_result.get("is_valid"):
        await update.message.reply_text(f"Request rejected: {eval_result.get('reason')}")
        return ConversationHandler.END

    # 3. Store the clean intent in memory and ask for URL (Human-in-the-Loop)
    clean_intent = eval_result.get("formatted_intent")
    context.user_data['intent'] = clean_intent
    
    await update.message.reply_text(
        f"Intent approved: '{clean_intent}'\n\n"
        f"Since I am in V1 mode, please reply with the exact URL you want me to monitor."
    )
    return WAITING_FOR_URL

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receives the URL from the user, infers the schedule, and locks it into the database."""
    target_url = update.message.text
    intent = context.user_data.get('intent')
    telegram_id = update.message.from_user.id
    
    user_id = get_or_create_user(telegram_id)
    
    await update.message.reply_text("Configuring dynamic active windows based on target URL...")

    # Ask Groq to infer the business hours and timezone for this specific target
    schedule_info = extract_watch_parameters(f"Intent: {intent} URL: {target_url}")
    
    tz = schedule_info.get("source_timezone") if schedule_info else None
    window_start = schedule_info.get("active_window_start") if schedule_info else None
    window_end = schedule_info.get("active_window_end") if schedule_info else None
    
    # Save to database with new timezone parameters
    add_new_watch(user_id, intent, target_url, window_start, window_end, tz)
    
    # WAKE THE DAEMON INSTANTLY
    trigger_daemon_wake()
    
    await update.message.reply_text(
        f"Link verified. I am now actively monitoring this URL for your intent in the background.\n\n"
        f"You can close this chat. I will text you only when something meaningful happens."
    )
    
    # Clear memory and end conversation
    context.user_data.clear()
    return ConversationHandler.END

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Answers the /pause command and stops all active monitoring."""
    telegram_id = update.message.from_user.id
    user_id = get_or_create_user(telegram_id)
    
    pause_all_user_watches(user_id)
    
    await update.message.reply_text(
        "⏸️ All active watches have been paused.\n\n"
        "Your daemon will no longer check those URLs. You are free to start a new watch by sending me a new intent!"
    )

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows the user all their watches and IDs."""
    telegram_id = update.message.from_user.id
    user_id = get_or_create_user(telegram_id)
    prompts = get_user_prompts(user_id)
    
    if not prompts:
        await update.message.reply_text("📭 You have no watches in the database.")
        return
        
    msg = "📋 Your Watches:\n\n"
    for p in prompts:
        status = "🟢 ACTIVE" if p['is_active'] else "⏸️ PAUSED"
        msg += f"ID: {p['id']} | {status}\nIntent: {p['intent']}\nURL: {p['target_url']}\n\n"
        
    msg += "To resume a paused watch, type: /resume <ID>"
    await update.message.reply_text(msg)

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resumes a specific watch by ID and wakes the daemon."""
    telegram_id = update.message.from_user.id
    user_id = get_or_create_user(telegram_id)
    
    if not context.args:
        await update.message.reply_text("⚠️ Please provide the ID. Example: /resume 5\nUse /list to see your IDs.")
        return
        
    try:
        prompt_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("⚠️ The ID must be a number.")
        return

    # THE GUARDRAIL: Enforce the watch limit when resuming
    if not check_user_limit(user_id):
        await update.message.reply_text("🛑 You already have an active watch! Please /pause it before resuming another one.")
        return
        
    success = resume_prompt(user_id, prompt_id)
    if success:
        # WAKE THE DAEMON - A resumed watch needs to be scanned immediately
        trigger_daemon_wake()
        await update.message.reply_text(f"▶️ Watch #{prompt_id} has been resumed and added to the active queue!")
    else:
        await update.message.reply_text("❌ Could not find a watch with that ID belonging to you.")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipes the user's slate clean."""
    telegram_id = update.message.from_user.id
    user_id = get_or_create_user(telegram_id)
    
    delete_all_user_watches(user_id)
    
    await update.message.reply_text("🧹 All your watches and history have been permanently deleted.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Brings up the detailed instruction manual."""
    help_text = (
        "🛠️ *Look Out - Instruction Manual*\n\n"
        "*How to start a new watch:*\n"
        "Just send me a normal text message explaining what you want to look for. "
        "For example: _\"Watch for Unstop hackathon registration to open.\"_\n"
        "I will evaluate your request and then ask you for the URL to monitor.\n\n"
        "*Command Reference:*\n"
        "📋 `/list` - View all your watches (active & paused) and their IDs.\n"
        "⏸️ `/pause` - Pause your currently active watch to free up your limit.\n"
        "▶️ `/resume <ID>` - Reactivate a paused watch (Example: `/resume 3`).\n"
        "🧹 `/clear` - Permanently wipe all your saved watches and history.\n"
        "🆘 `/help` - Show this manual.\n\n"
        "💡 *System Rules:*\n"
        "• You can only have *one* active watch at a time.\n"
        "• The system intelligently calculates monitoring intervals based on the target site's active business hours.\n"
        "• If the system finds a match, it will text you and *auto-pause* the watch to free up your queue."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    if not config.TELEGRAM_BOT_TOKEN:
        print("Error: Telegram token not found in config.")
        return

    # Initialize Bot
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

    # Set up the conversation flow
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_intent)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)]
        },
        fallbacks=[CommandHandler("start", start_command)]
    )

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("list", list_command))    
    app.add_handler(CommandHandler("resume", resume_command)) 
    app.add_handler(CommandHandler("clear", clear_command))  
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)

    print("--- Look Out Telegram Interface Running ---")
    app.run_polling()

if __name__ == "__main__":
    main()