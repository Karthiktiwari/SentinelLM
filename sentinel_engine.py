import os
import time
import uuid
import random
import json
import threading
import queue
from dotenv import load_dotenv
from confluent_kafka import SerializingProducer, DeserializingConsumer
from confluent_kafka.serialization import StringSerializer, StringDeserializer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer, AvroDeserializer
import requests

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

PRODUCER_TOPIC = "agent_events"
CONSUMER_TOPIC = "anomalies"
SCHEMA_FILE = "producer/agent_events.avsc"
ANOMALIES_SCHEMA_FILE = "producer/anomalies.avsc"

class SentinelEngine:
    def __init__(self):
        self.producer_running = False
        self.consumer_running = False
        self.processor_running = False
        self.producer_thread = None
        self.consumer_thread = None
        self.processor_thread = None
        self.event_queue = queue.Queue(maxsize=100) # For UI display
        self.anomaly_queue = queue.Queue(maxsize=100) # For UI display
        self.log_queue = queue.Queue(maxsize=50) # For UI logs
        self.anomaly_trigger = None # 'token_runaway', 'loop_count', or None
        
        self.log("Initializing Sentinel Engine...")
        try:
            self.sr_client = self._get_schema_registry_client()
            self.producer = self._get_producer()
            self.anomalies_producer = self._get_anomalies_producer()
            self.consumer = self._get_consumer()
            self.log("Kafka components initialized successfully.")
        except Exception as e:
            self.log(f"Error initializing Kafka components: {e}")

    def _get_schema_registry_client(self):
        conf = {
            'url': SCHEMA_REGISTRY_URL,
            'basic.auth.user.info': f"{SCHEMA_REGISTRY_API_KEY}:{SCHEMA_REGISTRY_API_SECRET}"
        }
        return SchemaRegistryClient(conf)

    def _get_producer(self):
        with open(SCHEMA_FILE, 'r') as f:
            schema_str = f.read()
        
        avro_serializer = AvroSerializer(self.sr_client, schema_str)
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

    def _get_anomalies_producer(self):
        with open(ANOMALIES_SCHEMA_FILE, 'r') as f:
            schema_str = f.read()
        
        avro_serializer = AvroSerializer(self.sr_client, schema_str)
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

    def _get_consumer(self):
        # Generic Avro Deserializer
        avro_deserializer = AvroDeserializer(self.sr_client)
        string_deserializer = StringDeserializer('utf_8')

        consumer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVERS,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': SASL_USERNAME,
            'sasl.password': SASL_PASSWORD,
            'key.deserializer': string_deserializer,
            'value.deserializer': avro_deserializer,
            'group.id': f"sentinel-demo-{uuid.uuid4()}", # Unique group for demo to see all msgs
            'auto.offset.reset': 'latest'
        }
        return DeserializingConsumer(consumer_conf)

    def generate_event(self):
        """Generates a simulated AI agent event matching the Flink schema."""
        event = {
            "trace_id": str(uuid.uuid4()),
            "node_name": f"agent-{random.randint(1, 5)}",
            "request_id": str(uuid.uuid4()),
            "ts": int(time.time() * 1000),
            "tokens_used": random.randint(10, 1000),
            "step_index": random.randint(1, 20),
            "latency_ms": random.randint(100, 5000),
            "model_name": random.choice(["gpt-4", "claude-3", "gemini-pro"])
        }

        if self.anomaly_trigger == 'token_runaway':
            event['tokens_used'] = random.randint(5000, 10000)
            self.anomaly_trigger = None
        elif self.anomaly_trigger == 'loop_count':
            event['step_index'] = random.randint(50, 100)
            self.anomaly_trigger = None
            
        return event

    def _producer_loop(self):
        self.log("Producer loop started")
        while self.producer_running:
            try:
                event = self.generate_event()
                # Key should be node_name (agent_id)
                self.producer.produce(topic=PRODUCER_TOPIC, key=event['node_name'], value=event)
                self.producer.poll(0)
                
                # Add to UI queue
                if self.event_queue.full():
                    self.event_queue.get()
                self.event_queue.put(event)
                
                time.sleep(1) # 1 event per second for demo pacing
            except Exception as e:
                self.log(f"Producer error: {e}")
                time.sleep(1)

    def _consumer_loop(self):
        self.log("Consumer loop started")
        self.consumer.subscribe([CONSUMER_TOPIC])
        while self.consumer_running:
            try:
                msg = self.consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    self.log(f"Consumer error: {msg.error()}")
                    continue

                event = msg.value()
                
                # Send to Datadog
                self.send_to_datadog(event)
                
                # Add to UI queue
                if self.anomaly_queue.full():
                    self.anomaly_queue.get()
                self.anomaly_queue.put(event)
                
            except Exception as e:
                self.log(f"Consumer loop error: {e}")
                time.sleep(1)
        self.consumer.close()
        self.log("Consumer loop stopped")

    def _processor_loop(self):
        """Simulates Flink SQL processing for local anomaly detection."""
        print("Processor loop started")
        
        avro_deserializer = AvroDeserializer(self.sr_client)
        string_deserializer = StringDeserializer('utf_8')
        consumer_conf = {
            'bootstrap.servers': BOOTSTRAP_SERVERS,
            'security.protocol': 'SASL_SSL',
            'sasl.mechanisms': 'PLAIN',
            'sasl.username': SASL_USERNAME,
            'sasl.password': SASL_PASSWORD,
            'key.deserializer': string_deserializer,
            'value.deserializer': avro_deserializer,
            'group.id': f"sentinel-processor-{uuid.uuid4()}",
            'auto.offset.reset': 'latest'
        }
        processor_consumer = DeserializingConsumer(consumer_conf)
        processor_consumer.subscribe([PRODUCER_TOPIC])

        while self.processor_running:
            try:
                msg = processor_consumer.poll(1.0)
                if msg is None: continue
                if msg.error(): continue

                event = msg.value()
                
                is_anomaly = False
                tokens = event.get('tokens_used') or event.get('tokens_generated', 0)
                if tokens > 5000:
                    is_anomaly = True
                
                steps = event.get('step_index') or event.get('loop_step', 0)
                if steps > 50:
                    is_anomaly = True
                
                if is_anomaly:
                    agent_id = event.get('node_name') or event.get('agent_id', 'unknown')
                    self.log(f"Local Processor found anomaly: {event.get('trace_id', 'unknown')}")
                    
                    anomaly_event = {
                        "trace_id": event.get("trace_id"),
                        "request_id": event.get("request_id"),
                        "node_name": agent_id,
                        "anomaly_type": "token_runaway" if tokens > 5000 else "infinite_loop",
                        "loop_count": int(steps),
                        "total_tokens": int(tokens),
                        "window_seconds": 60,
                        "ts": event.get("ts")
                    }
                    
                    self.anomalies_producer.produce(topic=CONSUMER_TOPIC, key=agent_id, value=anomaly_event)
                    self.anomalies_producer.poll(0)

            except Exception as e:
                print(f"Processor error: {e}")
                time.sleep(1)
        processor_consumer.close()

    def send_to_datadog(self, event):
        """Sends anomaly events to Datadog via the Events API."""
        if not DD_API_KEY:
            self.log("Datadog API Key not set, skipping event send.")
            return
            
        url = f"https://api.{DD_SITE}/api/v1/events"
        headers = {
            "Content-Type": "application/json",
            "DD-API-KEY": DD_API_KEY
        }
        
        agent_id = event.get('node_name') or event.get('agent_id', 'unknown')
        model_name = event.get('model_name', 'unknown')
        
        title = "SentinelLM Anomaly Detected"
        text = f"Anomaly detected for agent {agent_id}.\nDetails: {json.dumps(event, indent=2, default=str)}"
        
        payload = {
            "title": title,
            "text": text,
            "alert_type": "error",
            "source_type_name": "sentinellm",
            "tags": [
                "env:hackathon",
                "source:sentinellm",
                f"agent:{agent_id}",
                f"model:{model_name}"
            ]
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 202:
                self.log(f"Successfully sent event to Datadog: {title}")
            else:
                self.log(f"Failed to send to Datadog ({response.status_code}): {response.text}")
        except Exception as e:
            self.log(f"Error sending to Datadog: {e}")

    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        msg = f"[{timestamp}] {message}"
        print(msg)
        if self.log_queue.full():
            self.log_queue.get()
        self.log_queue.put(msg)

    def get_logs(self):
        logs = []
        while not self.log_queue.empty():
            logs.append(self.log_queue.get())
        return logs

    def start_producer(self):
        if not self.producer_running:
            self.producer_running = True
            self.producer_thread = threading.Thread(target=self._producer_loop, daemon=True)
            self.producer_thread.start()

    def stop_producer(self):
        self.producer_running = False
        if self.producer_thread:
            self.producer_thread.join(timeout=2)

    def start_consumer(self):
        if not self.consumer_running:
            self.consumer_running = True
            self.consumer_thread = threading.Thread(target=self._consumer_loop, daemon=True)
            self.consumer_thread.start()

    def stop_consumer(self):
        self.consumer_running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2)

    def start_processor(self):
        if not hasattr(self, 'processor_running'): self.processor_running = False
        
        if not self.processor_running:
            self.processor_running = True
            self.processor_thread = threading.Thread(target=self._processor_loop, daemon=True)
            self.processor_thread.start()

    def stop_processor(self):
        self.processor_running = False
        if hasattr(self, 'processor_thread') and self.processor_thread:
            self.processor_thread.join(timeout=2)

    def trigger_anomaly(self, anomaly_type):
        self.anomaly_trigger = anomaly_type

    def get_recent_events(self):
        events = []
        while not self.event_queue.empty():
            events.append(self.event_queue.get())
        return events

    def get_recent_anomalies(self):
        anomalies = []
        while not self.anomaly_queue.empty():
            anomalies.append(self.anomaly_queue.get())
        return anomalies
