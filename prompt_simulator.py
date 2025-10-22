import ccxt
import pandas as pd
import ta
import datetime
import time
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
# List of cryptocurrency symbols to fetch data for (Binance spot market format)
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT']  # Same symbols work for spot market
# The intraday timeframe for the primary series of indicators
INTRADAY_TIMEFRAME = '3m'
# The longer-term timeframe for context
LONG_TERM_TIMEFRAME = '4h'
# Number of recent candles to fetch for calculations
DATA_LIMIT = 100 # Fetch enough data for indicator calculations

# --- SIMULATION STATE (persists between runs) ---
# These variables simulate the bot's lifecycle
start_time = datetime.datetime.now()
invocation_count = 0

class SimulatedPortfolio:
    """A class to simulate a trading account and its positions."""
    def __init__(self):
        self.initial_cash = 10000
        self.available_cash = 4927.64 # From your example
        self.positions = {
            # Example positions matching your prompt. You can modify these.
            'ETH': {'quantity': 4.87, 'entry_price': 3844.03, 'leverage': 15},
            'SOL': {'quantity': 81.81, 'entry_price': 182.8, 'leverage': 15},
            'XRP': {'quantity': 3542.0, 'entry_price': 2.47, 'leverage': 10},
            'BTC': {'quantity': 0.12, 'entry_price': 107343.0, 'leverage': 10},
            'DOGE': {'quantity': 27858.0, 'entry_price': 0.18, 'leverage': 10},
            'BNB': {'quantity': 9.39, 'entry_price': 1073.69, 'leverage': 10},
        }
        self.sharpe_ratio = 0.01

    def get_account_details(self, current_prices):
        """Calculates and returns the current state of the account."""
        total_pnl = 0
        total_position_value = 0
        live_positions_info = []

        for symbol_base, pos in self.positions.items():
            symbol_pair = f"{symbol_base}/USDT"
            current_price = current_prices.get(symbol_pair, pos['entry_price'])
            
            unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']
            notional_usd = current_price * pos['quantity']
            
            total_pnl += unrealized_pnl
            total_position_value += notional_usd
            
            # This data is static in the example, but could be dynamic
            pos_info = {
                'symbol': symbol_base, 'quantity': pos['quantity'], 'entry_price': pos['entry_price'],
                'current_price': round(current_price, 5), 'unrealized_pnl': round(unrealized_pnl, 2),
                'leverage': pos['leverage'], 'notional_usd': round(notional_usd, 2)
                # Add other static details from your prompt if needed
            }
            live_positions_info.append(pos_info)

        account_value = self.available_cash + total_pnl # Simplified for this example
        total_return = ((account_value / self.initial_cash) - 1) * 100

        return {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": self.available_cash,
            "Current Account Value": round(account_value, 2),
            "Current live positions & performance": live_positions_info,
            "Sharpe Ratio": self.sharpe_ratio
        }

# Initialize our simulated account
portfolio = SimulatedPortfolio()

def get_market_data(binance, symbol):
    """Fetches and calculates all necessary market data for a single symbol."""
    try:
        # --- Fetch Data ---
        # Get the latest ticker for the current price
        ticker = binance.fetch_ticker(symbol)
        current_price = ticker['last'] if ticker else None
        if not current_price:
            print(f"Could not fetch ticker for {symbol}")
            return None

        # Get intraday and long-term klines
        intraday_ohlcv = binance.fetch_ohlcv(symbol, timeframe=INTRADAY_TIMEFRAME, limit=DATA_LIMIT)
        long_term_ohlcv = binance.fetch_ohlcv(symbol, timeframe=LONG_TERM_TIMEFRAME, limit=DATA_LIMIT)

        # --- Process Data into Pandas DataFrame ---
        intraday_df = pd.DataFrame(intraday_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        long_term_df = pd.DataFrame(long_term_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # Use the 'close' price for calculations as the mid-price
        intraday_df['mid_price'] = intraday_df['close']

        # --- Calculate Indicators ---
        # Intraday Indicators
        intraday_df['EMA_20'] = ta.trend.ema_indicator(intraday_df['close'], window=20)
        macd_intra = ta.trend.MACD(intraday_df['close'], window_fast=12, window_slow=26, window_sign=9)
        intraday_df['MACDh_12_26_9'] = macd_intra.macd_diff()
        intraday_df['RSI_7'] = ta.momentum.rsi(intraday_df['close'], window=7)
        intraday_df['RSI_14'] = ta.momentum.rsi(intraday_df['close'], window=14)

        # Long-term Indicators
        long_term_df['EMA_20'] = ta.trend.ema_indicator(long_term_df['close'], window=20)
        long_term_df['EMA_50'] = ta.trend.ema_indicator(long_term_df['close'], window=50)
        long_term_df['ATRr_3'] = ta.volatility.average_true_range(long_term_df['high'], long_term_df['low'], long_term_df['close'], window=3)
        long_term_df['ATRr_14'] = ta.volatility.average_true_range(long_term_df['high'], long_term_df['low'], long_term_df['close'], window=14)
        macd_lt = ta.trend.MACD(long_term_df['close'], window_fast=12, window_slow=26, window_sign=9)
        long_term_df['MACDh_12_26_9'] = macd_lt.macd_diff()
        long_term_df['RSI_14'] = ta.momentum.rsi(long_term_df['close'], window=14)

        # --- Format Output ---
        # Select the last 10 data points for the prompt
        latest_intraday = intraday_df.tail(10).round(5)
        latest_long_term = long_term_df.tail(10).round(5)

        # Process latest data points
        latest_intraday = intraday_df.tail(10).round(5)
        latest_long_term = long_term_df.tail(10).round(5)

        return {
            "current_price": current_price,
            "current_ema20": latest_intraday['EMA_20'].iloc[-1],
            "current_macd": latest_intraday['MACDh_12_26_9'].iloc[-1],
            "current_rsi_7": latest_intraday['RSI_7'].iloc[-1],
            "intraday_mid_prices": latest_intraday['mid_price'].tolist(),
            "intraday_ema20": latest_intraday['EMA_20'].tolist(),
            "intraday_macd": latest_intraday['MACDh_12_26_9'].tolist(),
            "intraday_rsi_7": latest_intraday['RSI_7'].tolist(),
            "intraday_rsi_14": latest_intraday['RSI_14'].tolist(),
            "long_term_ema20": latest_long_term['EMA_20'].iloc[-1],
            "long_term_ema50": latest_long_term['EMA_50'].iloc[-1],
            "long_term_atr3": latest_long_term['ATRr_3'].iloc[-1],
            "long_term_atr14": latest_long_term['ATRr_14'].iloc[-1],
            "long_term_volume_current": latest_long_term['volume'].iloc[-1],
            "long_term_volume_average": latest_long_term['volume'].mean(),
            "long_term_macd": latest_long_term['MACDh_12_26_9'].tolist(),
            "long_term_rsi_14": latest_long_term['RSI_14'].tolist()
        }
    except Exception as e:
        print(f"Could not fetch data for {symbol}: {e}")
        return None
def generate_prompt():
    """Main function to generate the full prompt string."""
    global invocation_count
    invocation_count += 1
    
    # --- Initialize Binance client for spot market (public data only) ---
    binance = ccxt.binance({
        'options': {
            'defaultType': 'spot',  # Use spot market instead of futures
        },
        'enableRateLimit': True,
    })
    
    # --- Main Prompt Header ---
    minutes_since_start = (datetime.datetime.now() - start_time).total_seconds() / 60
    current_timestamp = datetime.datetime.now().isoformat()
    
    prompt = f"It has been {int(minutes_since_start)} minutes since you started trading. "
    prompt += f"The current time is {current_timestamp} and you've been invoked {invocation_count} times.\n\n"
    prompt += "Below, we are providing you with a variety of state data, price data, and predictive signals so you can discover alpha. Below that is your current account information, value, performance, positions, etc.\n\n"
    prompt += "ALL OF THE PRICE OR SIGNAL DATA BELOW IS ORDERED: OLDEST → NEWEST\n\n"
    prompt += f"Timeframes note: Unless stated otherwise in a section title, intraday series are provided at {INTRADAY_TIMEFRAME} intervals. If a coin uses a different interval, it is explicitly stated in that coin’s section.\n\n"

    # --- Fetch and Format Data for Each Coin ---
    current_prices = {}
    all_coin_data = {}
    for symbol in SYMBOLS:
        print(f"Fetching data for {symbol}...")
        data = get_market_data(binance, symbol)
        if data:
            symbol_base = symbol.split('/')[0]
            all_coin_data[symbol_base] = data
            current_prices[symbol] = data['current_price']
            
    for symbol_base, data in all_coin_data.items():
        prompt += f"CURRENT MARKET STATE FOR ALL COINS\nALL {symbol_base} DATA\n"
        prompt += f"current_price = {data['current_price']}, current_ema20 = {data['current_ema20']:.3f}, current_macd = {data['current_macd']:.3f}, current_rsi (7 period) = {data['current_rsi_7']:.3f}\n\n"
        prompt += "Intraday series (by minute, oldest → latest):\n\n" # Adjust text if timeframe changes
        prompt += f"Mid prices: {data['intraday_mid_prices']}\n"
        prompt += f"EMA indicators (20‑period): {[round(x, 3) for x in data['intraday_ema20']]}\n"
        prompt += f"MACD indicators: {[round(x, 3) for x in data['intraday_macd']]}\n"
        prompt += f"RSI indicators (7‑Period): {[round(x, 3) for x in data['intraday_rsi_7']]}\n"
        prompt += f"RSI indicators (14‑Period): {[round(x, 3) for x in data['intraday_rsi_14']]}\n\n"
        prompt += f"Longer‑term context ({LONG_TERM_TIMEFRAME} timeframe):\n\n"
        prompt += f"20‑Period EMA: {data['long_term_ema20']:.3f} vs. 50‑Period EMA: {data['long_term_ema50']:.3f}\n"
        prompt += f"3‑Period ATR: {data['long_term_atr3']:.3f} vs. 14‑Period ATR: {data['long_term_atr14']:.3f}\n"
        prompt += f"Current Volume: {data['long_term_volume_current']:.3f} vs. Average Volume: {data['long_term_volume_average']:.3f}\n"
        prompt += f"MACD indicators: {[round(x, 3) for x in data['long_term_macd']]}\n"
        prompt += f"RSI indicators (14‑Period): {[round(x, 3) for x in data['long_term_rsi_14']]}\n\n"

    # --- Add Simulated Account Information ---
    account_details = portfolio.get_account_details(current_prices)
    prompt += "HERE IS YOUR ACCOUNT INFORMATION & PERFORMANCE\n"
    for key, value in account_details.items():
        if key != "Current live positions & performance":
            prompt += f"{key}: {value}\n"
    prompt += f"Current live positions & performance: {account_details['Current live positions & performance']}\n"

    return prompt

# --- Main Execution ---
if __name__ == "__main__":
    full_prompt = generate_prompt()
    print("\n--- GENERATED PROMPT ---\n")
    print(full_prompt)