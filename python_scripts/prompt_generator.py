# prompt_generator.py
import ccxt
import pandas as pd
import ta
import datetime
import numpy as np
from dotenv import load_dotenv
from portfolio import SimulatedPortfolio

load_dotenv()

SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT']
TIMEFRAMES = ['5m', '1h', '4h', '1d']
DATA_LIMIT = 200 # Using a larger limit for more accurate indicator calculations
CORRELATION_HISTORY_LIMIT = 200 # Number of candles for return correlation

def get_market_data(binance, symbol):
    """
    Fetches and processes comprehensive market data for a single symbol across multiple timeframes.
    Includes current price, liquidity, and a suite of technical indicators.
    """
    try:
        # Fetch ticker data once for current price and bid-ask spread
        ticker = binance.fetch_ticker(symbol)
        current_price = ticker['last']
        bid_ask_spread = (ticker['ask'] - ticker['bid']) / ticker['ask'] * 100 if ticker['ask'] > 0 else 0

        multi_timeframe_data = {}
        for timeframe in TIMEFRAMES:
            # Fetch historical data for the current timeframe
            ohlcv = binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=DATA_LIMIT)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # --- Calculate Additional Technical Indicators ---
            
            # Bollinger Bands (Volatility)
            bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
            df['bb_high'] = bb.bollinger_hband()
            df['bb_mid'] = bb.bollinger_mavg()
            df['bb_low'] = bb.bollinger_lband()
            
            # ATR (Average True Range - Volatility)
            df['atr'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            
            # VWMA (Volume-Weighted Moving Average)
            df['vwma'] = ta.volume.volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'], window=14)

            # --- Volume Analysis ---
            # Calculate a 20-period moving average of volume to identify trends
            df['volume_ma_20'] = df['volume'].rolling(window=20).mean()

            # --- Market Regime Detection ---
            # Use a 50/200 EMA crossover to classify the trend
            ema_fast = ta.trend.ema_indicator(df['close'], window=50)
            ema_slow = ta.trend.ema_indicator(df['close'], window=200)
            
            # Get the most recent full candle's data
            latest = df.iloc[-2] # Use -2 to get the last completed candle
            
            regime = 'Sideways' # Default regime
            # Check for non-null slow EMA to avoid errors on new charts
            if pd.notna(latest['close']) and pd.notna(ema_slow.iloc[-2]):
                if ema_fast.iloc[-2] > ema_slow.iloc[-2]:
                    regime = 'Bullish'
                else:
                    regime = 'Bearish'
                
            multi_timeframe_data[timeframe] = {
                'bb_high': latest['bb_high'],
                'bb_mid': latest['bb_mid'],
                'bb_low': latest['bb_low'],
                'atr': latest['atr'],
                'vwma': latest['vwma'],
                'volume': latest['volume'],
                'volume_ma': latest['volume_ma_20'],
                'market_regime': regime
            }

        return {
            "current_price": current_price,
            "bid_ask_spread_percent": bid_ask_spread,
            "timeframe_data": multi_timeframe_data
        }
    except Exception as e:
        print(f"Could not fetch comprehensive data for {symbol}: {e}")
        return None

def get_correlation_matrix(binance):
    """
    Fetches historical data for all symbols and calculates the Pearson correlation matrix
    of their price returns to inform diversification.
    """
    all_returns = {}
    for symbol in SYMBOLS:
        try:
            # Use a consistent timeframe for correlation analysis
            ohlcv = binance.fetch_ohlcv(symbol, timeframe='4h', limit=CORRELATION_HISTORY_LIMIT)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            # Calculate percentage change in closing price
            df['returns'] = df['close'].pct_change()
            all_returns[symbol.split('/')[0]] = df['returns']
        except Exception as e:
            print(f"Could not fetch historical data for {symbol} correlation: {e}")
    
    if not all_returns:
        return pd.DataFrame()

    returns_df = pd.DataFrame(all_returns).dropna()
    correlation_matrix = returns_df.corr()
    return correlation_matrix

def generate_prompt(portfolio: SimulatedPortfolio):
    """
    Constructs the main prompt for the AI by gathering all market data,
    portfolio status, and risk metrics into a single formatted string.
    """
    portfolio.invocation_count += 1
    binance = ccxt.binance({'options': {'defaultType': 'spot'}, 'enableRateLimit': True})
    minutes_since_start = (datetime.datetime.now() - portfolio.start_time).total_seconds() / 60
    
    prompt = f"It has been {int(minutes_since_start)} minutes since the first run. Invocation: {portfolio.invocation_count}.\n"
    prompt += "Analyze the comprehensive multi-timeframe market data and account status to make trading decisions.\n\n"
    
    print("Fetching correlation matrix...")
    correlation_matrix = get_correlation_matrix(binance)
    if not correlation_matrix.empty:
        prompt += "--- ASSET CORRELATION MATRIX (4H Returns) ---\n"
        prompt += correlation_matrix.round(2).to_string() + "\n"
        prompt += "Note: Avoid buying assets with >0.7 correlation to existing holdings.\n\n"

    prompt += "--- COMPREHENSIVE MARKET ANALYSIS ---\n"
    market_data_for_prompt = {}
    for symbol in SYMBOLS:
        print(f"Fetching comprehensive data for {symbol}...")
        data = get_market_data(binance, symbol)
        if data:
            market_data_for_prompt[symbol] = data
            symbol_base = symbol.split('/')[0]
            prompt += (
                f"--- {symbol_base} ---\n"
                f"  - Current Price: ${data['current_price']:.2f}\n"
                f"  - Bid-Ask Spread (Liquidity): {data['bid_ask_spread_percent']:.4f}%\n"
            )
            for tf, tf_data in data['timeframe_data'].items():
                volume_trend = "Above Average" if tf_data.get('volume', 0) > tf_data.get('volume_ma', 0) else "Below Average"
                prompt += (
                    f"  - Timeframe: {tf}\n"
                    f"    - Market Regime: {tf_data['market_regime']}\n"
                    f"    - Bollinger Bands: Low=${tf_data.get('bb_low', 0):.2f}, Mid=${tf_data.get('bb_mid', 0):.2f}, High=${tf_data.get('bb_high', 0):.2f}\n"
                    f"    - ATR (Volatility): ${tf_data.get('atr', 0):.3f}\n"
                    f"    - VWMA (Volume-Weighted Price): ${tf_data.get('vwma', 0):.2f}\n"
                    f"    - Volume: {tf_data.get('volume', 0):.0f} (Trend: {volume_trend})\n"
                )
            prompt += "\n"

    # Get a clean dictionary of current prices for portfolio calculations
    current_prices = {s: d['current_price'] for s, d in market_data_for_prompt.items() if d}
    
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

    return prompt, market_data_for_prompt, correlation_matrix