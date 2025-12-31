#!/bin/bash

# Load environment variables from .env
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | awk '/=/ {print $1}')
fi

# Check if DD_API_KEY is set
if [ -z "$DD_API_KEY" ]; then
    echo "Error: DD_API_KEY is not set in .env"
    exit 1
fi

echo "Starting SentinelLM Dashboard..."
# Running without ddtrace-run to avoid connection errors if Datadog Agent is missing.
# Custom events (anomalies) will still be sent to Datadog via the API.
streamlit run app.py
