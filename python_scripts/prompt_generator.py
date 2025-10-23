import ccxt
import pandas as pd
import ta
import datetime
from dotenv import load_dotenv
from portfolio import SimulatedPortfolio

load_dotenv()

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT']
INTRADAY_TIMEFRAME = '3m'
LONG_TERM_TIMEFRAME = '4h'
DATA_LIMIT = 100

def get_market_data(binance, symbol):
    try:
        ticker = binance.fetch_ticker(symbol)
        current_price = ticker['last']
        intraday_ohlcv = binance.fetch_ohlcv(symbol, timeframe=INTRADAY_TIMEFRAME, limit=DATA_LIMIT)
        long_term_ohlcv = binance.fetch_ohlcv(symbol, timeframe=LONG_TERM_TIMEFRAME, limit=DATA_LIMIT)
        intraday_df = pd.DataFrame(intraday_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        long_term_df = pd.DataFrame(long_term_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
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

def generate_prompt(portfolio: SimulatedPortfolio):
    portfolio.invocation_count += 1
    binance = ccxt.binance({'options': {'defaultType': 'spot'}, 'enableRateLimit': True})
    minutes_since_start = (datetime.datetime.now() - portfolio.start_time).total_seconds() / 60
    
    prompt = f"It has been {int(minutes_since_start)} minutes since the first run. Invocation: {portfolio.invocation_count}.\n"
    prompt += "Analyze the market and account status to make trading decisions.\n\n"
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
                f"  - Price: {data['current_price']:.2f}\n"
                f"  - Intraday EMA(20): {data['current_ema20']:.2f}\n"
                f"  - Intraday MACD Hist: {data['current_macd']:.4f}\n"
                f"  - Intraday RSI(7): {data['current_rsi_7']:.2f}\n"
                f"  - Long-Term EMA(20): {data['long_term_ema20']:.2f}\n\n"
            )

    prompt += "--- ACCOUNT & PERFORMANCE ---\n"
    account_summary = portfolio.get_account_summary(current_prices)
    for key, value in account_summary.items():
        prompt += f"{key}: {value}\n"

    detailed_positions = portfolio.get_detailed_positions(current_prices)
    if detailed_positions:
        prompt += "\n--- CURRENT POSITIONS ---\n"
        for pos in detailed_positions:
            prompt += (
                f"- {pos['coin']}: Notional: {pos['notional']}, "
                f"Unrealized P&L: {pos['unreal_pnl']}, "
                f"Avg Entry: ${pos['entry_price']:.2f}\n"
            )

    return prompt, market_data_for_prompt