# /utils/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- API Configuration ---
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# --- File Paths ---
PORTFOLIO_FILE = 'simulated_portfolio.pkl'
PRICE_CACHE_FILE = 'price_cache.json'

# --- Trading & Market Data Configuration ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT']
TIMEFRAMES = ['5m', '1h', '4h', '1d']
DATA_LIMIT = 200
CORRELATION_HISTORY_LIMIT = 200

# --- Risk Management Thresholds ---
HIGH_CORRELATION_THRESHOLD = 0.7
MAX_DRAWDOWN_THRESHOLD = 0.20
HARD_STOP_LOSS_THRESHOLD = 0.10

# --- Network Retry Configuration ---
RETRY_ATTEMPTS = 3
RETRY_DELAY_SECONDS = 5