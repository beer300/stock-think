# portfolio.py
import datetime

class SimulatedPortfolio:
    """A class to simulate a trading account and its positions."""
    def __init__(self):
        print("Initializing a new portfolio...")
        self.initial_cash = 10000.0
        self.available_cash = 10000.0
        self.positions = {}  # e.g., {'BTC': {'quantity': 0.1, 'entry_price': 50000}, ...}
        self.sharpe_ratio = 0.0 # Placeholder for future calculation
        self.start_time = datetime.datetime.now()
        self.invocation_count = 0

    def get_account_details(self, current_prices):
        """Calculates and returns the current state of the account."""
        total_pnl = 0
        total_position_value = 0

        # Calculate PnL and value for existing positions
        for symbol_base, pos in self.positions.items():
            symbol_pair = f"{symbol_base}/USDT"
            current_price = current_prices.get(symbol_pair, pos['entry_price'])
            unrealized_pnl = (current_price - pos['entry_price']) * pos['quantity']
            total_pnl += unrealized_pnl
            total_position_value += pos['quantity'] * current_price

        account_value = self.available_cash + total_position_value
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0

        # Format positions for display
        live_positions_info = []
        for symbol_base, pos in self.positions.items():
            live_positions_info.append(
                f"{pos['quantity']:.6f} {symbol_base} @ avg entry ${pos['entry_price']:.2f}"
            )

        return {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": f"${self.available_cash:,.2f}",
            "Current Account Value": f"${account_value:,.2f}",
            "Current live positions & performance": live_positions_info if live_positions_info else "None",
            "Sharpe Ratio": self.sharpe_ratio
        }

    def buy(self, symbol, quantity, current_price):
        """Simulates buying a certain quantity of a symbol."""
        cost = quantity * current_price
        if self.available_cash >= cost:
            self.available_cash -= cost
            symbol_base = symbol.split('/')[0]
            if symbol_base in self.positions:
                # Update existing position (average down/up)
                current_quantity = self.positions[symbol_base]['quantity']
                current_entry_price = self.positions[symbol_base]['entry_price']
                new_quantity = current_quantity + quantity
                new_entry_price = ((current_entry_price * current_quantity) + (cost)) / new_quantity
                
                self.positions[symbol_base]['quantity'] = new_quantity
                self.positions[symbol_base]['entry_price'] = new_entry_price
            else:
                # Add new position
                self.positions[symbol_base] = {'quantity': quantity, 'entry_price': current_price}
            
            print(f"Executed BUY of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Insufficient funds to buy {quantity:.6f} {symbol_base}.")

    def sell(self, symbol, quantity, current_price):
        """Simulates selling a certain quantity of a symbol."""
        symbol_base = symbol.split('/')[0]
        if symbol_base in self.positions and self.positions[symbol_base]['quantity'] >= quantity:
            proceeds = quantity * current_price
            self.available_cash += proceeds
            self.positions[symbol_base]['quantity'] -= quantity
            
            # If the position is closed, remove it from the dictionary
            if self.positions[symbol_base]['quantity'] < 1e-9: # Use a small threshold for float comparison
                del self.positions[symbol_base]
                
            print(f"Executed SELL of {quantity:.6f} {symbol_base} at ${current_price:,.2f}")
        else:
            print(f"Not enough {symbol_base} to sell. You have {self.positions.get(symbol_base, {}).get('quantity', 0)}.")