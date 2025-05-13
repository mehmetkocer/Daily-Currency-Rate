import os
import requests
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_BASE_URL = "https://currencyapi.net/api/v1/rates"
API_KEY = os.getenv("CURRENCY_API_KEY")

def fetch_latest_rates(api_key: str, base_currency: str = "USD") -> dict:
    """
    Fetches the latest currency rates from the currency API.

    Args:
        api_key (str): The API key for authentication.
        base_currency (str): The base currency for the rates (e.g., "USD").

    Returns:
        dict: A dictionary containing the API response data if successful,
              or an error message dictionary if an error occurs.
    """
    if not api_key:
        logging.error("API key is not configured. Please set CURRENCY_API_KEY environment variable.")
        return {"error": "API key not configured"}

    params = {
        "key": api_key,
        "base": base_currency
        # 'output': 'JSON' is default, so not strictly needed here
    }

    try:
        response = requests.get(API_BASE_URL, params=params)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        data = response.json()
        logging.info(f"Successfully fetched rates for base currency: {base_currency}")
        return data
    except requests.exceptions.HTTPError as http_err:
        logging.error(f"HTTP error occurred: {http_err} - {response.text}")
        return {"error": f"HTTP error: {http_err}", "status_code": response.status_code, "details": response.text}
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"Connection error occurred: {conn_err}")
        return {"error": f"Connection error: {conn_err}"}
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"Timeout error occurred: {timeout_err}")
        return {"error": f"Timeout error: {timeout_err}"}
    except requests.exceptions.RequestException as req_err:
        logging.error(f"An unexpected error occurred with the request: {req_err}")
        return {"error": f"Unexpected request error: {req_err}"}
    except ValueError as json_err: # Includes JSONDecodeError
        logging.error(f"Failed to decode JSON response: {json_err}")
        return {"error": f"JSON decode error: {json_err}"}

if __name__ == "__main__":
    # This is for basic testing of the fetcher
    # Ensure your .env file has CURRENCY_API_KEY set
    if not API_KEY:
        print("CURRENCY_API_KEY not found in environment variables. Please set it in your .env file.")
    else:
        print(f"Attempting to fetch rates with API Key: {API_KEY[:5]}...") # Print only a part of the key
        rates_data = fetch_latest_rates(api_key=API_KEY)
        if "error" in rates_data:
            print(f"Error fetching rates: {rates_data['error']}")
            if "details" in rates_data:
                print(f"Details: {rates_data['details']}")
        elif "rates" in rates_data: # Changed from "data" to "rates"
            print(f"Base currency: {rates_data.get('base')}")
            if "updated" in rates_data:
                from datetime import datetime
                print(f"Rates updated at (timestamp): {rates_data['updated']}")
                print(f"Rates updated at (UTC): {datetime.utcfromtimestamp(rates_data['updated']).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print("Sample of fetched rates:")
            for currency, rate_value in list(rates_data["rates"].items())[:5]: # Iterate through 'rates'
                print(f"  {currency}: {rate_value}") # Print rate value directly
        else:
            print("Fetched data structure is not as expected or 'rates' key is missing.")
            print(rates_data)
