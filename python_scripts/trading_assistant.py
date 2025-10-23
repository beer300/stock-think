# trading_assistant.py
import os
import requests
import json
import pickle
import re
from dotenv import load_dotenv
from prompt_generator import generate_prompt
from portfolio import SimulatedPortfolio

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
PORTFOLIO_FILE = 'simulated_portfolio.pkl'
HIGH_CORRELATION_THRESHOLD = 0.7

def get_decision_from_openrouter(prompt: str):
    """
    Sends the generated prompt to the OpenRouter API and returns the AI's response.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY not found in .env file."

    # The detailed instructions for the AI model
    system_instruction = (
        "You are an expert trading analyst. Your task is to think step-by-step to arrive at the best trading decisions. "
        "First, you MUST write your entire analysis, thought process, and reasoning inside a <thinking> XML block. "
        "This is for your internal monologue and will be displayed to the user as your thought process. "
        "After the closing </thinking> tag, you MUST provide your final structured output inside a <json_output> XML block. "
        "This block must contain a single valid JSON object with two keys: 'decisions' and 'portfolio'.\n"
        "The 'decisions' key must be a list of JSON objects, one for each symbol. Each object must have:\n"
        "  - 'symbol': The base coin symbol (e.g., 'BTC').\n"
        "  - 'action': 'BUY', 'SELL', or 'HOLD'.\n"
        "  - 'quantity': The number of coins to trade. Must be 0 for HOLD.\n"
        "  - 'confidence': 'High', 'Medium', or 'Low'.\n"
        "  - 'exit_plan': A brief strategy for this position (e.g., 'Sell if price drops to $65k or rises to $75k').\n"
        "The 'portfolio' key is a list of objects for all currently held assets, including all fields from the prompt.\n"
        "Example final output format:\n"
        "<json_output>\n"
        "{\n"
        '  "decisions": [\n'
        '    {"symbol": "BTC", "action": "BUY", "quantity": 0.01, "confidence": "High", "exit_plan": "Target $75,000, stop-loss at $68,000"},\n'
        '    {"symbol": "ETH", "action": "HOLD", "quantity": 0, "confidence": "Medium", "exit_plan": "Monitor for breakout above $4,200"}\n'
        '  ],\n'
        '  "portfolio": [\n'
        '    {"side": "LONG", "coin": "DOGE", "leverage": "1x", "notional": "$1,200.50", "unreal_pnl": "$50.25", "exit_plan": "Target $0.20"}\n'
        '  ]\n'
        "}\n"
        "</json_output>"
    )

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,  # Increased to handle the large context from the detailed prompt
        "temperature": 0.5,
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        return f"Error communicating with OpenRouter API: {e}"
    except (KeyError, IndexError) as e:
        return f"Error parsing response from OpenRouter: {e}\nResponse: {response.text}"


def parse_ai_response(response_text):
    """
    Parses the full AI response string to separate the <thinking> block (reasoning)
    from the <json_output> block (structured decisions).
    """
    reasoning = "No <thinking> block found in the AI response."
    json_data = {"decisions": [], "portfolio": []}

    # Use regex to find the content within the XML tags
    thinking_match = re.search(r'<thinking>([\s\S]*?)<\/thinking>', response_text)
    if thinking_match:
        reasoning = thinking_match.group(1).strip()

    json_match = re.search(r'<json_output>([\s\S]*?)<\/json_output>', response_text)
    if json_match:
        json_string = json_match.group(1).strip()
        try:
            json_data = json.loads(json_string)
        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Malformed JSON string received from AI: {json_string}")
            # Return an empty structure to prevent crashes
            json_data = {"decisions": [], "portfolio": [], "error": "Failed to decode AI JSON output."}
    
    return reasoning, json_data

if __name__ == "__main__":
    # --- 1. Load or Initialize Portfolio ---
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'rb') as f:
            portfolio = pickle.load(f)
    else:
        portfolio = SimulatedPortfolio()
    
    # --- 2. Generate Prompt with Comprehensive Market Data ---
    full_prompt, market_data_full, correlation_matrix = generate_prompt(portfolio)
    
    # Create a simplified dictionary of current prices for frequent use
    current_prices = {s: d['current_price'] for s, d in market_data_full.items() if d}

    # --- 3. Pre-Trade Risk Management Checks ---
    
    # A. Hard Stop-Loss Check: Automatically exit positions that have lost too much.
    print("\n--- Checking for Hard Stop-Losses ---")
    # Iterate over a copy of positions to allow modification during the loop
    current_positions = portfolio.get_detailed_positions(current_prices)
    for position in current_positions:
        symbol_pair = f"{position['coin']}/USDT"
        price = current_prices.get(symbol_pair)
        if not price: continue
        
        entry_price = position['entry_price']
        stop_loss_price = entry_price * (1 - portfolio.hard_stop_loss_threshold)
        
        if price < stop_loss_price:
            print(f"!!! HARD STOP-LOSS TRIGGERED FOR {position['coin']} at ${price:.2f} (Entry: ${entry_price:.2f})")
            portfolio.sell(symbol_pair, position['quantity'], price, reason="Hard Stop-Loss")

    # B. Maximum Drawdown Circuit Breaker: Halt all trading if the portfolio value drops significantly.
    print("\n--- Checking for Maximum Drawdown ---")
    total_value = portfolio.get_total_value(current_prices)
    drawdown = (portfolio.peak_value - total_value) / portfolio.peak_value if portfolio.peak_value > 0 else 0
    
    if drawdown > portfolio.max_drawdown_threshold:
        portfolio.circuit_breaker_tripped = True
        print(f"!!! MAX DRAWDOWN >{portfolio.max_drawdown_threshold*100}%. CIRCUIT BREAKER TRIPPED! HALTING TRADING. !!!")
    
    # Update portfolio value history and peak value after all checks
    portfolio.record_value_history(total_value)

    # Exit script if circuit breaker is tripped
    if portfolio.circuit_breaker_tripped:
        print("Trading is halted due to the circuit breaker. No new decisions will be made.")
        with open(PORTFOLIO_FILE, 'wb') as f: pickle.dump(portfolio, f)
        exit()

    # --- 4. Get AI Decisions ---
    print("\n--- Consulting AI for Trading Decisions ---")
    ai_response_text = get_decision_from_openrouter(full_prompt)
    reasoning, structured_data = parse_ai_response(ai_response_text)
    
    # Record the trade decision with prompt and reasoning
    portfolio.record_trade_decision(full_prompt, reasoning, structured_data.get('decisions', []))
    
    # --- 5. Execute AI Decisions with Final Checks ---
    decisions = structured_data.get('decisions', [])
    if decisions:
        print("\n--- Executing AI Decisions ---")
        for decision in decisions:
            symbol_base = decision.get('symbol')
            if not symbol_base: continue
            
            symbol_pair = f"{symbol_base}/USDT"
            action = decision.get('action', '').upper()
            
            try:
                quantity = float(decision.get('quantity', 0))
                if quantity < 1e-9 and action != 'HOLD': continue
            except (ValueError, TypeError): continue

            if symbol_pair in current_prices:
                price = current_prices[symbol_pair]
                if action == 'BUY':
                    # C. Correlation Check: Prevent buying assets that are too similar to existing ones.
                    is_highly_correlated = False
                    if not correlation_matrix.empty and symbol_base in correlation_matrix:
                        held_symbols = list(portfolio.positions.keys())
                        if held_symbols:
                            # Check correlation against all currently held assets
                            correlations = correlation_matrix[symbol_base].loc[held_symbols]
                            for held_symbol, corr_value in correlations.items():
                                if corr_value > HIGH_CORRELATION_THRESHOLD:
                                    print(f"SKIPPING BUY of {symbol_base}: Highly correlated ({corr_value:.2f}) with held asset {held_symbol}.")
                                    is_highly_correlated = True
                                    break
                    if not is_highly_correlated:
                         portfolio.buy(symbol_pair, quantity, price)

                elif action == 'SELL':
                    portfolio.sell(symbol_pair, quantity, price, reason="AI Decision")

    # --- 6. Finalize and Output State for Frontend ---
    print("\n--- Generating Final Output ---")
    account_summary = portfolio.get_account_summary(current_prices)
    detailed_positions = portfolio.get_detailed_positions(current_prices)
    
    # Add the AI's exit plan to the position details for display
    for position in detailed_positions:
        ai_decision = next((d for d in decisions if d.get('symbol') == position['coin']), None)
        position['exit_plan'] = ai_decision.get('exit_plan', 'N/A') if ai_decision else 'N/A'
    
    final_output = {
        "reasoning": reasoning,
        "decisions": decisions,
        "portfolio_summary": account_summary,
        "portfolio_positions": detailed_positions,
        "history": portfolio.value_history,
        "trade_history": portfolio.trade_history  # Include the trade history in the output
    }
    
    # Print the final JSON to be consumed by a frontend application
    print(json.dumps(final_output, indent=4))

    # --- 7. Save Portfolio State for Next Run ---
    with open(PORTFOLIO_FILE, 'wb') as f:
        pickle.dump(portfolio, f)