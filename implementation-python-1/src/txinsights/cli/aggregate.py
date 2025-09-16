import argparse
import sys
import time
import threading
from prometheus_client import start_http_server
from txinsights.aggregator import Aggregator, kafka_consumer_worker

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Aggregator with Dual-Consumer Strategy.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--kafka-topics", type=str, nargs="+",
                        default=["workflow.transactions", "workflow.steps"])
    parser.add_argument("--listen-port", type=int, default=8000, help="Port for /metrics endpoint")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Gap threshold for outliers (ms)")
    parser.add_argument("--abort-timeout-s", type=int, default=60, help="Timeout in seconds to consider a transaction aborted")
    args = parser.parse_args()

    # Start Prometheus HTTP server
    start_http_server(args.listen_port)
    print(f"Prometheus metrics exposed on port {args.listen_port}")

    # Initialize the central aggregator
    aggregator = Aggregator(outlier_ms=args.outlier_ms, abort_timeout_s=args.abort_timeout_s)

    if not args.kafka_bootstrap and not args.config_file:
        parser.error("Either --kafka-bootstrap or --config-file must be provided.")

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

    # --- Start Consumer Threads ---
    threads = []
    
    # 1. Monitor Consumer (read_uncommitted)
    monitor_thread = threading.Thread(
        target=kafka_consumer_worker,
        args=(
            conf,
            args.kafka_topics,
            "txinsights-monitor-group",
            "read_uncommitted",
            aggregator,
            "monitor",
        ),
        daemon=True,
    )
    threads.append(monitor_thread)

    # 2. Validator Consumer (read_committed)
    validator_thread = threading.Thread(
        target=kafka_consumer_worker,
        args=(
            conf,
            args.kafka_topics,
            "txinsights-validator-group",
            "read_committed",
            aggregator,
            "validator",
        ),
        daemon=True,
    )
    threads.append(validator_thread)

    # 3. Abort Checker Thread
    abort_checker_thread = threading.Thread(
        target=aggregator.check_for_aborted_transactions,
        daemon=True,
    )
    threads.append(abort_checker_thread)

    for t in threads:
        t.start()

    print("Aggregator service running. Press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
