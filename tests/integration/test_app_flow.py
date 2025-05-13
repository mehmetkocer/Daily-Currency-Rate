import pytest
import os
from unittest.mock import patch
from datetime import datetime, timezone

# Assuming app.main, app.db_manager, app.currency_fetcher are accessible
# This might require specific PYTHONPATH setup or conftest.py in the tests directory
from app import main as app_main
from app import db_manager
from app import currency_fetcher

# These environment variables would need to be set for the integration test
# to connect to a real (or test-containerized) PostgreSQL instance.
# Example: export DB_HOST_TEST=localhost DB_USER_TEST=testuser ...
# For simplicity, we'll rely on the same .env variables the app uses,
# assuming the test environment is configured to point to a test DB.

@pytest.fixture(scope="module")
def db_connection_info():
    """Provides DB connection info, ensuring required env vars are set for tests."""
    required_vars = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "CURRENCY_API_KEY"]
    if not all(os.getenv(var) for var in required_vars):
        pytest.skip("Required environment variables for integration test DB not set. Skipping.")
    
    # Return a dummy value, the main point is the check above
    return {var: os.getenv(var) for var in required_vars}

@pytest.fixture(scope="function")
def setup_test_database(db_connection_info):
    """
    Ensures the database schema is initialized before each test function
    and cleans up (e.g., drops table or truncates) after.
    This version assumes the schema exists or will be created by the app job.
    A more robust version might create/drop a dedicated test DB or tables.
    """
    conn = db_manager.get_db_connection()
    if not conn:
        pytest.skip("Failed to connect to the database for setup. Skipping integration test.")
    
    try:
        # Ensure schema is there (idempotent)
        db_manager.initialize_schema(conn)
        
        # Clean up before test: delete all rows from currency_rates
        with conn.cursor() as cur:
            cur.execute("DELETE FROM currency_rates;")
        conn.commit()
        
        yield conn # Provide the connection to the test if needed
        
    finally:
        # Optional: Clean up after test, e.g., by truncating again or dropping tables
        # For this example, we'll rely on the next test run to clean.
        if conn:
            conn.close()


@patch('app.currency_fetcher.fetch_latest_rates')
def test_fetch_and_store_integration(mock_fetch_rates, db_connection_info, setup_test_database):
    """
    Integration test for the main flow: fetch (mocked) and store (real DB).
    """
    # Mock the API call to return predictable data (V1 structure)
    # Unix timestamp for 2024-03-10T00:00:00Z is 1709942400
    # Let's use a slightly different time for variety, e.g., 2024-03-10T08:00:00Z = 1709971200
    mocked_timestamp = 1709971200 
    expected_date_str = "2024-03-09"

    mock_fetch_rates.return_value = {
        "valid": True,
        "updated": mocked_timestamp,
        "base": "USD",
        "rates": {
            "EUR": 0.9123, # Direct rate value
            "JPY": 150.456  # Direct rate value
        }
    }

    # Run the main job function from app.main
    # This will use the real db_manager to interact with the database
    app_main.fetch_and_store_rates_job()

    # Verify the data was inserted into the database
    conn = db_manager.get_db_connection() # Get a new connection to check data
    assert conn is not None, "Failed to connect to DB for verification"
    
    try:
        with conn.cursor() as cur:
            # Check for EUR
            cur.execute("SELECT rate FROM currency_rates WHERE currency_code = %s AND date = %s;", ("EUR", expected_date_str))
            eur_row = cur.fetchone()
            assert eur_row is not None, f"EUR rate not found in DB for date {expected_date_str}"
            assert float(eur_row[0]) == 0.9123

            # Check for JPY
            cur.execute("SELECT rate FROM currency_rates WHERE currency_code = %s AND date = %s;", ("JPY", expected_date_str))
            jpy_row = cur.fetchone()
            assert jpy_row is not None, f"JPY rate not found in DB for date {expected_date_str}"
            assert float(jpy_row[0]) == 150.456
            
            # Check that only 2 rows were inserted for this test run for the specific date
            cur.execute("SELECT COUNT(*) FROM currency_rates WHERE date = %s;", (expected_date_str,))
            count_row = cur.fetchone()
            assert count_row[0] == 2, f"Expected 2 rows for date {expected_date_str}, found {count_row[0]}"
            
    finally:
        if conn:
            conn.close()

    # Verify that fetch_latest_rates was called
    mock_fetch_rates.assert_called_once()

# Example of how to run this test:
# 1. Ensure a PostgreSQL instance is running and accessible.
# 2. Set environment variables:
#    export DB_HOST=localhost
#    export DB_PORT=5432
#    export DB_NAME=test_currency_db
#    export DB_USER=testuser
#    export DB_PASSWORD=testpass
#    export CURRENCY_API_KEY=dummykey (as it's mocked)
# 3. Run pytest from the project root:
#    pytest tests/integration/test_app_flow.py
