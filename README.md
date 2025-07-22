# NiftyNavigatorAgent

Raw Steps 
# NiftyNavigatorAgent

A Telegram bot (`@NiftyNaviEarnBot`) that recommends and monitors intraday trades on the Indian stock market using free LLMs and data APIs.

## Features
- Parse user input for investible amount and profit target
- Recommend top 5 liquid stocks via an open-source LLM
- Validate stock picks based on ATR and volume
- Hourly price monitoring with real-time alerts
- Pre-close and post-close summary notifications

## Tech Stack
- **Language:** Python 3.10+
- **Bot API:** python-telegram-bot
- **LLM:** Hugging Face Inference (free models)
- **Data:** yfinance or Alpha Vantage free tier
- **CI/CD & Scheduler:** GitHub Actions
- **Storage:** JSON file or SQLite
- **Testing:** pytest

## Prerequisites
- Python 3.10 or higher
- Git
- A Telegram bot token (via BotFather)
- (Optional) Hugging Face & Alpha Vantage API keys for higher rate limits

## Setup

1. **Clone the repo**  
   ```bash
   git clone https://github.com/<your-username>/NiftyNavigatorAgent.git
   cd NiftyNavigatorAgent
