import pytest
from unittest.mock import patch, MagicMock, call
from datetime import datetime, timezone

# Adjust the import path according to your project structure
from app import main
from app import db_manager # To mock its functions
from app import currency_fetcher # To mock its functions

# Mock environment variables for db_manager and currency_fetcher if they are accessed globally
# For main.py, SCRIPT_MODE is key.
@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch):
    """Mock environment variables needed by sub-modules if not already mocked by specific tests."""
    monkeypatch.setenv("CURRENCY_API_KEY", "fake_api_key_for_main_tests")
    monkeypatch.setenv("DB_HOST", "main_testhost")
    monkeypatch.setenv("DB_PORT", "main_5432")
    monkeypatch.setenv("DB_NAME", "main_testdb")
    monkeypatch.setenv("DB_USER", "main_testuser")
    monkeypatch.setenv("DB_PASSWORD", "main_testpass")

@pytest.fixture
def mock_db_connection_main(mocker):
    """Fixture to mock db_manager's get_db_connection and initialize_schema for main.py tests."""
    mock_conn = MagicMock()
    mocker.patch('app.db_manager.get_db_connection', return_value=mock_conn)
    mocker.patch('app.db_manager.initialize_schema') # Assume success
    mocker.patch('app.db_manager.insert_currency_rate') # Assume success
    return mock_conn

@pytest.fixture
def mock_currency_fetcher_main(mocker):
    """Fixture to mock currency_fetcher.fetch_latest_rates for main.py tests."""
    mock_fetch = mocker.patch('app.currency_fetcher.fetch_latest_rates')
    return mock_fetch

def test_fetch_and_store_rates_job_success(mock_db_connection_main, mock_currency_fetcher_main):
    """Test the main job with successful fetch and store."""
    mock_conn = mock_db_connection_main
    
    # V1 API structure
    mock_api_response = {
        "valid": True,
        "updated": 1610697000, # Unix timestamp for 2024-01-15T10:30:00Z
        "base": "USD",
        "rates": {
            "EUR": 0.9,
            "GBP": 0.8
        }
    }
    mock_currency_fetcher_main.return_value = mock_api_response
    
    main.fetch_and_store_rates_job()
    
    # Verify fetcher was called
    mock_currency_fetcher_main.assert_called_once()
    
    # Verify DB connection and schema initialization
    db_manager.get_db_connection.assert_called_once()
    db_manager.initialize_schema.assert_called_once_with(mock_conn)
    
    # Verify insert_currency_rate calls
    expected_date_obj = datetime.fromtimestamp(mock_api_response["updated"], timezone.utc).date()
    calls = [
        call(mock_conn, expected_date_obj, "EUR", 0.9), # Direct rate value
        call(mock_conn, expected_date_obj, "GBP", 0.8)  # Direct rate value
    ]
    db_manager.insert_currency_rate.assert_has_calls(calls, any_order=True)
    assert db_manager.insert_currency_rate.call_count == 2
    
    mock_conn.close.assert_called_once()

def test_fetch_and_store_rates_job_fetch_returns_none(mock_db_connection_main, mock_currency_fetcher_main):
    """Test job when currency_fetcher returns an error dictionary."""
    mock_conn = mock_db_connection_main # This mock_conn won't be used if job exits early
    # Mock returns an error dictionary
    mock_currency_fetcher_main.return_value = {"error": "API communication failed"}
    
    main.fetch_and_store_rates_job()
    
    mock_currency_fetcher_main.assert_called_once()
    # If fetch fails and job returns, these should not be called
    db_manager.get_db_connection.assert_not_called()
    db_manager.initialize_schema.assert_not_called()
    db_manager.insert_currency_rate.assert_not_called()
    mock_conn.close.assert_not_called() # db_conn would be None in job


def test_fetch_and_store_rates_job_no_updated_timestamp_from_api(mock_db_connection_main, mock_currency_fetcher_main, mocker):
    """Test job when API response doesn't provide 'updated' timestamp, should use current date."""
    mock_conn = mock_db_connection_main
    # V1 API structure, but missing 'updated' key
    mock_api_response = {
        "valid": True,
        "base": "USD",
        "rates": {"USD": 1.0}
    }
    mock_currency_fetcher_main.return_value = mock_api_response

    # Mock datetime.now(timezone.utc) to control current date
    fixed_now_utc = datetime(2024, 1, 16, 12, 0, 0, tzinfo=timezone.utc)
    # We need to mock datetime object within app.main specifically
    # and ensure its 'now' method returns our fixed_now_utc when called with timezone.utc
    mock_datetime = MagicMock()
    mock_datetime.now.return_value = fixed_now_utc
    mock_datetime.fromtimestamp = datetime.fromtimestamp # Keep original fromtimestamp
    mock_datetime.UTC = timezone.utc # Ensure UTC is available if needed by other parts of the mocked datetime
    
    mocker.patch('app.main.datetime', mock_datetime)
    mocker.patch('app.main.timezone', timezone) # Ensure the original timezone object is used

    main.fetch_and_store_rates_job()

    expected_date_obj = fixed_now_utc.date() # From mocked datetime.now(timezone.utc)
    # Check that insert_currency_rate was called with the rate from the "rates" dictionary
    db_manager.insert_currency_rate.assert_called_once_with(
        mock_conn, expected_date_obj, "USD", 1.0 # Direct rate value
    )
    mock_conn.close.assert_called_once()

def test_fetch_and_store_rates_job_db_connection_fails(mock_currency_fetcher_main, mocker):
    """Test job when getting a DB connection fails."""
    # Simulate successful fetch with V1 structure
    mock_currency_fetcher_main.return_value = {
        "valid": True,
        "updated": 1609459200, # Example Unix timestamp
        "base": "USD",
        "rates": {"USD": 1.0}
    }
    
    mocker.patch('app.db_manager.get_db_connection', return_value=None) # DB connection fails
    mock_initialize_schema = mocker.patch('app.db_manager.initialize_schema')
    mock_insert_rate = mocker.patch('app.db_manager.insert_currency_rate')
    
    main.fetch_and_store_rates_job()
    
    mock_currency_fetcher_main.assert_called_once() 
    db_manager.get_db_connection.assert_called_once()
    mock_initialize_schema.assert_not_called()
    mock_insert_rate.assert_not_called()

@patch('app.main.BlockingScheduler')
@patch.dict('os.environ', {'SCRIPT_MODE': 'run_once'})
def test_main_run_once_mode(mock_scheduler_constructor): # Removed unused db/fetcher mocks
    """Test SCRIPT_MODE='run_once' executes job directly, no schedule."""
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    
    with patch('app.main.fetch_and_store_rates_job') as mock_job:
        main.run_application_logic() # Call the new refactored function
        mock_job.assert_called_once()
        
    mock_scheduler_instance.add_job.assert_not_called()
    mock_scheduler_instance.start.assert_not_called()

@patch('app.main.BlockingScheduler')
@patch('app.main.fetch_and_store_rates_job') # Patch at method level
@patch.dict('os.environ', {'SCRIPT_MODE': 'schedule'}) 
def test_main_schedule_mode(mock_fetch_job_patch, mock_scheduler_constructor): # Renamed mock_fetch_job
    """Test SCRIPT_MODE='schedule' schedules job and starts scheduler."""
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    
    main.run_application_logic() # Call the new refactored function
    
    mock_fetch_job_patch.assert_not_called() # The job itself is not called directly by run_application_logic

    mock_scheduler_instance.add_job.assert_called_once_with(
        mock_fetch_job_patch, # Assert add_job was called with the mock object
        'cron',
        hour=6,
        minute=0
        # timezone="UTC" is set in BlockingScheduler constructor in app.main
    )
    mock_scheduler_instance.start.assert_called_once()

@patch('app.main.BlockingScheduler')
@patch('app.main.fetch_and_store_rates_job') # Patch at method level
@patch.dict('os.environ', {}, clear=True) 
def test_main_default_schedule_mode(mock_fetch_job_patch, mock_scheduler_constructor): # Renamed mock_fetch_job
    """Test default SCRIPT_MODE (not set) schedules job and starts scheduler."""
    mock_scheduler_instance = mock_scheduler_constructor.return_value
    
    main.run_application_logic() # Call the new refactored function

    mock_fetch_job_patch.assert_not_called() # The job itself is not called directly

    mock_scheduler_instance.add_job.assert_called_once_with(
        mock_fetch_job_patch, # Assert add_job was called with the mock object
        'cron',
        hour=6,
        minute=0
        # timezone="UTC" is set in BlockingScheduler constructor in app.main
    )
    mock_scheduler_instance.start.assert_called_once()
