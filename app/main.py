import logging
import os
from datetime import datetime, date as DDate, timezone # Alias to avoid conflict with datetime.date, import timezone
import time

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Assuming currency_fetcher and db_manager are in the same 'app' directory
from . import currency_fetcher
from . import db_manager

# Load environment variables from .env file
load_dotenv()

# Configure basic logging
logger = logging.getLogger("DailyCurrencyRateApp")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def fetch_and_store_rates_job():
    """
    The main job to be scheduled: fetches currency rates and stores them in the database.
    """
    logger.info("Starting daily currency rate fetch and store job...")

    api_key = os.getenv("CURRENCY_API_KEY")
    if not api_key:
        logger.error("CURRENCY_API_KEY not found in environment. Job cannot run.")
        return

    # 1. Fetch currency rates
    logger.info("Fetching latest currency rates...")
    rates_data = currency_fetcher.fetch_latest_rates(api_key=api_key, base_currency="USD")

    if "error" in rates_data:
        logger.error(f"Failed to fetch currency rates: {rates_data['error']}")
        if "details" in rates_data:
            logger.error(f"Details: {rates_data['details']}")
        return
    
    if "rates" not in rates_data or not isinstance(rates_data["rates"], dict): # Check for 'rates' key
        logger.error(f"Fetched rates data is not in the expected format or 'rates' key is missing: {rates_data}")
        return

    # Determine the date for the rates from the 'updated' timestamp.
    record_timestamp = rates_data.get("updated")
    logger.info(f"Raw 'updated' timestamp from API: {record_timestamp}") # Log raw timestamp
    if record_timestamp:
        try:
            int_timestamp = int(record_timestamp)
            logger.info(f"Integer-converted timestamp: {int_timestamp}") # Log int timestamp
            # Use timezone-aware datetime conversion
            record_date = datetime.fromtimestamp(int_timestamp, timezone.utc).date()
        except (ValueError, TypeError):
            logger.warning(f"Could not parse date from API 'updated' timestamp: {record_timestamp}. Using current UTC date.")
            record_date = datetime.now(timezone.utc).date()
    else:
        logger.warning("No 'updated' timestamp in API response. Using current UTC date.")
        record_date = datetime.now(timezone.utc).date()

    # 2. Store rates in database
    db_conn = None
    try:
        logger.info("Connecting to the database...")
        db_conn = db_manager.get_db_connection()
        if db_conn:
            logger.info("Initializing database schema (if needed)...")
            db_manager.initialize_schema(db_conn) # Idempotent

            logger.info(f"Inserting rates for date: {record_date}...")
            # inserted_count = 0
            # skipped_count = 0
            for currency_code, rate_value in rates_data["rates"].items(): # Iterate through 'rates'
                try:
                    # Rate value is directly available
                    db_manager.insert_currency_rate(db_conn, record_date, currency_code, float(rate_value))
                    # insert_currency_rate handles its own logging for success/skip/failure per item
                except ValueError:
                    logger.error(f"Could not convert rate '{rate_value}' to float for currency {currency_code}. Skipping.")
                except Exception as e:
                    logger.error(f"Error processing or inserting rate for {currency_code}: {e}")
            
            logger.info("Finished processing rates for insertion.")

    except Exception as e:
        logger.error(f"An error occurred in the database operations: {e}")
    finally:
        if db_conn:
            db_conn.close()
            logger.info("Database connection closed.")
    
    logger.info("Daily currency rate fetch and store job finished.")


def run_application_logic():
    """Handles the main application startup logic: run once or schedule."""
    # Simplified startup for now: run the job once if SCRIPT_MODE is 'run_once', otherwise start scheduler.
    script_mode = os.getenv("SCRIPT_MODE", "schedule").lower()

    if script_mode == "run_once":
        logger.info("SCRIPT_MODE is 'run_once'. Running the job immediately.")
        fetch_and_store_rates_job()
        logger.info("Job finished. Exiting.")
    elif script_mode == "schedule":
        logger.info("SCRIPT_MODE is 'schedule'. Scheduler is active.")
        scheduler = BlockingScheduler(timezone="UTC")
        scheduler.add_job(fetch_and_store_rates_job, 'cron', hour=6, minute=0)
        logger.info("Job scheduled daily at 06:00 UTC. Press Ctrl+C to exit.")
        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped.")
    else:
        logger.error(f"Invalid SCRIPT_MODE: {script_mode}. Set to 'run_once' or 'schedule'.")

if __name__ == "__main__":
    logger.info("Application starting...")
    run_application_logic()
    # For immediate testing without waiting for the scheduler:
    # run_once = os.getenv("RUN_ONCE", "false").lower() == "true"
    # if run_once:
    #     logger.info("RUN_ONCE is true. Running the job immediately.")
    #     fetch_and_store_rates_job()
    # else:
    #     logger.info("Scheduler is active. Job will run at configured time.")
    #     scheduler = BlockingScheduler(timezone="UTC")
    #     # Schedule job to run every day at 06:00 UTC
    #     scheduler.add_job(fetch_and_store_rates_job, 'cron', hour=6, minute=0)
    #     logger.info("Job scheduled daily at 06:00 UTC. Press Ctrl+C to exit.")
    #     try:
    #         scheduler.start()
    #     except (KeyboardInterrupt, SystemExit):
    #         logger.info("Scheduler stopped.")
    #     try:
    #         scheduler.start()
    #     except (KeyboardInterrupt, SystemExit):
    #         logger.info("Scheduler stopped.")
