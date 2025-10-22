# portfolio.py
import datetime
import json

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
        # --- NEW: Add a list to store value history ---
        self.value_history = []

    def __setstate__(self, state):
        """
        Custom method to handle loading pickled state. This makes the class
        backward-compatible with older pickle files that lack 'value_history'.
        """
        # Restore the attributes from the pickled file
        self.__dict__.update(state)
        # Check for the existence of 'value_history' and add it if it's missing
        if not hasattr(self, 'value_history'):
            self.value_history = []
            # Optional: If you want to ensure the chart has a starting point,
            # you can add the initial value to the history.
            if hasattr(self, 'initial_cash'):
                 self.record_value_history(self.initial_cash)


    def get_account_details(self, current_prices):
        """Calculates and returns the current state of the account."""
        total_position_value = 0
        for symbol_base, pos in self.positions.items():
            symbol_pair = f"{symbol_base}/USDT"
            current_price = current_prices.get(symbol_pair, pos['entry_price'])
            total_position_value += pos['quantity'] * current_price

        account_value = self.available_cash + total_position_value
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0

        live_positions_info = [
            f"{pos['quantity']:.6f} {symbol_base} @ avg entry ${pos['entry_price']:.2f}"
            for symbol_base, pos in self.positions.items()
        ]

        return {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": f"${self.available_cash:,.2f}",
            "Current Account Value": f"${account_value:,.2f}",
            "Current live positions & performance": live_positions_info if live_positions_info else "None",
            "Sharpe Ratio": self.sharpe_ratio
        }

    def record_value_history(self, account_value):
        """Records the current account value with a UTC timestamp."""
        if not self.value_history or self.value_history[-1]['value'] != round(account_value, 2):
            # Ensure timestamp is in ISO 8601 format with a 'Z' for UTC, which is more robust for JavaScript's new Date()
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            self.value_history.append({
                'timestamp': timestamp,
                'value': round(account_value, 2)
            })

    # (buy and sell methods remain unchanged)
    def buy(self, symbol, quantity, current_price):
        cost = quantity * current_price
        if self.available_cash >= cost:
            self.available_cash -= cost
            symbol_base = symbol.split('/')[0]
            if symbol_base in self.positions:
                current_quantity = self.positions[symbol_base]['quantity']
                new_quantity = current_quantity + quantity
                new_entry_price = ((self.positions[symbol_base]['entry_price'] * current_quantity) + (cost)) / new_quantity
                self.positions[symbol_base]['quantity'] = new_quantity
                self.positions[symbol_base]['entry_price'] = new_entry_price
            else:
                self.positions[symbol_base] = {'quantity': quantity, 'entry_price': current_price}
            print(f"Executed BUY of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Insufficient funds to buy {quantity:.6f} {symbol_base}.")


    def sell(self, symbol, quantity, current_price):
        symbol_base = symbol.split('/')[0]
        if symbol_base in self.positions and self.positions[symbol_base]['quantity'] >= quantity:
            proceeds = quantity * current_price
            self.available_cash += proceeds
            self.positions[symbol_base]['quantity'] -= quantity
            if self.positions[symbol_base]['quantity'] < 1e-9:
                del self.positions[symbol_base]
            print(f"Executed SELL of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Not enough {symbol_base} to sell. You have {self.positions.get(symbol_base, {}).get('quantity', 0)}.")