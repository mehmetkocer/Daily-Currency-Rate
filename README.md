# Daily Currency Rate Application

This project is a Python application that fetches daily currency exchange rates from the [currencyapi.net](https://currencyapi.net) API and stores them in a PostgreSQL database. The application is containerized using Docker and managed with Docker Compose. It includes a CI/CD pipeline using GitHub Actions for automated building and testing.

For a detailed explanation of the architecture, design decisions, and setup instructions, please see the [Solution Design Document](SOLUTION_DESIGN.md).

## Features

*   Daily fetching of currency rates (scheduled for 06:00 UTC).
*   Storage of historical currency rates in PostgreSQL.
*   Rates are stored against a base currency (default USD) to facilitate USD equivalent calculations.
*   Containerized application and database using Docker and Docker Compose.
*   Automated CI/CD pipeline for builds and tests using GitHub Actions.
*   Unit and integration tests to ensure code quality.

## Project Structure

```
.
├── .github/workflows/         # GitHub Actions CI/CD pipeline
│   └── ci_cd.yml
├── app/                       # Core Python application logic
│   ├── __init__.py
│   ├── currency_fetcher.py    # Fetches data from currency API
│   ├── db_manager.py          # Manages database interactions
│   └── main.py                # Main application script with scheduler
├── notes/                     # Project planning and progress (not part of runtime)
│   ├── progress.md
│   └── project_plan.md
├── tests/                     # Unit and integration tests
│   ├── __init__.py
│   ├── integration/
│   │   ├── __init__.py
│   │   └── test_app_flow.py
│   └── unit/
│       ├── __init__.py
│       ├── test_currency_fetcher.py
│       ├── test_db_manager.py
│       └── test_main.py
├── .env.example               # Example environment variables file
├── .gitignore                 # Specifies intentionally untracked files
├── docker-compose.yml         # Docker Compose configuration
├── Dockerfile                 # Dockerfile for the Python application
├── README.md                  # This file
├── requirements.txt           # Python dependencies
├── SOLUTION_DESIGN.md         # Detailed solution architecture and guide
├── task-description.md        # Original task requirements
└── pytest.ini                 # Pytest configuration
```

## Prerequisites

*   [Docker](https://docs.docker.com/get-docker/)
*   [Docker Compose](https://docs.docker.com/compose/install/)
*   [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

## Quick Start (Local Development)

1.  **Clone the repository:**
    ```bash
    git clone <your-repository-url>
    cd Daily-Currency-Rate
    ```

2.  **Set up environment variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and provide your `CURRENCY_API_KEY` and other configurations as needed. The default database credentials in `.env.example` and `docker-compose.yml` are suitable for local startup.
        ```dotenv
        CURRENCY_API_KEY=YOUR_ACTUAL_API_KEY_HERE
        DB_HOST=db
        DB_PORT=5432
        DB_NAME=mydatabase
        DB_USER=user
        DB_PASSWORD=password
        SCRIPT_MODE=schedule # 'schedule' or 'run_once'
        # For testing locally (see "Running Tests" section):
        # DB_HOST_TEST=localhost
        # DB_PORT_TEST=5432 # Ensure this matches the host port mapped in docker-compose.yml for the db service
        # DB_NAME_TEST=testdb
        # DB_USER_TEST=testuser
        # DB_PASSWORD_TEST=testpassword
        ```

3.  **Build and run the application using Docker Compose:**
    ```bash
    docker-compose up --build -d
    ```
    This will build the Python application image (if not already built or if changes were made) and start both the `app` and `db` services in detached mode.

4.  **View logs:**
    *   Application logs:
        ```bash
        docker-compose logs -f app
        ```
    *   Database logs:
        ```bash
        docker-compose logs -f db
        ```

5.  **Stop the application:**
    ```bash
    docker-compose down
    ```
    To also remove the database volume (all data will be lost):
    ```bash
    docker-compose down -v
    ```

## Running Tests

Tests are written using `pytest`.

1.  **Install test dependencies** (if you haven't already, or if running outside a CI environment where they are installed):
    ```bash
    pip install -r requirements.txt 
    ```
    (This step is primarily if you intend to run `pytest` directly on your host. The CI pipeline handles this within its environment.)

2.  **Unit Tests:**
    These tests mock external dependencies and can be run without a live database or API access.
    ```bash
    pytest tests/unit
    ```

3.  **Integration Tests:**
    These tests require a running PostgreSQL instance. The CI pipeline (`.github/workflows/ci_cd.yml`) sets up a service container for this.
    To run locally:
    *   Ensure the database service from `docker-compose.yml` is running:
        ```bash
        docker-compose up -d db
        ```
    *   Set the required environment variables for the test database connection (see `.env.example` or the `SOLUTION_DESIGN.md` for details on `DB_HOST_TEST`, etc., ensuring they point to the `db` service, typically `localhost` and the mapped port if accessing from the host).
        Example for bash/zsh (if your `docker-compose.yml` maps port `5432` of the `db` service to `5432` on the host):
        ```bash
        export DB_HOST=localhost 
        export DB_PORT=5432      
        export DB_NAME=mydatabase # The DB name used by the 'db' service
        export DB_USER=user       # The user for the 'db' service
        export DB_PASSWORD=password # The password for the 'db' service
        export CURRENCY_API_KEY="dummy_key" # API is mocked in integration tests
        export SCRIPT_MODE="run_once"
        ```
    *   Run the integration tests:
        ```bash
        pytest tests/integration
        ```

4.  **Manual Script Execution for Testing:**
    You can also manually trigger the main application script in `run_once` mode to test its execution flow with the configured environment (e.g., to check database interaction or API fetching if not mocked). This is useful for quick checks outside the formal test suites.
    ```bash
    docker-compose exec -e SCRIPT_MODE=run_once app python -m app.main
    ```

## CI/CD Pipeline

The project uses GitHub Actions for CI/CD, defined in `.github/workflows/ci_cd.yml`. The pipeline automates building, testing, and deploying the application. It includes the following jobs:

*   **Build Job (`build`):**
    *   Builds the Docker image for the Python application.
    *   Pushes the image to GitHub Container Registry (GHCR) on pushes to the `main` branch or when manually triggered via `workflow_dispatch`.
    *   Tags images with `latest` and the commit SHA.

*   **Test Job (`test`):**
    *   Runs after the `build` job.
    *   Sets up a PostgreSQL service container (`postgres:13-alpine`) for integration tests.
    *   Installs Python dependencies.
    *   Executes both unit tests and integration tests using `pytest`.

*   **Deploy to Development Job (`deploy_development`):**
    *   Runs after successful `build` and `test` jobs.
    *   Automatically triggers on pushes to the `main` branch.
    *   Deploys the application to a development server. This involves:
        *   Setting up SSH to the development server.
        *   Copying the `docker-compose.yml` file.
        *   Creating an `.env` file on the server with development-specific configurations.
        *   Pulling the newly built Docker image.
        *   Updating the image tag in `docker-compose.yml` on the server.
        *   Running `docker-compose up` to start/update the application.
        *   Pruning old Docker images.

*   **Deploy to Production Job (`deploy_production`):**
    *   Runs after successful `build` and `test` jobs.
    *   Triggered manually via `workflow_dispatch`.
    *   Deploys the application to a production server. The process is similar to the development deployment but uses production-specific configurations and server details.

## Detailed Documentation

For more in-depth information on the project's architecture, setup, deployment, and design decisions, please refer to the [SOLUTION_DESIGN.md](SOLUTION_DESIGN.md) file.
