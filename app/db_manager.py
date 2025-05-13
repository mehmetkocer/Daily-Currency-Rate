import os
import psycopg2
import logging
from datetime import date
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "5432") # Default PostgreSQL port
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        logging.info("Successfully connected to the PostgreSQL database.")
        return conn
    except psycopg2.OperationalError as e:
        logging.error(f"Error connecting to PostgreSQL: {e}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred during DB connection: {e}")
        raise

def initialize_schema(conn):
    """
    Initializes the database schema by creating the currency_rates table if it doesn't exist.
    Adds a unique constraint on (date, currency_code).
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS currency_rates (
                    id SERIAL PRIMARY KEY,
                    date DATE NOT NULL,
                    currency_code VARCHAR(10) NOT NULL, -- Increased length
                    rate DECIMAL NOT NULL
                );
            """)
            
            # Check and alter column type if necessary (for existing tables)
            cur.execute("""
                SELECT data_type, character_maximum_length
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'currency_rates'
                  AND column_name = 'currency_code';
            """)
            column_info = cur.fetchone()
            if column_info:
                current_type, current_length = column_info
                # Check if it's varchar and length is 3
                if current_type == 'character varying' and current_length == 3:
                    logging.info("Altering currency_code column from VARCHAR(3) to VARCHAR(10)...")
                    cur.execute("""
                        ALTER TABLE currency_rates
                        ALTER COLUMN currency_code TYPE VARCHAR(10);
                    """)
                    logging.info("Successfully altered currency_code column type to VARCHAR(10).")
                elif current_type == 'character varying' and current_length == 10:
                    logging.info("currency_code column is already VARCHAR(10).")
                else:
                    logging.info(f"currency_code column type is {current_type}({current_length}), not altering.")

            # Add unique constraint if it doesn't exist
            # Check if constraint exists
            cur.execute("""
                SELECT conname 
                FROM pg_constraint 
                WHERE conrelid = 'currency_rates'::regclass 
                AND conname = 'uq_date_currency_code';
            """)
            if not cur.fetchone():
                cur.execute("""
                    ALTER TABLE currency_rates
                    ADD CONSTRAINT uq_date_currency_code UNIQUE (date, currency_code);
                """)
                logging.info("Added unique constraint uq_date_currency_code to currency_rates table.")
            else:
                logging.info("Unique constraint uq_date_currency_code already exists on currency_rates table.")
            
            conn.commit()
            logging.info("Database schema initialized successfully (currency_rates table created/verified).")
    except Exception as e:
        logging.error(f"Error initializing schema: {e}")
        conn.rollback() # Rollback in case of error
        raise

def insert_currency_rate(conn, record_date: date, currency_code: str, rate: float):
    """
    Inserts a new currency rate into the database.
    Handles potential duplicate entries by doing nothing if the constraint is violated.
    """
    sql = """
        INSERT INTO currency_rates (date, currency_code, rate)
        VALUES (%s, %s, %s)
        ON CONFLICT (date, currency_code) DO NOTHING; 
        -- ON CONFLICT DO NOTHING handles duplicates gracefully based on the unique constraint
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (record_date, currency_code, rate))
            conn.commit()
            if cur.rowcount > 0:
                logging.info(f"Inserted rate for {currency_code} on {record_date}: {rate}")
            else:
                logging.info(f"Rate for {currency_code} on {record_date} already exists. Skipped insertion.")
    except Exception as e:
        logging.error(f"Error inserting currency rate for {currency_code} on {record_date}: {e}")
        conn.rollback()
        raise

if __name__ == "__main__":
    
    if not all([DB_HOST, DB_NAME, DB_USER, DB_PASSWORD]):
        print("Database connection details not found in environment variables. Please set them in your .env file.")
    else:
        print("Attempting to connect to database and initialize schema...")
        connection = None
        try:
            connection = get_db_connection()
            if connection:
                initialize_schema(connection)
                
                # Example insertion (idempotent due to ON CONFLICT)
                print("\nAttempting to insert sample data...")
                from datetime import datetime
                today_date = datetime.utcnow().date()
                
                insert_currency_rate(connection, today_date, "EUR", 0.92)
                insert_currency_rate(connection, today_date, "GBP", 0.79)
                # Try inserting the same EUR rate again to test ON CONFLICT
                insert_currency_rate(connection, today_date, "EUR", 0.92) 
                
                print("\nFetching a few records to verify (manual check):")
                with connection.cursor() as cur:
                    cur.execute("SELECT date, currency_code, rate FROM currency_rates ORDER BY id DESC LIMIT 5;")
                    records = cur.fetchall()
                    if records:
                        for record in records:
                            print(f"  Date: {record[0]}, Code: {record[1]}, Rate: {record[2]}")
                    else:
                        print("  No records found in currency_rates table.")

        except Exception as e:
            print(f"An error occurred during DB manager testing: {e}")
        finally:
            if connection:
                connection.close()
                logging.info("Database connection closed.")
