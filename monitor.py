from pathlib import Path
from dotenv import load_dotenv
import os
import json
import asyncio
from datetime import datetime
import yfinance as yf
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# === Load environment ===
load_dotenv()
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID_FILE = ".chatid"
POSITIONS_FILE = "positions.json"
MONITOR_FLAG_FILE = ".monitor_active"

# === Thresholds ===
UP_THRESHOLD = 3.0
DOWN_THRESHOLD = -2.0

# === Utility: load chat_id from file ===
def get_chat_id():
    if not os.path.exists(CHAT_ID_FILE):
        return None
    with open(CHAT_ID_FILE, "r") as f:
        return f.read().strip()

# === Utility: load positions from JSON ===
def load_positions():
    if not os.path.exists(POSITIONS_FILE):
        return []
    with open(POSITIONS_FILE, "r") as f:
        return json.load(f)

# === Utility: clear positions ===
def clear_positions():
    with open(POSITIONS_FILE, "w") as f:
        f.write("[]")

# === Monitoring loop ===
async def monitor_loop(application):
    while os.path.exists(MONITOR_FLAG_FILE):
        positions = load_positions()
        if not positions:
            await asyncio.sleep(3600)
            continue

        alerts = []
        for p in positions:
            symbol = p["symbol"]
            entry = float(p["entry_price"])
            ticker = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
            try:
                data = yf.Ticker(ticker).history(period="1d", interval="1m")
                current = float(data['Close'][-1])
            except Exception as e:
                print(f"[ERROR] Failed fetching price for {symbol}: {e}")
                continue

            change = ((current - entry) / entry) * 100
            print(f"[DEBUG] {symbol}: Entry ₹{entry:.2f}, Current ₹{current:.2f}, Change {change:.2f}%")

            if change >= UP_THRESHOLD:
                alerts.append(f"📈 {symbol} up {change:.2f}% (₹{current:.2f}) since entry ₹{entry:.2f}")
            elif change <= DOWN_THRESHOLD:
                alerts.append(f"📉 {symbol} down {change:.2f}% (₹{current:.2f}) since entry ₹{entry:.2f}")

        if alerts:
            msg = f"🚨 Position Alerts ({datetime.now().strftime('%H:%M')}):\n\n" + "\n".join(alerts)
            chat_id = get_chat_id()
            if chat_id:
                await application.bot.send_message(chat_id=chat_id, text=msg)
                print("[INFO] Alerts sent!")
        else:
            print("[INFO] No significant movements detected.")

        await asyncio.sleep(3600)  # wait 1 hour

# === /start command ===
async def start_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    with open(CHAT_ID_FILE, "w") as f:
        f.write(chat_id)

    clear_positions()
    Path(MONITOR_FLAG_FILE).touch()
    await update.message.reply_text("📊 Monitoring started. Alerts every 1 hour.")
    asyncio.create_task(monitor_loop(context.application))

# === /stop, /bye, /done command ===
async def stop_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if os.path.exists(MONITOR_FLAG_FILE):
        os.remove(MONITOR_FLAG_FILE)
    await update.message.reply_text("🛑 Monitoring stopped.")

# === Run the Telegram bot ===
app = ApplicationBuilder().token(TG_TOKEN).build()
app.add_handler(CommandHandler("start", start_monitor))
app.add_handler(CommandHandler("stop", stop_monitor))
app.add_handler(CommandHandler("bye", stop_monitor))
app.add_handler(CommandHandler("done", stop_monitor))

print("[DEBUG] Monitor Telegram bot is running...")
app.run_polling()
