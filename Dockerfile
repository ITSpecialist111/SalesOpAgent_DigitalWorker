# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy the current directory contents into the container at /app
COPY . /app

# Install dependencies
# We use pip to install the package in editable mode or just requirements
# If pyproject.toml exists, pip install . works
RUN pip install --no-cache-dir .

# Patch SDK version mismatch: agent_framework renamed ChatAgent -> Agent
# and uses 'client' instead of 'chat_client' as the first parameter.
# The A365 tooling extensions v0.1.0 still references the old name.
RUN python scripts/patch_sdk.py

# Expose port (if serving HTTP)
EXPOSE 8000

# Define environment variable
ENV PYTHONUNBUFFERED=1

# Run the application
# Use the generic host entry point (host_agent_server.py with correct SDK imports)
CMD ["python", "src/start_with_generic_host.py"]
