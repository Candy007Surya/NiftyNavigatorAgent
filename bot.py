# bot.py
# Setup:
# 1. python3 -m venv venv
# 2. Activate: PowerShell: .\venv\Scripts\Activate.ps1
# 3. Install: pip install python-telegram-bot python-dotenv requests
# 4. Create .env with:
#      TELEGRAM_BOT_TOKEN="<your-telegram-token>"
#      HF_API_TOKEN="<your-huggingface-token>"
# 5. Run: python bot.py

# Stock Advisory Telegram Bot: NiftyNavigator

import os
import re
import json
from datetime import datetime
import requests
import yfinance as yf
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# === Load Environment Variables ===
load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "mistralai/mistral-7b-instruct"

# Debug: confirm credentials & model
print(f"[DEBUG] Telegram token loaded: {bool(TG_TOKEN)}")
print(f"[DEBUG] OpenRouter key loaded: {bool(OPENROUTER_KEY)}")
print(f"[DEBUG] Model for Agent #1 & #2: {MODEL_NAME}")

if not TG_TOKEN or not OPENROUTER_KEY:
    print("ERROR: Missing TELEGRAM_BOT_TOKEN or OPENROUTER_API_KEY in .env")
    exit(1)

# === Storage Helpers ===
# load_positions: reads saved buy positions from positions.json
POS_FILE = os.path.join(os.path.dirname(__file__), 'positions.json')

def load_positions():
    if not os.path.exists(POS_FILE):
        return []
    with open(POS_FILE, 'r') as f:
        return json.load(f)

# save_positions: writes current positions list to positions.json
def save_positions(positions):
    with open(POS_FILE, 'w') as f:
        json.dump(positions, f, indent=2)

# add_position: appends a new buy position to storage
def add_position(symbol: str, price: float):
    positions = load_positions()
    positions.append({
        "symbol": symbol,
        "entry_price": price,
        "timestamp": datetime.utcnow().isoformat()
    })
    save_positions(positions)

# === Input Parsing ===
# parse_input: extracts investible amount and target percent from user text
async def parse_input(text: str):
    pattern = r"₹\s*([\d,]+)\s*@\s*(\d+(?:\.\d+)?)%"
    match = re.search(pattern, text)
    if not match:
        return None, None
    amount = int(match.group(1).replace(',', ''))
    percent = float(match.group(2))
    return amount, percent

# === Agent Call ===
# fetch_recommendations: calls OpenRouter for a given prompt (used for both Agent #1 & #2)
async def fetch_recommendations(prompt: str) -> str:
    print(f"[DEBUG] Agent calling model: {MODEL_NAME}")  # log model use
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openrouter.ai"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    return data['choices'][0]['message']['content']

# === Bot Command Handlers ===
# start: sends a welcome message explaining usage
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("[DEBUG] /start invoked")
    await update.message.reply_text(
        "👋 Welcome to NiftyNavigator!\n" 
        "Send: ₹<amount> @ <percent>% (e.g., ₹20000 @ 3%)"
    )

# help_command: shows help instructions
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("[DEBUG] /help invoked")
    await update.message.reply_text(
        "Format: ₹<amount> @ <percent>% (e.g., ₹20000 @ 3%).\n" 
        "I'll recommend 5 liquid NSE/BSE stocks intraday."
    )

# buy_handler: handles "I buy SYMBOL" messages, records entry price
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    print(f"[DEBUG] buy_handler received: {text}")
    pattern = re.compile(r"^I buy\s+([A-Za-z\.]+)$", re.IGNORECASE)
    m = pattern.match(text)
    if not m:
        return
    symbol = m.group(1).upper()
    ticker = symbol if symbol.endswith('.NS') else f"{symbol}.NS"
    try:
        data = yf.Ticker(ticker).history(period="1d", interval="1m")
        entry_price = float(data['Close'].iloc[-1])
        print(f"[DEBUG] fetched price for {symbol}: {entry_price}")
    except Exception as e:
        print(f"[ERROR] Failed fetching price for {symbol}: {e}")
        await update.message.reply_text(
            f"⚠️ Couldn't fetch price for {symbol}. Check symbol and try again."
        )
        return
    add_position(symbol, entry_price)
    await update.message.reply_text(
        f"✅ Recorded {symbol} at ₹{entry_price:.2f}. I'll watch this position!"
    )

# handle_message: main logic for investment prompt and two-agent flow
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    # Skip “I buy SYMBOL” commands here
    if re.match(r"^I buy\s+[A-Za-z\.]+$", text, re.IGNORECASE):
        return

    # Parse amount and percent
    amount, percent = await parse_input(text)
    if amount is None:
        await update.message.reply_text("❌ Couldn't parse input. Use: ₹<amount> @ <percent>%")
        return

    # Acknowledge receipt
    await update.message.reply_text(
        f"✅ Received: ₹{amount}, target: {percent}%\nFetching top 5 picks..."
    )

    # Agent #1: recommendation prompt
    prompt = (
        f"Recommend 5 highly liquid NSE/BSE stocks for investing ₹{amount} "
        f"with a goal of {percent}% intraday profit. Provide a brief rationale for each."
    )

    try:
        # 1️⃣ Call Agent #1 to get raw picks
        picks = await fetch_recommendations(prompt)

        # Format the picks list
        lines = [l.strip() for l in picks.splitlines() if l.strip()]
        numbered = "\n".join(f"{i+1}. {lines[i]}" for i in range(len(lines)))
        top_pick = lines[0].split("–")[0].strip()
        symbols = ", ".join(ln.split("–")[0].strip() for ln in lines)

        # Build base of final message
        final_msg = f"📈 5 picks for ₹{amount} @ {percent}%:\n{numbered}\n\n"

        # Agent #2: minimal validation prompt
        validation_prompt = (
            f"Symbols: {symbols}. Can each plausibly hit {percent}% intraday profit? Yes or No."
        )
        print(f"[DEBUG] Agent #2 minimal prompt: {validation_prompt}")

        # 2️⃣ Attempt Agent #2, but guard against length errors
        try:
            validation = await fetch_recommendations(validation_prompt)
            print(f"[DEBUG] Validation response: {validation!r}")
            # Only take first few lines to avoid huge messages
            val_lines = [l.strip() for l in validation.splitlines()][:5]
            bullets = "\n".join(f"• {l}" for l in val_lines)
            final_msg += f"🔍 Sanity check:\n{bullets}\n\n"
        except Exception as ve:
            print(f"[WARN] Validation skipped: {ve}")
            final_msg += "🔍 Sanity check: skipped (service limit)\n\n"

        # ⭐️ Append top suggestion
        final_msg += f"⭐️ Top suggestion: {top_pick}"

        # Send the combined reply
        await update.message.reply_text(final_msg)

    except Exception as e:
        print(f"[ERROR] fetch_recommendations failed: {e}")
        await update.message.reply_text(
            "⚠️ Sorry, couldn’t fetch recommendations. Try again later."
        )

# Handle /id command to get your Telegram chat ID
async def chat_id_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    await update.message.reply_text(f"🆔 Your Telegram chat ID is:\n`{chat_id}`", parse_mode='Markdown')
    print(f"[DEBUG] Telegram chat ID: {chat_id}")

# === Bot Setup ===
if __name__ == "__main__":
    app = ApplicationBuilder().token(TG_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Regex(re.compile(r"^I buy\s+[A-Za-z\.]+$", re.IGNORECASE)), buy_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CommandHandler("id", chat_id_handler))
    print("🤖 NiftyNavigator is starting...")
    app.run_polling()