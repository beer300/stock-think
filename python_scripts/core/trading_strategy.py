# /core/trading_strategy.py
import pandas as pd
from utils import config
from core.portfolio_manager import SimulatedPortfolio

def run_risk_management_checks(portfolio: SimulatedPortfolio) -> bool:
    """
    Performs all pre-trade safety checks on the portfolio.

    This includes:
    1.  Hard Stop-Loss Check: Automatically exits positions that have lost a predefined percentage.
    2.  Maximum Drawdown Check: Halts all trading if the portfolio's value drops
        significantly from its peak (a "circuit breaker").

    Args:
        portfolio: The SimulatedPortfolio object to be checked.

    Returns:
        True if trading is safe to continue, False if a circuit breaker is tripped.
    """
    print("\n--- Running Pre-Trade Risk Management ---")

    # --- A. Hard Stop-Loss Check ---
    # Iterate over a copy of position keys to allow for modification during the loop
    current_positions = portfolio.get_detailed_positions()
    for position in current_positions:
        symbol_base = position['coin']
        current_price = portfolio.get_price_for_valuation(symbol_base)
        if not current_price:
            continue

        entry_price = position['entry_price']
        stop_loss_price = entry_price * (1 - portfolio.hard_stop_loss_threshold)

        if current_price < stop_loss_price:
            print(f"!!! HARD STOP-LOSS TRIGGERED FOR {symbol_base} at ${current_price:,.2f} (Entry: ${entry_price:,.2f})")
            portfolio.sell(f"{symbol_base}/USDT", position['quantity'], current_price, reason="Hard Stop-Loss")

    # --- B. Maximum Drawdown Circuit Breaker Check ---
    total_value = portfolio.get_total_value()
    # Update portfolio value history and peak value before checking drawdown
    portfolio.record_value_history(total_value)

    if portfolio.peak_value > 0:
        drawdown = (portfolio.peak_value - total_value) / portfolio.peak_value
        if drawdown > portfolio.max_drawdown_threshold:
            portfolio.circuit_breaker_tripped = True
            print(f"!!! MAX DRAWDOWN >{portfolio.max_drawdown_threshold*100:.1f}%. CIRCUIT BREAKER TRIPPED! HALTING TRADING. !!!")
            return False # Trading is not safe

    if portfolio.circuit_breaker_tripped:
        print("Trading remains halted due to a previously tripped circuit breaker.")
        return False # Trading is not safe

    return True # All checks passed, trading is safe to continue


def execute_ai_decisions(portfolio: SimulatedPortfolio, decisions: list, current_prices: dict, correlation_matrix: pd.DataFrame):
    """
    Executes the trading decisions from the AI after performing final checks,
    such as correlation analysis for new buy orders.

    Args:
        portfolio: The SimulatedPortfolio object.
        decisions: A list of decision dictionaries from the AI.
        current_prices: A dictionary of the latest asset prices.
        correlation_matrix: A pandas DataFrame with the asset correlation data.
    """
    if not decisions:
        print("No valid AI decisions to execute.")
        return

    print("\n--- Executing AI Decisions ---")
    for decision in decisions:
        symbol_base = decision.get('symbol')
        if not symbol_base:
            continue

        symbol_pair = f"{symbol_base}/USDT"
        action = decision.get('action', '').upper()

        try:
            quantity = float(decision.get('quantity', 0))
            if quantity < 1e-9 and action != 'HOLD':
                continue
        except (ValueError, TypeError):
            print(f"Skipping decision for {symbol_base} due to invalid quantity.")
            continue

        # Ensure we have a valid price to execute the trade
        price = current_prices.get(symbol_pair)
        if not price:
            print(f"Skipping decision for {symbol_pair}: No valid current price available.")
            continue

        if action == 'BUY':
            # --- C. Correlation Check ---
            # Prevent buying assets that are too similar to existing holdings.
            is_highly_correlated = False
            if not correlation_matrix.empty and symbol_base in correlation_matrix:
                held_symbols = list(portfolio.positions.keys())
                if held_symbols:
                    # Check correlation against all currently held assets
                    correlations = correlation_matrix[symbol_base].loc[held_symbols]
                    for held_symbol, corr_value in correlations.items():
                        if corr_value > config.HIGH_CORRELATION_THRESHOLD:
                            print(f"SKIPPING BUY of {symbol_base}: Highly correlated ({corr_value:.2f}) with held asset {held_symbol}.")
                            is_highly_correlated = True
                            break
            if not is_highly_correlated:
                portfolio.buy(symbol_pair, quantity, price)

        elif action == 'SELL':
            portfolio.sell(symbol_pair, quantity, price, reason="AI Decision")

        elif action == 'HOLD':
            # No action needed for HOLD, but we can log it for clarity
            # print(f"AI decision: HOLD {symbol_base}.")
            pass