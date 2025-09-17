"""
Coordinator Collector for the Kafka Transaction Insight System.

This service connects to the Kafka cluster using the Admin API to fetch
information about ongoing transactions directly from the transaction coordinator.
It then publishes this data to an internal topic for consumption by the aggregator.
"""

import sys
import json
import time
from confluent_kafka.admin import AdminClient
from confluent_kafka import Producer

def create_admin_client(config: dict) -> AdminClient:
    """Creates and returns a Kafka AdminClient."""
    return AdminClient(config)

def create_producer(config: dict) -> Producer:
    """Creates and returns a Kafka Producer."""
    return Producer(config)

def fetch_and_publish_transactions(admin_client: AdminClient, producer: Producer, topic: str):
    """
    Fetches the list of ongoing transactions from the broker and publishes
    their state to a Kafka topic.
    """
    # The list_transactions() method returns a future.
    future = admin_client.list_transactions(request_timeout=10)

    try:
        # Wait for the result.
        result = future.result()
        now = int(time.time() * 1000)
        found_txns = 0

        for txn in result.transactions:
            # Filter for transactions we care about (non-terminal states).
            if txn.state.name in ("ONGOING", "PREPARE_COMMIT"):
                found_txns += 1
                message = {
                    "transactional_id": txn.transactional_id,
                    "producer_id": txn.producer_id,
                    "producer_epoch": txn.producer_epoch,
                    "state": txn.state.name,
                    "start_timestamp_ms": txn.start_timestamp,
                    "last_update_timestamp_ms": txn.last_update,
                    "coordinator_broker_id": txn.coordinator.id,
                    "collection_timestamp_ms": now,
                }
                # Produce message to the internal topic.
                producer.produce(
                    topic=topic,
                    value=json.dumps(message).encode('utf-8'),
                    key=txn.transactional_id.encode('utf-8')
                )
        
        if found_txns > 0:
            print(f"[{time.ctime()}] Found and published {found_txns} ongoing transaction(s).")
        else:
            print(f"[{time.ctime()}] No ongoing transactions found.")

        producer.flush()

    except Exception as e:
        sys.stderr.write(f"Error fetching transaction states: {e}\n")

def collection_loop(kafka_config: dict, topic: str, interval_s: int):
    """The main loop for the collector service."""
    print("Starting CoordinatorCollector service...")
    try:
        admin_client = create_admin_client(kafka_config)
        producer = create_producer(kafka_config)
        print(f"Publishing coordinator state to topic '{topic}' every {interval_s}s.")
        
        while True:
            fetch_and_publish_transactions(admin_client, producer, topic)
            time.sleep(interval_s)
            
    except KeyboardInterrupt:
        print("\nShutting down CoordinatorCollector.")
    except Exception as e:
        sys.stderr.write(f"A critical error occurred: {e}\n")
