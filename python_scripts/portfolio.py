# porfolio.py
import datetime
import json
import numpy as np

class SimulatedPortfolio:
    """A class to simulate a trading account and its positions."""
    def __init__(self):
        print("Initializing a new portfolio...")
        self.initial_cash = 10000.0
        self.available_cash = 10000.0
        self.positions = {}
        self.sharpe_ratio = 0.0
        self.start_time = datetime.datetime.now()
        self.invocation_count = 0
        self.value_history = []
        self.trade_history = []  # Store the history of trades with reasoning
        
        # Attributes for risk management
        self.peak_value = self.initial_cash
        self.max_drawdown_threshold = 0.20 # Halt trading if portfolio drops >20% from peak
        self.hard_stop_loss_threshold = 0.10 # Automatic 10% loss exit per position
        self.circuit_breaker_tripped = False

    def __setstate__(self, state):
        """Custom method to handle loading pickled portfolio objects for backward compatibility."""
        self.__dict__.update(state)
        # Ensure new attributes exist when loading older portfolio files
        if not hasattr(self, 'value_history'):
            self.value_history = []
        if not hasattr(self, 'trade_history'):
            self.trade_history = []
        if not hasattr(self, 'peak_value'):
            self.peak_value = self.initial_cash
        if not hasattr(self, 'max_drawdown_threshold'):
            self.max_drawdown_threshold = 0.20
        if not hasattr(self, 'hard_stop_loss_threshold'):
            self.hard_stop_loss_threshold = 0.10
        if not hasattr(self, 'circuit_breaker_tripped'):
            self.circuit_breaker_tripped = False
        
        # If starting a portfolio from an old file, initialize its value history
        if not self.value_history and hasattr(self, 'initial_cash'):
             self.record_value_history(self.initial_cash)

    def get_total_value(self, current_prices):
        """Calculates the total current value of the portfolio (cash + positions)."""
        total_position_value = sum(
            pos['quantity'] * current_prices.get(f"{symbol_base}/USDT", pos['entry_price'])
            for symbol_base, pos in self.positions.items()
        )
        return self.available_cash + total_position_value

    def get_account_summary(self, current_prices):
        """Calculates and returns a summary of the account's performance and status."""
        account_value = self.get_total_value(current_prices)
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0
        drawdown = ((self.peak_value - account_value) / self.peak_value) * 100 if self.peak_value > 0 else 0

        summary = {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": f"${self.available_cash:,.2f}",
            "Current Account Value": f"${account_value:,.2f}",
            "Peak Account Value": f"${self.peak_value:,.2f}",
            "Current Drawdown": f"{drawdown:.2f}%",
            "Sharpe Ratio": self.sharpe_ratio
        }
        if self.circuit_breaker_tripped:
            summary["STATUS"] = "CIRCUIT BREAKER TRIPPED: TRADING HALTED"
        return summary

    def get_detailed_positions(self, current_prices):
        """Returns a detailed list of current positions including P&L and other metrics."""
        detailed_positions = []
        for symbol_base, pos in self.positions.items():
            symbol_pair = f"{symbol_base}/USDT"
            current_price = current_prices.get(symbol_pair, pos['entry_price'])
            notional_value = pos['quantity'] * current_price
            unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']
            
            detailed_positions.append({
                "side": "LONG", # Assuming spot, so all positions are LONG
                "coin": symbol_base,
                "leverage": "1x", # Spot trading is 1x leverage
                "notional": f"${notional_value:,.2f}",
                "unreal_pnl": f"${unrealized_pnl:,.2f}",
                "entry_price": pos['entry_price'],
                "quantity": pos['quantity'] # Added for stop-loss logic
            })
        return detailed_positions

    def record_value_history(self, account_value):
        """Records the current account value for charting and updates the peak value for drawdown calculation."""
        # Update the peak value every time the history is recorded
        self.peak_value = max(self.peak_value, account_value)
        
        # To avoid redundant data points, only add if the value has changed
        if not self.value_history or self.value_history[-1]['value'] != round(account_value, 2):
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            self.value_history.append({
                'timestamp': timestamp,
                'value': round(account_value, 2)
            })

    def buy(self, symbol, quantity, current_price):
        """Executes a buy order, updating cash and position details."""
        cost = quantity * current_price
        symbol_base = symbol.split('/')[0]
        
        if self.available_cash >= cost:
            self.available_cash -= cost
            # If position already exists, average down the entry price
            if symbol_base in self.positions:
                current_quantity = self.positions[symbol_base]['quantity']
                new_quantity = current_quantity + quantity
                new_entry_price = ((self.positions[symbol_base]['entry_price'] * current_quantity) + cost) / new_quantity
                self.positions[symbol_base]['quantity'] = new_quantity
                self.positions[symbol_base]['entry_price'] = new_entry_price
            else:
                self.positions[symbol_base] = {'quantity': quantity, 'entry_price': current_price}
            print(f"Executed BUY of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Insufficient funds to buy {quantity:.6f} {symbol_base}.")

    def sell(self, symbol, quantity, current_price, reason=""):
        """Executes a sell order, updating cash and removing or reducing the position."""
        symbol_base = symbol.split('/')[0]
        
        if symbol_base in self.positions and self.positions[symbol_base]['quantity'] >= quantity:
            proceeds = quantity * current_price
            self.available_cash += proceeds
            self.positions[symbol_base]['quantity'] -= quantity
            
            # If the entire position is sold, remove it from the dictionary
            if self.positions[symbol_base]['quantity'] < 1e-9: # Use a small threshold for float comparison
                del self.positions[symbol_base]
            
            log_message = f"Executed SELL of {quantity:.6f} {symbol_base} at ${current_price:,.2f}"
            if reason:
                log_message += f" (Reason: {reason})"
            print(log_message)
        else:
            print(f"Not enough {symbol_base} to sell. You have {self.positions.get(symbol_base, {}).get('quantity', 0)}.")

    def record_trade_decision(self, prompt: str, reasoning: str, decisions: list, timestamp=None):
        """Records the AI's trading decisions and reasoning for historical tracking."""
        if timestamp is None:
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        # Create a prices dictionary for portfolio value calculation
        prices = {}
        if decisions:
            for decision in decisions:
                if isinstance(decision, dict) and 'symbol' in decision:
                    symbol = decision['symbol']
                    # Try to get price from market data if available
                    try:
                        price = float(decision.get('current_price', 0))
                        if price > 0:
                            prices[f"{symbol}/USDT"] = price
                    except (ValueError, TypeError):
                        continue
        
        trade_record = {
            'timestamp': timestamp,
            'prompt': prompt,
            'reasoning': reasoning,
            'decisions': decisions,
            'portfolio_value': self.get_total_value(prices) if prices else self.get_total_value({})
        }
        
        if not hasattr(self, 'trade_history'):
            self.trade_history = []
            
        self.trade_history.append(trade_record)
        # Keep only the last 100 trade records to manage memory
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]