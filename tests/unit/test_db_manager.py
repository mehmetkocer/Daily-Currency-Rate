import pytest
from unittest.mock import patch, MagicMock, call
import psycopg2 # For exception types

# Adjust the import path according to your project structure
from app import db_manager

# mock_env_db_credentials fixture is removed as patching is done directly in tests.

@pytest.fixture
def mock_db_connection(mocker):
    """Fixture to mock the database connection and cursor."""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mocker.patch('app.db_manager.psycopg2.connect', return_value=mock_conn)
    # Mock the __enter__ and __exit__ methods for the cursor context manager
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.__exit__.return_value = None
    return mock_conn, mock_cursor

def test_get_db_connection_success(mocker, mock_db_connection): # Removed mock_env_db_credentials
    """Test successful database connection."""
    conn_fixture, _ = mock_db_connection

    # Patch module-level variables in db_manager
    mocker.patch('app.db_manager.DB_HOST', 'testhost')
    mocker.patch('app.db_manager.DB_PORT', '5432')
    mocker.patch('app.db_manager.DB_NAME', 'testdb')
    mocker.patch('app.db_manager.DB_USER', 'testuser')
    mocker.patch('app.db_manager.DB_PASSWORD', 'testpass')
    
    # Call the function that uses psycopg2.connect
    actual_conn = db_manager.get_db_connection()
    
    # Assert that psycopg2.connect was called with the correct parameters
    db_manager.psycopg2.connect.assert_called_once_with(
        host="testhost",
        port="5432",
        dbname="testdb",
        user="testuser",
        password="testpass"
    )
    assert actual_conn == conn_fixture # Ensure the mocked connection is returned

def test_get_db_connection_failure(mocker): # Removed mock_env_db_credentials
    """Test database connection failure."""
    # Patch module-level variables for completeness, though connection will fail before using them fully
    mocker.patch('app.db_manager.DB_HOST', 'testhost_fail')
    mocker.patch('app.db_manager.DB_PORT', '1234')
    mocker.patch('app.db_manager.DB_NAME', 'testdb_fail')
    mocker.patch('app.db_manager.DB_USER', 'testuser_fail')
    mocker.patch('app.db_manager.DB_PASSWORD', 'testpass_fail')

    mocker.patch('app.db_manager.psycopg2.connect', side_effect=psycopg2.OperationalError("Connection failed"))
    
    with pytest.raises(psycopg2.OperationalError, match="Connection failed"):
        db_manager.get_db_connection()
    
    db_manager.psycopg2.connect.assert_called_once() # Check it was attempted

def test_initialize_schema_success_constraint_exists(mock_db_connection):
    """Test schema initialization when constraint already exists."""
    conn, cursor = mock_db_connection
    
    # Simulate the column type check - assume it's already VARCHAR(10)
    # The first fetchone is for column info, second for constraint check (constraint exists)
    cursor.fetchone.side_effect = [('character varying', 10), (1,)]
    
    db_manager.initialize_schema(conn)
    
    # Check that CREATE TABLE IF NOT EXISTS is called
    # Exact SQL string from app/db_manager.py, including leading newline and indentation
    # Reflects the current implementation with VARCHAR(10)
    create_table_sql_exact = """
                CREATE TABLE IF NOT EXISTS currency_rates (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    currency_code VARCHAR(10) NOT NULL, -- Increased length
                    rate DECIMAL NOT NULL
                );
            """
    
    # Simulate the column type check - assume it's already VARCHAR(10) or doesn't need alteration
    # Check that the query to check for constraint existence is called
    # Exact SQL string from app/db_manager.py
    check_constraint_sql_exact = """
                SELECT conname 
                FROM pg_constraint 
                WHERE conrelid = 'currency_rates'::regclass 
                AND conname = 'uq_date_currency_code';
            """
        
    cursor.execute.assert_any_call(create_table_sql_exact)
    cursor.execute.assert_any_call(check_constraint_sql_exact)
    
    # Ensure ADD CONSTRAINT is NOT called
    add_constraint_sql = "ALTER TABLE currency_rates ADD CONSTRAINT uq_date_currency_code UNIQUE (date, currency_code);"
    for executed_call in cursor.execute.call_args_list:
        # Ensure the SQL string being executed is not the add_constraint_sql
        # executed_call[0] is the args tuple, executed_call[0][0] is the first arg (sql string)
        assert executed_call.args[0].strip() != add_constraint_sql.strip()
        
    conn.commit.assert_called_once()
    # cursor.close is handled by context manager, not called directly on mock

def test_initialize_schema_success_constraint_does_not_exist(mock_db_connection):
    """Test schema initialization when constraint does not exist."""
    conn, cursor = mock_db_connection
    
    # Simulate the column type check - assume it's already VARCHAR(10)
    # The first fetchone is for column info, second for constraint check (constraint doesn't exist here)
    cursor.fetchone.side_effect = [('character varying', 10), None]
    
    db_manager.initialize_schema(conn)
    
    # Exact SQL strings from app/db_manager.py
    # Reflects the current implementation with VARCHAR(10)
    create_table_sql_exact = """
                CREATE TABLE IF NOT EXISTS currency_rates (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    currency_code VARCHAR(10) NOT NULL, -- Increased length
                    rate DECIMAL NOT NULL
                );
            """

    check_constraint_sql_exact = """
                SELECT conname 
                FROM pg_constraint 
                WHERE conrelid = 'currency_rates'::regclass 
                AND conname = 'uq_date_currency_code';
            """
    add_constraint_sql_exact = """
                    ALTER TABLE currency_rates
                    ADD CONSTRAINT uq_date_currency_code UNIQUE (date, currency_code);
                """

    # Check calls
    cursor.execute.assert_any_call(create_table_sql_exact)
    cursor.execute.assert_any_call(check_constraint_sql_exact)
    cursor.execute.assert_any_call(add_constraint_sql_exact)
    
    conn.commit.assert_called_once()
    # cursor.close is handled by context manager

def test_initialize_schema_alter_column_type(mock_db_connection):
    """Test schema initialization correctly alters column type from VARCHAR(3) to VARCHAR(10)."""
    conn, cursor = mock_db_connection

    # Simulate column is VARCHAR(3) and constraint does not exist
    cursor.fetchone.side_effect = [
        ('character varying', 3), # First fetchone for column info
        None                     # Second fetchone for constraint check
    ]

    db_manager.initialize_schema(conn)

    # Exact SQL for altering column
    alter_column_sql_exact = """
                        ALTER TABLE currency_rates
                        ALTER COLUMN currency_code TYPE VARCHAR(10);
                    """
    # Exact SQL for adding constraint
    add_constraint_sql_exact = """
                    ALTER TABLE currency_rates
                    ADD CONSTRAINT uq_date_currency_code UNIQUE (date, currency_code);
                """
    
    # Check that ALTER COLUMN is called
    cursor.execute.assert_any_call(alter_column_sql_exact)
    # Check that ADD CONSTRAINT is also called (as per mock setup)
    cursor.execute.assert_any_call(add_constraint_sql_exact)
    
    conn.commit.assert_called_once()

def test_initialize_schema_db_error_on_create(mock_db_connection):
    """Test schema initialization with a DB error during CREATE TABLE."""
    conn, cursor = mock_db_connection
    cursor.execute.side_effect = [psycopg2.Error("Create table failed"), None, None] # Fail on first execute

    with pytest.raises(psycopg2.Error, match="Create table failed"):
      db_manager.initialize_schema(conn)
    
    cursor.execute.assert_called_once() # Should fail on the first call (CREATE TABLE)
    conn.rollback.assert_called_once()
    # cursor.close is handled by context manager

def test_initialize_schema_db_error_on_add_constraint(mock_db_connection):
    """Test schema initialization with a DB error during ADD CONSTRAINT."""
    conn, cursor = mock_db_connection
    # Simulate constraint does not exist initially
    # First execute (CREATE TABLE) is fine
    # Second execute (check constraint) is fine, returns None
    # Third execute (ADD CONSTRAINT) fails
    cursor.fetchone.return_value = None 
    
    def execute_side_effect(sql, params=None):
        if "ADD CONSTRAINT" in sql:
            raise psycopg2.Error("Add constraint failed")
        return MagicMock() # Default for other calls

    cursor.execute.side_effect = execute_side_effect
    
    with pytest.raises(psycopg2.Error, match="Add constraint failed"):
        db_manager.initialize_schema(conn)
        
    conn.rollback.assert_called_once()
    # cursor.close is handled by context manager


def test_insert_currency_rate_success(mock_db_connection):
    """Test successful insertion of a currency rate."""
    conn, cursor = mock_db_connection
    cursor.rowcount = 1 # Simulate a successful insertion
    
    test_date = "2024-01-01"
    test_code = "EUR"
    test_rate = 0.9123
    
    db_manager.insert_currency_rate(conn, test_date, test_code, test_rate)
    
    # Exact SQL string from app/db_manager.py, including leading newline, indentation, and comment
    expected_sql_exact = """
        INSERT INTO currency_rates (date, currency_code, rate)
        VALUES (%s, %s, %s)
        ON CONFLICT (date, currency_code) DO NOTHING; 
        -- ON CONFLICT DO NOTHING handles duplicates gracefully based on the unique constraint
    """
    cursor.execute.assert_called_once_with(
        expected_sql_exact, # Use the exact string
        (test_date, test_code, test_rate)
    )
    conn.commit.assert_called_once()
    # cursor.close is handled by context manager

def test_insert_currency_rate_skipped_due_to_conflict(mock_db_connection):
    """Test when insertion is skipped due to ON CONFLICT DO NOTHING."""
    conn, cursor = mock_db_connection
    cursor.rowcount = 0 # Simulate no rows affected (conflict occurred)

    test_date = "2024-01-02"
    test_code = "GBP"
    test_rate = 0.88

    db_manager.insert_currency_rate(conn, test_date, test_code, test_rate)

    # Exact SQL string from app/db_manager.py
    expected_sql_exact = """
        INSERT INTO currency_rates (date, currency_code, rate)
        VALUES (%s, %s, %s)
        ON CONFLICT (date, currency_code) DO NOTHING; 
        -- ON CONFLICT DO NOTHING handles duplicates gracefully based on the unique constraint
    """
    cursor.execute.assert_called_once_with(
        expected_sql_exact, # Use the exact string
        (test_date, test_code, test_rate)
    )
    conn.commit.assert_called_once() # Commit is still called

def test_insert_currency_rate_db_error(mock_db_connection):
    """Test currency rate insertion with a database error."""
    conn, cursor = mock_db_connection
    cursor.execute.side_effect = psycopg2.Error("Insert failed")
    
    with pytest.raises(psycopg2.Error, match="Insert failed"): # Match the specific error
        db_manager.insert_currency_rate(conn, "2024-01-01", "USD", 1.0)
        
    conn.rollback.assert_called_once()
    # cursor.close is handled by context manager
