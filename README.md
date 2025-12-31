# SentinelLM Streaming Pipeline

This project implements the streaming layer for SentinelLM, including a Kafka producer for generating synthetic agent events and a consumer for processing anomalies and sending them to Datadog.

## Setup

1.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration:**
    *   Copy `.env.example` to `.env`.
    *   Fill in your Confluent Cloud and Datadog credentials in `.env`.

## Components

### 1. Producer (`producer/producer.py`)
*   Generates synthetic events for the `agent_events` topic.
*   Uses Avro schema defined in `producer/agent_events.avsc`.
*   Simulates anomalies (Token runaway, Loop count) occasionally.

### 2. Datadog Consumer (`consumer/datadog_consumer.py`)
*   Consumes from the `anomalies` topic.
*   Deserializes Avro messages.
*   Sends events to Datadog.

## Usage

1.  **Start the Producer:**
    ```bash
    python producer/producer.py
    ```

2.  **Start the Consumer:**
    ```bash
    python consumer/datadog_consumer.py
    ```
