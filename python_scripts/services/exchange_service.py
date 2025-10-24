# /services/exchange_service.py
import ccxt
import pandas as pd
import ta
import datetime
from utils import config
from utils.error_handler import retry_on_exception
from core.portfolio_manager import SimulatedPortfolio

class ExchangeService:
    """
    Handles all communication with the cryptocurrency exchange.
    This includes fetching market data, calculating technical indicators,
    and generating the data-rich prompt for the AI service.
    """
    def __init__(self):
        self.binance = ccxt.binance({
            'options': {'defaultType': 'spot'},
            'enableRateLimit': True
        })

    @retry_on_exception
    def _fetch_ticker(self, symbol: str):
        """Internal method to fetch ticker data with retry logic."""
        return self.binance.fetch_ticker(symbol)

    @retry_on_exception
    def _fetch_ohlcv(self, symbol: str, timeframe: str, limit: int):
        """Internal method to fetch OHLCV data with retry logic."""
        return self.binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

    def get_market_data_for_symbol(self, symbol: str):
        """
        Fetches and processes comprehensive market data for a single symbol.
        Includes current price, liquidity, and a suite of technical indicators
        across multiple timeframes.
        """
        try:
            # 1. Fetch current price and liquidity data
            ticker = self._fetch_ticker(symbol)
            if not ticker or 'last' not in ticker:
                print(f"Warning: Could not fetch valid ticker for {symbol}.")
                return None

            current_price = ticker['last']
            bid_ask_spread = (ticker['ask'] - ticker['bid']) / ticker['ask'] * 100 if ticker.get('ask', 0) > 0 else 0

            multi_timeframe_data = {}
            for timeframe in config.TIMEFRAMES:
                # 2. Fetch historical data for each timeframe
                ohlcv = self._fetch_ohlcv(symbol, timeframe, config.DATA_LIMIT)
                if not ohlcv or len(ohlcv) < 50: # Check for sufficient data
                    print(f"Warning: Not enough OHLCV data for {symbol} on {timeframe} timeframe.")
                    continue

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                if df.empty:
                    continue

                # 3. Calculate Technical Indicators
                bb = ta.volatility.BollingerBands(close=df['close'], window=20, window_dev=2)
                ema_fast = ta.trend.ema_indicator(df['close'], window=50)
                ema_slow = ta.trend.ema_indicator(df['close'], window=200)

                # Use -2 to get the last *completed* candle
                latest = df.iloc[-2]

                # Determine Market Regime
                regime = 'Sideways'
                if pd.notna(ema_slow.iloc[-2]):
                    if ema_fast.iloc[-2] > ema_slow.iloc[-2]:
                        regime = 'Bullish'
                    else:
                        regime = 'Bearish'

                multi_timeframe_data[timeframe] = {
                    'bb_high': bb.bollinger_hband().iloc[-2],
                    'bb_mid': bb.bollinger_mavg().iloc[-2],
                    'bb_low': bb.bollinger_lband().iloc[-2],
                    'atr': ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14).iloc[-2],
                    'vwma': ta.volume.volume_weighted_average_price(df['high'], df['low'], df['close'], df['volume'], window=14).iloc[-2],
                    'volume': latest['volume'],
                    'volume_ma': df['volume'].rolling(window=20).mean().iloc[-2],
                    'market_regime': regime
                }

            if not multi_timeframe_data:
                return None # Return None if no timeframe data could be processed

            return {
                "current_price": current_price,
                "bid_ask_spread_percent": bid_ask_spread,
                "timeframe_data": multi_timeframe_data
            }
        except Exception as e:
            print(f"Error processing comprehensive data for {symbol}: {e}")
            return None

    def get_correlation_matrix(self):
        """
        Calculates the Pearson correlation matrix of price returns for all symbols.
        """
        all_returns = {}
        for symbol in config.SYMBOLS:
            ohlcv = self._fetch_ohlcv(symbol, '4h', config.CORRELATION_HISTORY_LIMIT)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                # Calculate percentage change in closing price
                df['returns'] = df['close'].pct_change()
                all_returns[symbol.split('/')[0]] = df['returns']

        if not all_returns:
            return pd.DataFrame()

        returns_df = pd.DataFrame(all_returns).dropna()
        return returns_df.corr()

    def generate_full_prompt(self, portfolio: SimulatedPortfolio):
        """
        Constructs the main prompt for the AI by gathering all market data,
        portfolio status, and risk metrics into a single formatted string.
        """
        portfolio.invocation_count += 1
        minutes_since_start = (datetime.datetime.now() - portfolio.start_time).total_seconds() / 60

        prompt = f"It has been {int(minutes_since_start)} minutes since the first run. Invocation: {portfolio.invocation_count}.\n"
        prompt += "Analyze the comprehensive multi-timeframe market data and account status to make trading decisions.\n\n"

        # 1. Asset Correlation Matrix
        print("Fetching correlation matrix...")
        correlation_matrix = self.get_correlation_matrix()
        if not correlation_matrix.empty:
            prompt += "--- ASSET CORRELATION MATRIX (4H Returns) ---\n"
            prompt += correlation_matrix.round(2).to_string() + "\n"
            prompt += f"Note: Avoid buying assets with >{config.HIGH_CORRELATION_THRESHOLD} correlation to existing holdings.\n\n"

        # 2. Comprehensive Market Analysis for each symbol
        prompt += "--- COMPREHENSIVE MARKET ANALYSIS ---\n"
        market_data_full = {}
        for symbol in config.SYMBOLS:
            print(f"Fetching comprehensive data for {symbol}...")
            data = self.get_market_data_for_symbol(symbol)
            if data:
                market_data_full[symbol] = data
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

        # 3. Account & Performance Summary
        current_prices = {s: d['current_price'] for s, d in market_data_full.items() if d}
        portfolio.update_last_known_prices(current_prices) # Update portfolio's internal price list

        prompt += "--- ACCOUNT & PERFORMANCE ---\n"
        account_summary = portfolio.get_account_summary()
        for key, value in account_summary.items():
            prompt += f"{key}: {value}\n"

        # 4. Current Positions
        detailed_positions = portfolio.get_detailed_positions()
        if detailed_positions:
            prompt += "\n--- CURRENT POSITIONS ---\n"
            for pos in detailed_positions:
                prompt += (
                    f"- {pos['coin']}: Notional: {pos['notional']}, "
                    f"Unrealized P&L: {pos['unreal_pnl']}, "
                    f"Avg Entry: ${pos['entry_price']:.2f}\n"
                )

        return prompt, market_data_full, correlation_matrix