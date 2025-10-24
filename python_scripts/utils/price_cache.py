# /utils/price_cache.py
import json
from . import config

def load_price_cache():
    """Loads the last known prices from a JSON file."""
    try:
        with open(config.PRICE_CACHE_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_price_cache(prices):
    """Saves the current prices to a JSON file."""
    with open(config.PRICE_CACHE_FILE, 'w') as f:
        json.dump(prices, f, indent=4)