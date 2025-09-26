import os
import argparse
from prometheus_client import start_http_server
from ktxinsights.aggregator import Aggregator, aggregate

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Aggregator with Dual-Consumer Strategy.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--consumer-config", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--topic", type=str, default=os.environ.get("KTX_TOPIC", "ktx.state"), help="Topic for transaction state")
    parser.add_argument("--listen-port", type=int, default=int(os.environ.get("KTX_LISTEN_PORT", 8000)), help="Port for /metrics endpoint")
    parser.add_argument("--abort-timeout-s", type=int, default=int(os.environ.get("ABORT_TIMEOUT_S", 60)), help="Timeout in seconds to consider a transaction aborted")

    args = parser.parse_args()

    if not args.kafka_bootstrap:
        args.kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP")
    if not args.consumer_config:
        args.consumer_config = os.environ.get("CONSUMER_CONFIG")

    if not args.kafka_bootstrap and not( args.consumer_config ):
        parser.error("Either --kafka-bootstrap or --consumer-config must be provided.")

    consumer_conf = {}
    if args.consumer_config:
        with open(args.consumer_config) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                key, value = line.strip().split('=', 1)
                consumer_conf[key.strip()] = value.strip()

    if args.kafka_bootstrap:
        consumer_conf['bootstrap.servers'] = args.kafka_bootstrap

    # Start Prometheus HTTP server
    start_http_server(args.listen_port)
    print(f"Prometheus metrics exposed on port {args.listen_port}")

    # Initialize the central aggregator
    aggregator = Aggregator(abort_timeout_s=args.abort_timeout_s)

    aggregate(aggregator, args.topic, consumer_conf)

if __name__ == "__main__":
    main()
