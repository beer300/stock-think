# main.py
import os
import sys
import pickle
import json
from core.portfolio_manager import SimulatedPortfolio
from core.trading_strategy import run_risk_management_checks, execute_ai_decisions
from services.exchange_service import ExchangeService
from services.ai_service import get_decision_from_openrouter, parse_ai_response
from utils import config
from utils.price_cache import load_price_cache, save_price_cache

def log(message: str):
    """Helper function to print messages to stderr."""
    print(message, file=sys.stderr)

def main():
    """
    The main entry point and execution loop for the trading bot application.
    """
    
    # --- 1. Load Portfolio, Services, and Price Cache ---
    log("--- Initializing Trading Bot ---")
    if os.path.exists(config.PORTFOLIO_FILE):
        try:
            with open(config.PORTFOLIO_FILE, 'rb') as f:
                portfolio = pickle.load(f)
            log("Loaded existing portfolio from file.")
        except (pickle.UnpicklingError, EOFError) as e:
            log(f"Could not load portfolio file, creating a new one. Error: {e}")
            portfolio = SimulatedPortfolio()
    else:
        portfolio = SimulatedPortfolio()
        log("No existing portfolio found, created a new one.")
        
    portfolio.last_known_prices = load_price_cache()
    
    exchange = ExchangeService()

    # --- 2. Generate Prompt with Comprehensive Market Data ---
    prompt, market_data_full, correlation_matrix = exchange.generate_full_prompt(portfolio)
    
    current_prices = {
        s: d['current_price'] 
        for s, d in market_data_full.items() 
        if d and d.get('current_price') is not None
    }
    
    # --- 3. Update and Save Price Cache ---
    portfolio.update_last_known_prices(current_prices)
    save_price_cache(portfolio.last_known_prices)
    log("Price cache has been updated and saved.")

    # --- 4. Run Pre-Trade Risk Management ---
    is_trading_safe = run_risk_management_checks(portfolio)
    if not is_trading_safe:
        log("Trading halted due to risk management checks. Exiting run.")
        with open(config.PORTFOLIO_FILE, 'wb') as f:
            pickle.dump(portfolio, f)
        # Still print a valid JSON output for the frontend to handle gracefully
        error_output = {"error": "Trading halted due to risk management checks.", "portfolio_summary": portfolio.get_account_summary()}
        print(json.dumps(error_output, indent=4))
        return

    # --- 5. Get AI Decisions ---
    log("\n--- Consulting AI for Trading Decisions ---")
    ai_response_text = get_decision_from_openrouter(prompt)
    reasoning, structured_data = parse_ai_response(ai_response_text)
    
    decisions = structured_data.get('decisions', [])
    
    portfolio.record_trade_decision(prompt, reasoning, decisions)
    
    # --- 6. Execute AI Decisions ---
    execute_ai_decisions(portfolio, decisions, current_prices, correlation_matrix)

    # --- 7. Finalize and Generate Output for Frontend ---
    log("\n--- Generating Final Output ---")
    account_summary = portfolio.get_account_summary()
    detailed_positions = portfolio.get_detailed_positions()
    
    for position in detailed_positions:
        ai_decision = next((d for d in decisions if d.get('symbol') == position['coin']), None)
        position['exit_plan'] = ai_decision.get('exit_plan', 'N/A') if ai_decision else 'N/A'
    
    final_output = {
        "reasoning": reasoning,
        "decisions": decisions,
        "portfolio_summary": account_summary,
        "portfolio_positions": detailed_positions,
        "history": portfolio.value_history,
        "trade_history": portfolio.trade_history
    }
    
    # --- 8. Save Final Portfolio State for Next Run ---
    with open(config.PORTFOLIO_FILE, 'wb') as f:
        pickle.dump(portfolio, f)
    log("Portfolio state saved successfully. Run complete.")

    # This is now the ONLY print to standard output (stdout)
    print(json.dumps(final_output, indent=4))


if __name__ == "__main__":
    main()