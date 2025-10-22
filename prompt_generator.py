import ccxt
import pandas as pd
import ta
import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- CONFIGURATION ---
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT']
INTRADAY_TIMEFRAME = '3m'
LONG_TERM_TIMEFRAME = '4h'
DATA_LIMIT = 100

# --- SIMULATION STATE ---
start_time = datetime.datetime.now()
invocation_count = 0

class SimulatedPortfolio:
    """A class to simulate a trading account and its positions."""
    def __init__(self):
        self.initial_cash = 10000
        self.available_cash = 10000
        self.positions = {}
        self.sharpe_ratio = 0.0

    def get_account_details(self, current_prices):
        """Calculates and returns the current state of the account."""
        total_pnl = 0
        for symbol_base, pos in self.positions.items():
            symbol_pair = f"{symbol_base}/USDT"
            current_price = current_prices.get(symbol_pair, pos['entry_price'])
            unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']
            total_pnl += unrealized_pnl

        account_value = self.available_cash + total_pnl
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0

        return {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": self.available_cash,
            "Current Account Value": round(account_value, 2),
            "Current live positions & performance": list(self.positions.keys()),
            "Sharpe Ratio": self.sharpe_ratio
        }

    def buy(self, symbol, quantity, current_price):
        """Simulates buying a certain quantity of a symbol."""
        cost = quantity * current_price
        if self.available_cash >= cost:
            self.available_cash -= cost
            symbol_base = symbol.split('/')[0]
            if symbol_base in self.positions:
                # Update existing position
                current_quantity = self.positions[symbol_base]['quantity']
                current_entry_price = self.positions[symbol_base]['entry_price']
                new_quantity = current_quantity + quantity
                new_entry_price = ((current_entry_price * current_quantity) + (current_price * quantity)) / new_quantity
                self.positions[symbol_base]['quantity'] = new_quantity
                self.positions[symbol_base]['entry_price'] = new_entry_price
            else:
                # Add new position
                self.positions[symbol_base] = {'quantity': quantity, 'entry_price': current_price, 'leverage': 1} # Assuming leverage of 1 for simplicity
            print(f"Executed BUY of {quantity} {symbol_base} at ${current_price:.2f}")
        else:
            print(f"Insufficient funds to buy {quantity} {symbol_base}.")

    def sell(self, symbol, quantity, current_price):
        """Simulates selling a certain quantity of a symbol."""
        symbol_base = symbol.split('/')[0]
        if symbol_base in self.positions and self.positions[symbol_base]['quantity'] >= quantity:
            proceeds = quantity * current_price
            self.available_cash += proceeds
            self.positions[symbol_base]['quantity'] -= quantity
            if self.positions[symbol_base]['quantity'] == 0:
                del self.positions[symbol_base]
            print(f"Executed SELL of {quantity} {symbol_base} at ${current_price:.2f}")
        else:
            print(f"Not enough {symbol_base} to sell.")


def get_market_data(binance, symbol):
    """Fetches and calculates all necessary market data for a single symbol."""
    try:
        ticker = binance.fetch_ticker(symbol)
        current_price = ticker['last']

        intraday_ohlcv = binance.fetch_ohlcv(symbol, timeframe=INTRADAY_TIMEFRAME, limit=DATA_LIMIT)
        long_term_ohlcv = binance.fetch_ohlcv(symbol, timeframe=LONG_TERM_TIMEFRAME, limit=DATA_LIMIT)

        intraday_df = pd.DataFrame(intraday_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        long_term_df = pd.DataFrame(long_term_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        # --- Calculate Indicators ---
        intraday_df['EMA_20'] = ta.trend.ema_indicator(intraday_df['close'], window=20)
        intraday_df['MACDh_12_26_9'] = ta.trend.MACD(intraday_df['close']).macd_diff()
        intraday_df['RSI_7'] = ta.momentum.rsi(intraday_df['close'], window=7)
        long_term_df['EMA_20'] = ta.trend.ema_indicator(long_term_df['close'], window=20)

        latest_intraday = intraday_df.tail(10).round(5)
        latest_long_term = long_term_df.tail(1).round(5)

        return {
            "current_price": current_price,
            "current_ema20": latest_intraday['EMA_20'].iloc[-1],
            "current_macd": latest_intraday['MACDh_12_26_9'].iloc[-1],
            "current_rsi_7": latest_intraday['RSI_7'].iloc[-1],
            "long_term_ema20": latest_long_term['EMA_20'].iloc[-1],
        }
    except Exception as e:
        print(f"Could not fetch data for {symbol}: {e}")
        return None

def generate_prompt(portfolio):
    """Main function to generate the full prompt string."""
    global invocation_count
    invocation_count += 1

    binance = ccxt.binance({'options': {'defaultType': 'spot'}, 'enableRateLimit': True})

    minutes_since_start = (datetime.datetime.now() - start_time).total_seconds() / 60

    prompt = f"It has been {int(minutes_since_start)} minutes since you started. You have been invoked {invocation_count} times.\n"
    prompt += "Analyze the provided market data and account status to make trading decisions.\n\n"
    prompt += "--- MARKET DATA ---\n"

    current_prices = {}
    market_data_for_prompt = {}
    for symbol in SYMBOLS:
        print(f"Fetching data for {symbol}...")
        data = get_market_data(binance, symbol)
        if data:
            current_prices[symbol] = data['current_price']
            market_data_for_prompt[symbol] = data
            symbol_base = symbol.split('/')[0]
            prompt += (
                f"{symbol_base}:\n"
                f"  - Current Price: {data['current_price']:.2f}\n"
                f"  - Intraday EMA(20): {data['current_ema20']:.2f}\n"
                f"  - Intraday MACD Hist: {data['current_macd']:.4f}\n"
                f"  - Intraday RSI(7): {data['current_rsi_7']:.2f}\n"
                f"  - Long-Term EMA(20): {data['long_term_ema20']:.2f}\n\n"
            )

    prompt += "--- ACCOUNT & PERFORMANCE ---\n"
    account_details = portfolio.get_account_details(current_prices)
    for key, value in account_details.items():
        prompt += f"{key}: {value}\n"

    return prompt, market_data_for_prompt