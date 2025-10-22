# python_scripts/main.py
import os
import requests
import json
import pickle
import re
from dotenv import load_dotenv
from prompt_generator import generate_prompt, SYMBOLS
from portfolio import SimulatedPortfolio

load_dotenv()

PORTFOLIO_FILE = 'simulated_portfolio.pkl'

def get_decision_from_openrouter(prompt: str):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "Error: OPENROUTER_API_KEY not found."

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
        "max_tokens": 2048,
        "temperature": 0.5,
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        return f"Error communicating with OpenRouter API: {e}"
    except (KeyError, IndexError) as e:
        return f"Error parsing response from OpenRouter: {e}\nResponse: {response.text}"


def parse_ai_response(response_text):
    """Parses the AI's response to separate reasoning from the structured JSON output."""
    reasoning = "No <thinking> block found."
    json_data = {"decisions": [], "portfolio": []}

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
            print(f"Malformed JSON string: {json_string}")
            # Return empty structure on error to avoid frontend crash
            json_data = {"decisions": [], "portfolio": [], "error": "Failed to decode AI JSON output."}
    
    return reasoning, json_data

if __name__ == "__main__":
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, 'rb') as f:
            portfolio = pickle.load(f)
    else:
        portfolio = SimulatedPortfolio()
        portfolio.record_value_history(portfolio.initial_cash)

    full_prompt, market_data = generate_prompt(portfolio)
    ai_response_text = get_decision_from_openrouter(full_prompt)
    reasoning, structured_data = parse_ai_response(ai_response_text)
    
    decisions = structured_data.get('decisions', [])
    if decisions:
        for decision in decisions:
            symbol_base = decision.get('symbol')
            if not symbol_base: continue
            
            symbol_pair = f"{symbol_base}/USDT"
            action = decision.get('action', '').upper()
            
            try:
                quantity = float(decision.get('quantity', 0))
                if quantity < 1e-9 and action != 'HOLD':
                    continue
            except (ValueError, TypeError):
                continue

            if symbol_pair in market_data:
                current_price = market_data[symbol_pair]['current_price']
                if action == 'BUY':
                    portfolio.buy(symbol_pair, quantity, current_price)
                elif action == 'SELL':
                    portfolio.sell(symbol_pair, quantity, current_price)

    final_prices = {symbol: data['current_price'] for symbol, data in market_data.items()}
    account_summary = portfolio.get_account_summary(final_prices)
    detailed_positions = portfolio.get_detailed_positions(final_prices)
    
    # Update positions with AI's exit plan if available
    for position in detailed_positions:
        ai_decision = next((d for d in decisions if d.get('symbol') == position['coin']), None)
        position['exit_plan'] = ai_decision.get('exit_plan', 'N/A') if ai_decision else 'N/A'

    total_value = float(re.sub(r'[^\d.]', '', account_summary.get("Current Account Value", "0")))
    portfolio.record_value_history(total_value)

    # --- Final JSON Output for Frontend ---
    final_output = {
        "reasoning": reasoning,
        "decisions": decisions,
        "portfolio_summary": account_summary,
        "portfolio_positions": detailed_positions,
        "history": portfolio.value_history
    }
    
    print(json.dumps(final_output, indent=4))

    with open(PORTFOLIO_FILE, 'wb') as f:
        pickle.dump(portfolio, f)