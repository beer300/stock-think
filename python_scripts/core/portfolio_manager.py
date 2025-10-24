# /core/portfolio_manager.py
import datetime
import pickle
from utils import config

class SimulatedPortfolio:
    """
    A class to simulate a trading account, manage its state, positions,
    and performance metrics. It includes robust valuation logic to handle
    potential gaps in real-time market data.
    """
    def __init__(self):
        print("Initializing a new portfolio...")
        self.initial_cash: float = 10000.0
        self.available_cash: float = 10000.0
        self.positions: dict = {}  # E.g., {'BTC': {'quantity': 0.1, 'entry_price': 65000}}
        self.start_time: datetime.datetime = datetime.datetime.now()
        self.invocation_count: int = 0
        self.value_history: list = []
        self.trade_history: list = []

        # --- Risk Management Attributes ---
        self.peak_value: float = self.initial_cash
        self.max_drawdown_threshold: float = config.MAX_DRAWDOWN_THRESHOLD
        self.hard_stop_loss_threshold: float = config.HARD_STOP_LOSS_THRESHOLD
        self.circuit_breaker_tripped: bool = False

        # --- Data Resilience Attribute ---
        self.last_known_prices: dict = {}

    def __setstate__(self, state):
        """
        Custom method to handle loading pickled portfolio objects for backward compatibility.
        Ensures that new attributes exist when loading older portfolio files.
        """
        self.__dict__.update(state)
        # Add new attributes if they are missing in the old pickle file
        if not hasattr(self, 'value_history'): self.value_history = []
        if not hasattr(self, 'trade_history'): self.trade_history = []
        if not hasattr(self, 'peak_value'): self.peak_value = self.initial_cash
        if not hasattr(self, 'max_drawdown_threshold'): self.max_drawdown_threshold = config.MAX_DRAWDOWN_THRESHOLD
        if not hasattr(self, 'hard_stop_loss_threshold'): self.hard_stop_loss_threshold = config.HARD_STOP_LOSS_THRESHOLD
        if not hasattr(self, 'circuit_breaker_tripped'): self.circuit_breaker_tripped = False
        if not hasattr(self, 'last_known_prices'): self.last_known_prices = {}

    # -------------------------------------------------------------------
    # THIS IS THE MISSING METHOD THAT CAUSED THE ERROR
    # -------------------------------------------------------------------
    def update_last_known_prices(self, current_prices: dict):
        """
        Safely updates the internal price cache with the latest fetched prices.
        It only updates prices that are valid (not None).
        """
        for symbol, price in current_prices.items():
            if price is not None and price > 0:
                self.last_known_prices[symbol] = price
    # -------------------------------------------------------------------

    def get_price_for_valuation(self, symbol_base: str) -> float:
        """
        Returns the best available price for an asset for valuation purposes.
        It prioritizes the last known price over the original entry price to give
        the most accurate portfolio value, even if a live price fetch failed.
        """
        symbol_pair = f"{symbol_base}/USDT"
        position = self.positions.get(symbol_base, {})
        # Fallback chain: Last Known Price -> Entry Price -> 0.0
        return self.last_known_prices.get(symbol_pair, position.get('entry_price', 0.0))

    def get_total_value(self) -> float:
        """Calculates the total current value of the portfolio (cash + positions)."""
        total_position_value = sum(
            pos['quantity'] * self.get_price_for_valuation(symbol_base)
            for symbol_base, pos in self.positions.items()
        )
        return self.available_cash + total_position_value

    def get_account_summary(self) -> dict:
        """Returns a summary of the account's performance and status."""
        account_value = self.get_total_value()
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0
        drawdown = ((self.peak_value - account_value) / self.peak_value) * 100 if self.peak_value > 0 else 0

        summary = {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": f"${self.available_cash:,.2f}",
            "Current Account Value": f"${account_value:,.2f}",
            "Peak Account Value": f"${self.peak_value:,.2f}",
            "Current Drawdown": f"{drawdown:.2f}%",
        }
        if self.circuit_breaker_tripped:
            summary["STATUS"] = "CIRCUIT BREAKER TRIPPED: TRADING HALTED"
        return summary

    def get_detailed_positions(self) -> list:
        """Returns a detailed list of current positions including P&L."""
        detailed_positions = []
        for symbol_base, pos in self.positions.items():
            current_price = self.get_price_for_valuation(symbol_base)
            notional_value = pos['quantity'] * current_price
            unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']

            detailed_positions.append({
                "side": "LONG",
                "coin": symbol_base,
                "notional": f"${notional_value:,.2f}",
                "unreal_pnl": f"${unrealized_pnl:,.2f}",
                "entry_price": pos['entry_price'],
                "quantity": pos['quantity']
            })
        return detailed_positions

    def record_value_history(self, account_value: float):
        """Records the account value for charting and updates the peak value."""
        self.peak_value = max(self.peak_value, account_value)
        rounded_value = round(account_value, 2)

        if not self.value_history or self.value_history[-1]['value'] != rounded_value:
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            self.value_history.append({'timestamp': timestamp, 'value': rounded_value})

    def buy(self, symbol: str, quantity: float, current_price: float):
        """Executes a buy order, updating cash and position details."""
        cost = quantity * current_price
        symbol_base = symbol.split('/')[0]

        if self.available_cash >= cost:
            self.available_cash -= cost
            if symbol_base in self.positions:
                # Average down the entry price if position already exists
                current_quantity = self.positions[symbol_base]['quantity']
                current_cost = self.positions[symbol_base]['entry_price'] * current_quantity
                new_quantity = current_quantity + quantity
                self.positions[symbol_base]['entry_price'] = (current_cost + cost) / new_quantity
                self.positions[symbol_base]['quantity'] = new_quantity
            else:
                self.positions[symbol_base] = {'quantity': quantity, 'entry_price': current_price}
            print(f"Executed BUY of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Insufficient funds to buy {quantity:.6f} {symbol_base}.")

    def sell(self, symbol: str, quantity: float, current_price: float, reason: str = ""):
        """Executes a sell order, updating cash and removing or reducing the position."""
        symbol_base = symbol.split('/')[0]

        if symbol_base in self.positions and self.positions[symbol_base]['quantity'] >= quantity:
            self.available_cash += quantity * current_price
            self.positions[symbol_base]['quantity'] -= quantity

            if self.positions[symbol_base]['quantity'] < 1e-9: # Use threshold for float comparison
                del self.positions[symbol_base]

            log_message = f"Executed SELL of {quantity:.6f} {symbol_base} at ${current_price:,.2f}"
            if reason:
                log_message += f" (Reason: {reason})"
            print(log_message)
        else:
            print(f"Not enough {symbol_base} to sell. You have {self.positions.get(symbol_base, {}).get('quantity', 0)}.")

    def record_trade_decision(self, prompt: str, reasoning: str, decisions: list):
        """Records the AI's trading decisions and reasoning for historical tracking."""
        trade_record = {
            'timestamp': datetime.datetime.utcnow().isoformat() + "Z",
            'prompt': "...", # Prompt can be very long, summarizing or omitting can be useful
            'reasoning': reasoning,
            'decisions': decisions,
            'portfolio_value': self.get_total_value()
        }
        self.trade_history.append(trade_record)