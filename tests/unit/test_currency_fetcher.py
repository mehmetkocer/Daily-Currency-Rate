import pytest
import os # Import os to get env variables
from unittest.mock import patch, MagicMock
import requests # Import requests for exception types

# Adjust the import path according to your project structure
# This assumes 'app' is a package and 'currency_fetcher' is a module within it.
# If your tests are run from the root directory, this should work.
from app import currency_fetcher

@pytest.fixture
def mock_env_api_key(monkeypatch):
    """Fixture to mock the CURRENCY_API_KEY environment variable."""
    monkeypatch.setenv("CURRENCY_API_KEY", "test_api_key")
    return "test_api_key" # Return the key for use in tests

def test_fetch_latest_rates_success(mock_env_api_key, mocker):
    """
    Test successful fetching and parsing of currency rates.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    # Consistent with API documentation: Unix timestamp for 'updated', direct rates
    mock_response.json.return_value = {
        "valid": True,
        "updated": 1609459200, # Example Unix timestamp for 2024-01-01T00:00:00Z
        "base": "USD",
        "rates": {
            "EUR": 0.9,
            "GBP": 0.8
        }
    }
    
    # Patch requests.get within the currency_fetcher module
    # Assign the mock to a variable to assert calls on it, more robustly
    mock_get = mocker.patch('app.currency_fetcher.requests.get', return_value=mock_response)
    
    result = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    
    assert "error" not in result
    assert result.get("updated") == 1609459200
    assert "EUR" in result.get("rates", {})
    assert result.get("rates", {}).get("EUR") == 0.9
    assert "GBP" in result.get("rates", {})
    assert result.get("rates", {}).get("GBP") == 0.8
    
    # Verify that requests.get was called correctly
    mock_get.assert_called_once_with(
        currency_fetcher.API_BASE_URL,
        params={"key": mock_env_api_key, "base": "USD"} # Corrected parameter names
    )

def test_fetch_latest_rates_api_error(mock_env_api_key, mocker):
    """
    Test handling of an API error (e.g., 401 Unauthorized).
    """
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error")

    mocker.patch('app.currency_fetcher.requests.get', return_value=mock_response)
    
    result = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    
    assert "error" in result
    assert result["status_code"] == 401
    currency_fetcher.requests.get.assert_called_once()

def test_fetch_latest_rates_connection_error(mock_env_api_key, mocker):
    """
    Test handling of a connection error.
    """
    mocker.patch('app.currency_fetcher.requests.get', side_effect=requests.exceptions.ConnectionError("Test Connection Error"))
    
    result = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    
    assert "error" in result
    assert "Connection error" in result["error"]
    currency_fetcher.requests.get.assert_called_once()

def test_fetch_latest_rates_json_decode_error(mock_env_api_key, mocker):
    """
    Test handling of a JSON decoding error.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Decoding JSON has failed")

    mocker.patch('app.currency_fetcher.requests.get', return_value=mock_response)
    
    result = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    
    assert "error" in result
    assert "JSON decode error" in result["error"]
    currency_fetcher.requests.get.assert_called_once()

def test_fetch_latest_rates_missing_updated_or_rates(mock_env_api_key, mocker):
    """
    Test handling of API response missing 'updated' or 'rates' keys (V1 structure).
    """
    mock_response_no_updated = MagicMock()
    mock_response_no_updated.status_code = 200
    mock_response_no_updated.json.return_value = {
        "valid": True,
        "base": "USD",
        "rates": {"EUR": 0.9} # Missing 'updated'
    }
    
    mock_response_no_rates = MagicMock()
    mock_response_no_rates.status_code = 200
    mock_response_no_rates.json.return_value = {
        "valid": True,
        "updated": 1609459200, # Has 'updated'
        "base": "USD" # Missing 'rates'
    }

    # Test with missing 'updated'
    mock_get_no_updated = mocker.patch('app.currency_fetcher.requests.get', return_value=mock_response_no_updated)
    result_no_updated = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    assert "error" not in result_no_updated # fetch_latest_rates returns the JSON as is
    assert result_no_updated.get("rates", {}).get("EUR") == 0.9
    assert "updated" not in result_no_updated
    mock_get_no_updated.assert_called_once()
    mock_get_no_updated.reset_mock() # Reset mock for the next call in the same test

    # Test with missing 'rates'
    mock_get_no_rates = mocker.patch('app.currency_fetcher.requests.get', return_value=mock_response_no_rates)
    result_no_rates = currency_fetcher.fetch_latest_rates(api_key=mock_env_api_key)
    assert "error" not in result_no_rates # fetch_latest_rates returns the JSON as is
    assert result_no_rates.get("updated") == 1609459200
    assert "rates" not in result_no_rates
    mock_get_no_rates.assert_called_once()

def test_fetch_latest_rates_no_api_key(mocker):
    """
    Test behavior when an empty or None API_KEY is passed.
    """
    mock_get = mocker.patch('app.currency_fetcher.requests.get')

    # Test with None API key
    result_none_key = currency_fetcher.fetch_latest_rates(api_key=None)
    assert "error" in result_none_key
    assert result_none_key["error"] == "API key not configured"
    mock_get.assert_not_called()

    # Test with empty string API key
    result_empty_key = currency_fetcher.fetch_latest_rates(api_key="")
    assert "error" in result_empty_key
    assert result_empty_key["error"] == "API key not configured"
    mock_get.assert_not_called() # Should still be not called in total for this test case
