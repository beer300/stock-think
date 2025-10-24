# /utils/error_handler.py
import time
import ccxt
from functools import wraps
from . import config

def retry_on_exception(func):
    """
    A decorator to retry a function call on network-related exceptions.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        attempts = 0
        while attempts < config.RETRY_ATTEMPTS:
            try:
                return func(*args, **kwargs)
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable, ccxt.RequestTimeout) as e:
                attempts += 1
                print(f"Network error in {func.__name__}: {e}. Attempt {attempts}/{config.RETRY_ATTEMPTS}. Retrying in {config.RETRY_DELAY_SECONDS}s...")
                time.sleep(config.RETRY_DELAY_SECONDS)
        
        print(f"Function {func.__name__} failed after {config.RETRY_ATTEMPTS} attempts.")
        return None # Or raise a final exception
    return wrapper