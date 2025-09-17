import argparse
from ktxinsights.collector import collection_loop

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Coordinator State Collector.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--topic", type=str, default="ktxinsights.coordinator.state", help="Topic to publish coordinator state to")
    parser.add_argument("--poll-interval-s", type=int, default=15, help="Base polling interval in seconds.")
    parser.add_argument("--tx-id-prefix", type=str, help="Only collect transactions with this prefix.")
    parser.add_argument("--tx-id-regex", type=str, help="Only collect transactions matching this regex.")
    parser.add_argument("--read-only", action="store_true", help="Run in read-only mode without attempting to abort transactions.")
    args = parser.parse_args()

    if not args.kafka_bootstrap and not args.config_file:
        parser.error("Either --kafka-bootstrap or --config-file must be provided.")

    conf = {}
    if args.config_file:
        with open(args.config_file) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                key, value = line.strip().split('=', 1)
                # A bit of a hack to separate admin client configs
                if key.startswith('admin.'):
                    conf[key[6:]] = value.strip()
                else:
                    conf[key.strip()] = value.strip()

    if args.kafka_bootstrap:
        conf['bootstrap.servers'] = args.kafka_bootstrap

    collection_loop(
        kafka_config=conf,
        topic=args.topic,
        poll_interval_s=args.poll_interval_s,
        tx_id_prefix=args.tx_id_prefix,
        tx_id_regex=args.tx_id_regex,
        read_only=args.read_only,
    )

if __name__ == "__main__":
    main()
