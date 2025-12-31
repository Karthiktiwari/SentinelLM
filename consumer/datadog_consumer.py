import os
import json
import time
import requests
from dotenv import load_dotenv
from confluent_kafka import DeserializingConsumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import StringDeserializer

# Load environment variables
load_dotenv()

# Configuration
BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS")
SASL_USERNAME = os.getenv("SASL_USERNAME")
SASL_PASSWORD = os.getenv("SASL_PASSWORD")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
SCHEMA_REGISTRY_API_KEY = os.getenv("SCHEMA_REGISTRY_API_KEY")
SCHEMA_REGISTRY_API_SECRET = os.getenv("SCHEMA_REGISTRY_API_SECRET")

DD_API_KEY = os.getenv("DD_API_KEY")
DD_SITE = os.getenv("DD_SITE", "datadoghq.com")

TOPIC = "anomalies"
GROUP_ID = "datadog-consumer-group"

def get_schema_registry_client():
    conf = {
        'url': SCHEMA_REGISTRY_URL,
        'basic.auth.user.info': f"{SCHEMA_REGISTRY_API_KEY}:{SCHEMA_REGISTRY_API_SECRET}"
    }
    return SchemaRegistryClient(conf)

def send_to_datadog(event):
    url = f"https://api.{DD_SITE}/api/v1/events"
    headers = {
        "Content-Type": "application/json",
        "DD-API-KEY": DD_API_KEY
    }
    
    # Construct Datadog event
    title = "SentinelLM Anomaly Detected"
    text = f"Anomaly detected for agent {event.get('agent_id', 'unknown')}.\nDetails: {json.dumps(event, indent=2, default=str)}"
    
    payload = {
        "title": title,
        "text": text,
        "alert_type": "error",
        "source_type_name": "sentinellm",
        "tags": [
            "source:sentinellm",
            f"agent:{event.get('agent_id', 'unknown')}",
            f"model:{event.get('model_name', 'unknown')}"
        ]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 202:
            print("Event sent to Datadog successfully.")
        else:
            print(f"Failed to send event to Datadog: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Error sending to Datadog: {e}")

def main():
    if not BOOTSTRAP_SERVERS or not DD_API_KEY:
        print("Error: Environment variables not set. Please check .env file.")
        return

    sr_client = get_schema_registry_client()
    # We use a generic AvroDeserializer. 
    # Note: In a real app, you might want to pass the specific schema or use a specific reader.
    # For now, we assume the writer schema is sufficient (default behavior).
    avro_deserializer = AvroDeserializer(sr_client)
    string_deserializer = StringDeserializer('utf_8')

    consumer_conf = {
        'bootstrap.servers': BOOTSTRAP_SERVERS,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': SASL_USERNAME,
        'sasl.password': SASL_PASSWORD,
        'key.deserializer': string_deserializer,
        'value.deserializer': avro_deserializer,
        'group.id': GROUP_ID,
        'auto.offset.reset': 'earliest'
    }

    consumer = DeserializingConsumer(consumer_conf)
    consumer.subscribe([TOPIC])

    print(f"Consuming from {TOPIC}...")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                print(f"Consumer error: {msg.error()}")
                continue

            event = msg.value()
            print(f"Received anomaly: {event}")
            send_to_datadog(event)

    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
