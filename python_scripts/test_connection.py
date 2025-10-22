import ccxt
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_binance_connection():
    try:
        # Print API key length (not the actual key) for verification
        api_key = os.environ.get('BINANCE_API_KEY')
        secret_key = os.environ.get('BINANCE_SECRET_KEY')
        print(f"API Key found (length: {len(api_key) if api_key else 'not found'})")
        print(f"Secret Key found (length: {len(secret_key) if secret_key else 'not found'})")
        
        # Initialize Binance client with debug mode
        binance = ccxt.binanceusdm({
            'apiKey': api_key,
            'secret': secret_key,
            'options': {
                'defaultType': 'future',
            },
            'verbose': True  # Enable debug mode
        })
        
        # Test basic market data (doesn't require authentication)
        print("\nTesting public API (no authentication required)...")
        ticker = binance.fetch_ticker('BTC/USDT')
        print(f"✓ BTC/USDT ticker retrieved: ${ticker['last']:,.2f}")
        
        # Test authenticated endpoint
        print("\nTesting authenticated API...")
        balance = binance.fetch_balance()
        print("✓ Successfully authenticated and retrieved balance")
        
        return True
        
    except ccxt.AuthenticationError as e:
        print(f"\n❌ Authentication Error: {str(e)}")
        print("Please check if your API keys are correct and have the proper permissions enabled.")
        return False
    except ccxt.NetworkError as e:
        print(f"\n❌ Network Error: {str(e)}")
        print("Please check your internet connection.")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected Error: {str(e)}")
        print("Please check the error message above and your API configuration.")
        return False

if __name__ == "__main__":
    test_binance_connection()