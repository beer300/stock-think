# main.py
import os
import requests
import json
import pickle # <--- IMPORT PICKLE
from dotenv import load_dotenv

# Import our separated classes and functions
from prompt_generator import generate_prompt, SYMBOLS
from portfolio import SimulatedPortfolio

# Load environment variables from .env file
load_dotenv()

# Define the file path for saving the portfolio state
PORTFOLIO_FILE = 'simulated_portfolio.pkl'

def get_decision_from_openrouter(prompt: str):
    # (This function remains unchanged)
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY not found in environment variables."

    system_instruction = (
        "You are an expert trading analyst. Your task is to think step-by-step to arrive at the best trading decisions. "
        "First, you MUST write your entire analysis, thought process, and reasoning inside a <thinking> XML block. "
        "Inside this block, analyze each symbol's intraday and long-term data, consider the current portfolio, and formulate a strategy. "
        "After the closing </thinking> tag, and only then, provide your final decisions. "
        "Your final output MUST follow this strict format for each symbol on four consecutive lines:\n"
        "SYMBOL\n"
        "ACTION\n"
        "CONFIDENCE\n"
        "QUANTITY: [value]\n\n"
        "RULES FOR FINAL OUTPUT:\n"
        "- The ACTION must be BUY, SELL, or HOLD.\n"
        "- The QUANTITY must be a calculated number of coins, not a percentage or dollar amount.\n"
        "- For HOLD actions, the quantity must be 0."
    )
    
    headers = { "Authorization": f"Bearer {api_key}", "Content-Type": "application/json" }
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 1000,
        "temperature": 0.5,
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        response_json = response.json()
        return response_json['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        return f"Error communicating with OpenRouter API: {e}"
    except (KeyError, IndexError) as e:
        return f"Error parsing response from OpenRouter: {e}\nResponse: {response.text}"

def parse_decision_with_reasoning(decision_text):
    # (This function remains unchanged)
    reasoning = "No reasoning block found."
    try:
        start_tag = "<thinking>"
        end_tag = "</thinking>"
        start_index = decision_text.find(start_tag)
        end_index = decision_text.find(end_tag)
        
        if start_index != -1 and end_index != -1:
            reasoning = decision_text[start_index + len(start_tag):end_index].strip()
            decision_part = decision_text[end_index + len(end_tag):].strip()
        else:
            decision_part = decision_text
            
    except Exception:
        decision_part = decision_text

    lines = [line.strip() for line in decision_part.strip().split('\n') if line.strip()]
    if not lines:
        return reasoning, "No decisions found after reasoning.", []
    
    summary = lines[0] if not lines[0] in [s.split('/')[0] for s in SYMBOLS] else "Executing trades based on analysis."
    structured_data = []
    
    i = 1 if summary == lines[0] else 0
    
    while i < len(lines):
        try:
            if lines[i] in [s.split('/')[0] for s in SYMBOLS]:
                symbol, action, confidence, quantity_str = lines[i], lines[i+1], lines[i+2], lines[i+3]
                quantity = quantity_str.split(':')[1].strip()
                
                structured_data.append({
                    "symbol": symbol, "action": action,
                    "confidence": confidence, "quantity": quantity
                })
                i += 4
            else:
                i += 1
        except (IndexError, ValueError):
            break

    return reasoning, summary, structured_data

def display_results(reasoning, summary, decisions):
    # (This function remains unchanged)
    print("\n" + "="*80)
    print("AI TRADING ASSISTANT (DeepSeek via OpenRouter)".center(80))
    print("="*80)
    print("\n--- AI'S THOUGHT PROCESS ---")
    print(reasoning)
    print("\n--- STRATEGY SUMMARY ---")
    print(f"  {summary}\n")
    if not decisions:
        print("No structured decisions were parsed from the AI's response.")
        return
    print("--- FINAL DECISIONS ---")
    header = f"| {'SYMBOL':<10} | {'ACTION':<15} | {'CONFIDENCE':<15} | {'QUANTITY':<20} |"
    separator = "-" * len(header)
    print(separator)
    print(header)
    print(separator)
    for d in decisions:
        row = f"| {d['symbol']:<10} | {d['action']:<15} | {d['confidence']:<15} | {d['quantity']:<20} |"
        print(row)
    print(separator)
    print("\n")

# --- Main Execution ---
if __name__ == "__main__":
    # --- LOAD OR CREATE PORTFOLIO ---
    if os.path.exists(PORTFOLIO_FILE):
        print(f"Loading existing portfolio from '{PORTFOLIO_FILE}'...")
        with open(PORTFOLIO_FILE, 'rb') as f:
            portfolio = pickle.load(f)
        print("Portfolio loaded successfully.")
    else:
        print(f"No portfolio file found. Creating a new one.")
        portfolio = SimulatedPortfolio()

    print("\n1. Generating prompt with latest market data...")
    full_prompt, market_data = generate_prompt(portfolio)

    print("\n2. Sending prompt to OpenRouter to elicit reasoning...")
    ai_response = get_decision_from_openrouter(full_prompt)

    print("\n3. Parsing and displaying the reasoning and decisions...")
    reasoning, summary, structured_decisions = parse_decision_with_reasoning(ai_response)
    display_results(reasoning, summary, structured_decisions)
    
    print("\n4. Executing simulated trades...")
    if structured_decisions:
        for decision in structured_decisions:
            symbol_base = decision['symbol']
            symbol_pair = f"{symbol_base}/USDT"
            action = decision['action'].upper()
            
            try:
                quantity = float(decision['quantity'])
                if quantity == 0 and action != 'HOLD':
                    print(f"Warning: Quantity is 0 for a {action} action on {symbol_base}. Skipping.")
                    continue
            except ValueError:
                print(f"Warning: Could not parse quantity '{decision['quantity']}' for {symbol_base}. Skipping.")
                continue

            if symbol_pair in market_data:
                current_price = market_data[symbol_pair]['current_price']
                if action == 'BUY':
                    portfolio.buy(symbol_pair, quantity, current_price)
                elif action == 'SELL':
                    portfolio.sell(symbol_pair, quantity, current_price)
            else:
                print(f"Market data not available for {symbol_pair}. Cannot execute trade.")

    print("\n5. Final Portfolio Status...")
    # Get final prices for the most up-to-date valuation
    final_prices = {symbol: data['current_price'] for symbol, data in market_data.items()}
    final_account_details = portfolio.get_account_details(final_prices)
    for key, value in final_account_details.items():
        print(f"{key}: {value}")
    
    # --- SAVE THE UPDATED PORTFOLIO ---
    with open(PORTFOLIO_FILE, 'wb') as f:
        pickle.dump(portfolio, f)
    print(f"\nPortfolio state has been saved to '{PORTFOLIO_FILE}'.")
    print("\n")