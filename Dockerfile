# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Install system dependencies that might be needed by psycopg2 or other libraries
# python3-dev and libpq-dev are common for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container at /usr/src/app
COPY requirements.txt ./

# Install any needed packages specified in requirements.txt
# --no-cache-dir: Disables the cache to reduce image size
# --trusted-host pypi.python.org: Can be useful if there are SSL issues with PyPI
RUN pip install --no-cache-dir --trusted-host pypi.python.org -r requirements.txt

# Copy the rest of the application code into the container at /usr/src/app
# This includes the 'app' directory and any other necessary files at the root
COPY . .

# Make port 80 available to the world outside this container (if needed, e.g., for a web app)
# Not strictly necessary for this worker/scheduler app, but good practice if it ever exposes an API/health check.
# EXPOSE 80

# Define environment variables (can be overridden at runtime)
# For example, SCRIPT_MODE to control if the app runs once or starts the scheduler
ENV SCRIPT_MODE="schedule"
# Other ENV variables like DB connection details and API_KEY should be passed during 'docker run' or via docker-compose

# Command to run the application
# We run main.py from the app directory.
# If main.py is at the root, it would be `CMD ["python", "main.py"]`
# If main.py is inside app/, and app is a package, we might run it as a module
# For simplicity, assuming main.py is directly executable and handles its imports.
# The current main.py uses relative imports like `from . import currency_fetcher`,
# so it should be run as part of the 'app' package.
# `python -m app.main` executes app/main.py as a module.
CMD ["python", "-m", "app.main"]
