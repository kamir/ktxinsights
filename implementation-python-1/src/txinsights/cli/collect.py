import argparse
from txinsights.collector import collection_loop

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Coordinator State Collector.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--topic", type=str, default="txinsights.coordinator.state", help="Topic to publish coordinator state to")
    parser.add_argument("--interval-s", type=int, default=15, help="Polling interval in seconds")
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

    collection_loop(conf, args.topic, args.interval_s)

if __name__ == "__main__":
    main()
