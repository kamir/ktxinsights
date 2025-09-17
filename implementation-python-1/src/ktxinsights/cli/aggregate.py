import argparse
import json
import sys
import time
import threading
from prometheus_client import start_http_server
from ktxinsights.aggregator import Aggregator, kafka_consumer_worker

def file_reader_worker(file_path: str, aggregator: Aggregator):
    """Simulates both consumers by reading from a single event file."""
    print(f"Reading events from file: {file_path}")
    with open(file_path, 'r') as f:
        for line in f:
            try:
                event = json.loads(line)
                # In file mode, we simulate both consumers seeing the event
                aggregator.process_event(event, "monitor")
                aggregator.process_event(event, "validator")
                # Add a small delay to simulate real-time processing
                time.sleep(0.01)
            except json.JSONDecodeError:
                continue
    print("Finished reading event file.")

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Aggregator with Dual-Consumer Strategy.")
    parser.add_argument("--file", type=str, help="Path to an events.jsonl file to process instead of connecting to Kafka.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--kafka-topics", type=str, nargs="+",
                        default=["workflow.transactions", "workflow.steps"])
    parser.add_argument("--coordinator-topic", type=str, default="ktxinsights.coordinator.state", help="Topic for coordinator state")
    parser.add_argument("--listen-port", type=int, default=8000, help="Port for /metrics endpoint")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Gap threshold for outliers (ms)")
    parser.add_argument("--abort-timeout-s", type=int, default=60, help="Timeout in seconds to consider a transaction aborted")
    args = parser.parse_args()

    # Start Prometheus HTTP server
    start_http_server(args.listen_port)
    print(f"Prometheus metrics exposed on port {args.listen_port}")

    # Initialize the central aggregator
    aggregator = Aggregator(outlier_ms=args.outlier_ms, abort_timeout_s=args.abort_timeout_s)

    if args.file:
        # File-based mode
        file_thread = threading.Thread(
            target=file_reader_worker,
            args=(args.file, aggregator),
            daemon=True
        )
        file_thread.start()
    else:
        # Kafka-based mode
        if not args.kafka_bootstrap and not args.config_file:
            parser.error("Either --kafka-bootstrap, --config-file, or --file must be provided.")

        conf = {}
        if args.config_file:
            with open(args.config_file) as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    key, value = line.strip().split('=', 1)
                    conf[key.strip()] = value.strip()
        
        if args.kafka_bootstrap:
            conf['bootstrap.servers'] = args.kafka_bootstrap

        # --- Start Kafka Consumer Threads ---
        threads = []
        monitor_thread = threading.Thread(
            target=kafka_consumer_worker,
            args=(conf, args.kafka_topics, "ktxinsights-monitor-group", "read_uncommitted", aggregator, "monitor"),
            daemon=True,
        )
        threads.append(monitor_thread)

        validator_thread = threading.Thread(
            target=kafka_consumer_worker,
            args=(conf, args.kafka_topics, "ktxinsights-validator-group", "read_committed", aggregator, "validator"),
            daemon=True,
        )
        threads.append(validator_thread)

        # 3. Coordinator Consumer (read_committed, as it's internal)
        coordinator_thread = threading.Thread(
            target=kafka_consumer_worker,
            args=(conf, [args.coordinator_topic], "ktxinsights-coordinator-group", "read_committed", aggregator, "coordinator"),
            daemon=True,
        )
        threads.append(coordinator_thread)
        
        for t in threads:
            t.start()

    # Abort checker runs in both modes
    abort_checker_thread = threading.Thread(
        target=aggregator.check_for_aborted_transactions,
        daemon=True,
    )
    abort_checker_thread.start()

    print("Aggregator service running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
