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
        self.value_history = []

    def __setstate__(self, state):
        self.__dict__.update(state)
        if not hasattr(self, 'value_history'):
            self.value_history = []
            if hasattr(self, 'initial_cash'):
                 self.record_value_history(self.initial_cash)

    def get_account_summary(self, current_prices):
        """Calculates and returns a summary of the account."""
        total_position_value = sum(
            pos['quantity'] * current_prices.get(f"{symbol_base}/USDT", pos['entry_price'])
            for symbol_base, pos in self.positions.items()
        )
        account_value = self.available_cash + total_position_value
        total_return = ((account_value / self.initial_cash) - 1) * 100 if self.initial_cash > 0 else 0

        return {
            "Current Total Return (percent)": f"{total_return:.2f}%",
            "Available Cash": f"${self.available_cash:,.2f}",
            "Current Account Value": f"${account_value:,.2f}",
            "Sharpe Ratio": self.sharpe_ratio
        }

    def get_detailed_positions(self, current_prices):
        """Returns a detailed list of current positions including P&L."""
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
                "entry_price": pos['entry_price']
            })
        return detailed_positions

    def record_value_history(self, account_value):
        """Records the current account value with a UTC timestamp."""
        if not self.value_history or self.value_history[-1]['value'] != round(account_value, 2):
            timestamp = datetime.datetime.utcnow().isoformat() + "Z"
            self.value_history.append({
                'timestamp': timestamp,
                'value': round(account_value, 2)
            })

    def buy(self, symbol, quantity, current_price):
        cost = quantity * current_price
        symbol_base = symbol.split('/')[0] # FIX: Moved definition to outer scope
        if self.available_cash >= cost:
            self.available_cash -= cost
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