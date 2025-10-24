# /services/ai_service.py
import requests
import json
import re
from utils import config

def get_decision_from_openrouter(prompt: str) -> str:
    """
    Sends the generated prompt to the OpenRouter API and returns the AI's raw response string.

    Args:
        prompt: The complete, formatted prompt string containing all market and portfolio data.

    Returns:
        The raw string content from the AI model's response.
    """
    if not config.OPENROUTER_API_KEY:
        error_message = "Error: OPENROUTER_API_KEY not found in the environment."
        print(error_message)
        # Return a structured error response that the parser can handle
        return f"<thinking>{error_message}</thinking><json_output>{json.dumps({'decisions': [], 'error': error_message})}</json_output>"

    # The detailed instructions for the AI model on how to think and what format to respond in.
    # This system instruction is critical for getting reliable, structured output.
    system_instruction = (
        "You are an expert trading analyst. Your task is to think step-by-step to arrive at the best trading decisions. "
        "First, you MUST write your entire analysis, thought process, and reasoning inside a <thinking> XML block. "
        "This is for your internal monologue and will be displayed to the user as your thought process. "
        "After the closing </thinking> tag, you MUST provide your final structured output inside a <json_output> XML block. "
        "This block must contain a single valid JSON object with one key: 'decisions'.\n"
        "The 'decisions' key must be a list of JSON objects, one for each symbol. Each object must have:\n"
        "  - 'symbol': The base coin symbol (e.g., 'BTC').\n"
        "  - 'action': 'BUY', 'SELL', or 'HOLD'.\n"
        "  - 'quantity': The number of coins to trade. Must be 0 for HOLD.\n"
        "  - 'confidence': 'High', 'Medium', or 'Low'.\n"
        "  - 'exit_plan': A brief strategy for this position (e.g., 'Sell if price drops to $65k or rises to $75k').\n"
        "Example final output format:\n"
        "<json_output>\n"
        "{\n"
        '  "decisions": [\n'
        '    {"symbol": "BTC", "action": "BUY", "quantity": 0.01, "confidence": "High", "exit_plan": "Target $75,000, stop-loss at $68,000"},\n'
        '    {"symbol": "ETH", "action": "HOLD", "quantity": 0, "confidence": "Medium", "exit_plan": "Monitor for breakout above $4,200"}\n'
        '  ]\n'
        "}\n"
        "</json_output>"
    )

    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "deepseek/deepseek-chat",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
        "temperature": 0.5,
    }

    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, data=json.dumps(data))
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        return response.json()['choices'][0]['message']['content']
    except requests.exceptions.RequestException as e:
        error_message = f"Error communicating with OpenRouter API: {e}"
        print(error_message)
        return f"<thinking>{error_message}</thinking><json_output>{json.dumps({'decisions': [], 'error': error_message})}</json_output>"
    except (KeyError, IndexError) as e:
        error_message = f"Error parsing response from OpenRouter: {e}\nResponse: {response.text}"
        print(error_message)
        return f"<thinking>{error_message}</thinking><json_output>{json.dumps({'decisions': [], 'error': error_message})}</json_output>"


def parse_ai_response(response_text: str) -> tuple[str, dict]:
    """
    Parses the full AI response string to separate the <thinking> block (reasoning)
    from the <json_output> block (structured decisions).

    Args:
        response_text: The raw string response from the AI model.

    Returns:
        A tuple containing:
        - The reasoning string.
        - The structured data dictionary from the JSON output.
    """
    # Default values in case parsing fails
    reasoning = "No <thinking> block found or response was invalid."
    structured_data = {"decisions": []}

    # Use regex to find the content within the XML tags (case-insensitive and multiline)
    thinking_match = re.search(r'<thinking>([\s\S]*?)<\/thinking>', response_text, re.IGNORECASE | re.DOTALL)
    if thinking_match:
        reasoning = thinking_match.group(1).strip()

    json_match = re.search(r'<json_output>([\s\S]*?)<\/json_output>', response_text, re.IGNORECASE | re.DOTALL)
    if json_match:
        json_string = json_match.group(1).strip()
        try:
            # Attempt to parse the extracted JSON string
            structured_data = json.loads(json_string)
        except json.JSONDecodeError as e:
            error_msg = f"AI response contained malformed JSON."
            print(f"JSON Decode Error: {e}")
            print(f"Malformed JSON string from AI: {json_string}")
            # Ensure reasoning contains the error and return an empty structure to prevent crashes
            reasoning += f"\n\n--- PARSING ERROR ---\n{error_msg}"
            structured_data = {"decisions": [], "error": error_msg}
    else:
        reasoning += "\n\n--- PARSING ERROR ---\nNo <json_output> block found in the AI response."

    return reasoning, structured_data