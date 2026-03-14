FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY openclaw/ openclaw/
COPY config/ config/

# Install the package
RUN pip install --no-cache-dir .

# Create data directory for persistent state
RUN mkdir -p /app/data

# Run the agent
CMD ["openclaw"]
