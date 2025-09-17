"""
Coordinator Collector for the Kafka Transaction Insight System.

This service connects to the Kafka cluster using the Admin API to fetch
information about ongoing transactions directly from the transaction coordinator.
It then publishes this data to an internal topic for consumption by the aggregator.
"""

import sys
import json
import time
import random
import re
from confluent_kafka.admin import AdminClient
from confluent_kafka import Producer
from prometheus_client import start_http_server, Counter, Histogram

# ---------------------------
# Prometheus Metrics Definition
# ---------------------------
COORDINATOR_POLL_DURATION = Histogram(
    "ktxinsights_coordinator_poll_duration_seconds",
    "Duration of the AdminClient.list_transactions() call.",
)

COORDINATOR_POLL_ERRORS = Counter(
    "ktxinsights_coordinator_poll_errors_total",
    "Total errors encountered during coordinator polling.",
    labelnames=("error_type",),
)

def create_admin_client(config: dict) -> AdminClient:
    """Creates and returns a Kafka AdminClient."""
    return AdminClient(config)

def create_producer(config: dict) -> Producer:
    """Creates and returns a Kafka Producer."""
    return Producer(config)

def fetch_and_publish_transactions(
    admin_client: AdminClient,
    producer: Producer,
    topic: str,
    tx_id_prefix: str = None,
    tx_id_regex: str = None,
    duration_metric=COORDINATOR_POLL_DURATION,
    error_metric=COORDINATOR_POLL_ERRORS,
):
    """
    Fetches the list of ongoing transactions from the broker and publishes
    their state to a Kafka topic.
    Returns the number of transactions found.
    """
    start_time = time.time()
    # The list_transactions() method returns a future.
    future = admin_client.list_transactions(request_timeout=10)

    try:
        # Wait for the result.
        result = future.result()
        duration = time.time() - start_time
        duration_metric.observe(duration)

        now = int(time.time() * 1000)
        found_txns = 0
        
        # Compile regex if provided
        regex = re.compile(tx_id_regex) if tx_id_regex else None

        for txn in result.transactions:
            # Filter for transactions we care about (non-terminal states).
            if txn.state.name not in ("ONGOING", "PREPARE_COMMIT"):
                continue

            # Apply filters
            if tx_id_prefix and not txn.transactional_id.startswith(tx_id_prefix):
                continue
            if regex and not regex.match(txn.transactional_id):
                continue

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
        return found_txns

    except Exception as e:
        error_metric.labels(error_type=type(e).__name__).inc()
        sys.stderr.write(f"Error fetching transaction states: {e}\n")
        # Re-raise the exception to be handled by the polling loop's backoff mechanism
        raise

def collection_loop(
    kafka_config: dict,
    topic: str,
    poll_interval_s: int,
    tx_id_prefix: str = None,
    tx_id_regex: str = None,
    read_only: bool = False,
):
    """The main loop for the collector service with exponential backoff and jitter."""
    print("Starting CoordinatorCollector service...")
    # In a real scenario, you might start the Prometheus server here if it's not already running.
    # For this tool, we assume it's started by the CLI entry point.
    
    backoff_s = poll_interval_s
    max_backoff_s = max(60, poll_interval_s * 4)

    try:
        admin_client = create_admin_client(kafka_config)
        producer = create_producer(kafka_config)
        print(f"Publishing coordinator state to topic '{topic}' every ~{poll_interval_s}s.")
        if read_only:
            print("Running in read-only mode.")
        
        while True:
            try:
                fetch_and_publish_transactions(
                    admin_client,
                    producer,
                    topic,
                    tx_id_prefix,
                    tx_id_regex,
                    duration_metric=COORDINATOR_POLL_DURATION,
                    error_metric=COORDINATOR_POLL_ERRORS,
                )
                # On success, reset backoff to the base interval
                backoff_s = poll_interval_s
            except Exception:
                # On failure, increase the backoff time
                backoff_s = min(max_backoff_s, backoff_s * 2)
                print(f"Encountered error, backing off for {backoff_s:.2f}s")

            # Add jitter to the sleep time to avoid thundering herd
            sleep_time = backoff_s + random.uniform(0, backoff_s * 0.1)
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\nShutting down CoordinatorCollector.")
    except Exception as e:
        sys.stderr.write(f"A critical error occurred: {e}\n")
