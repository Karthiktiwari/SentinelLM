import os
import time
import uuid
import random
import json
from dotenv import load_dotenv
from confluent_kafka import SerializingProducer
from confluent_kafka.serialization import StringSerializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

# Load environment variables
load_dotenv()

# Configuration
BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS")
SASL_USERNAME = os.getenv("SASL_USERNAME")
SASL_PASSWORD = os.getenv("SASL_PASSWORD")
SCHEMA_REGISTRY_URL = os.getenv("SCHEMA_REGISTRY_URL")
SCHEMA_REGISTRY_API_KEY = os.getenv("SCHEMA_REGISTRY_API_KEY")
SCHEMA_REGISTRY_API_SECRET = os.getenv("SCHEMA_REGISTRY_API_SECRET")

TOPIC = "agent_events"
SCHEMA_FILE = "producer/agent_events.avsc"

def get_schema_registry_client():
    conf = {
        'url': SCHEMA_REGISTRY_URL,
        'basic.auth.user.info': f"{SCHEMA_REGISTRY_API_KEY}:{SCHEMA_REGISTRY_API_SECRET}"
    }
    return SchemaRegistryClient(conf)

def get_producer(schema_registry_client, schema_str):
    avro_serializer = AvroSerializer(schema_registry_client, schema_str)

    producer_conf = {
        'bootstrap.servers': BOOTSTRAP_SERVERS,
        'security.protocol': 'SASL_SSL',
        'sasl.mechanisms': 'PLAIN',
        'sasl.username': SASL_USERNAME,
        'sasl.password': SASL_PASSWORD,
        'key.serializer': StringSerializer('utf_8'),
        'value.serializer': avro_serializer
    }
    return SerializingProducer(producer_conf)

def load_schema():
    with open(SCHEMA_FILE, 'r') as f:
        return f.read()

def generate_event():
    agent_id = f"agent-{random.randint(1, 5)}"
    node_name = f"node-{random.choice(['A', 'B', 'C', 'D'])}"
    model_name = random.choice(["gemini-pro", "deepseek", "gemini-flash"])
    
    return {
        "trace_id": str(uuid.uuid4()),
        "request_id": str(uuid.uuid4()),
        "model_name": model_name,
        "agent_id": agent_id,
        "node_name": node_name,
        "deployment_version": "v1.2.0",
        "step_index": random.randint(1, 10),
        "tokens_used": random.randint(10, 1000),
        "latency_ms": random.randint(100, 2000),
        "ts": int(time.time() * 1000)
    }

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed for User record {msg.key()}: {err}")
    else:
        # print(f"User record {msg.key()} successfully produced to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
        pass

def main():
    if not BOOTSTRAP_SERVERS:
        print("Error: Environment variables not set. Please check .env file.")
        return

    print("Initializing producer...")
    schema_str = load_schema()
    sr_client = get_schema_registry_client()
    producer = get_producer(sr_client, schema_str)

    print(f"Producing events to {TOPIC}...")
    try:
        while True:
            event = generate_event()
            # Trigger some anomalies occasionally
            if random.random() < 0.05:
                event['tokens_used'] = random.randint(5000, 10000) # Token runaway
                print(f"⚠️ Generated Token Runaway: {event['tokens_used']} tokens")
            
            if random.random() < 0.05:
                event['step_index'] = random.randint(50, 100) # Loop count anomaly
                print(f"⚠️ Generated Loop Anomaly: {event['step_index']} steps")
            
            if random.random() < 0.05:
                event['latency_ms'] = random.randint(5000, 10000) # Latency spike
                print(f"⚠️ Generated Latency Spike: {event['latency_ms']} ms")
            
            # Ensure key is string
            key = str(event['agent_id'])
            
            producer.produce(topic=TOPIC, key=key, value=event, on_delivery=delivery_report)
            producer.poll(0)
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping producer...")
    finally:
        producer.flush()

if __name__ == "__main__":
    main()
