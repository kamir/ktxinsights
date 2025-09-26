import argparse
import os
from ktxinsights.collector import collect, CollectorConfig

def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Coordinator State Collector.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--consumer-config", type=str, help="Path to Confluent Cloud Consumer configuration file.")
    parser.add_argument("--producer-config", type=str, help="Path to Confluent Cloud Producer configuration file.")
    parser.add_argument("--topic", type=str, default=os.environ.get("KTX_TOPIC", "ktx.state"), help="Topic to publish coordinator state to")
    parser.add_argument("--topic-tx", type=str, default=os.environ.get("KTX_TOPIC_TX", "ktx.tx"), help="Topic containing transaction events to listen to")
    args = parser.parse_args()

    if not args.kafka_bootstrap:
        args.kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP")
    if not args.consumer_config:
        args.consumer_config = os.environ.get("CONSUMER_CONFIG")
    if not args.producer_config:
        args.producer_config = os.environ.get("PRODUCER_CONFIG")

    if not args.kafka_bootstrap and not( args.consumer_config or args.producer_config):
        parser.error("Either --kafka-bootstrap or --consumer-config and --producer-config must be provided.")

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

    producer_conf = {}
    if args.producer_config:
        with open(args.producer_config) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                key, value = line.strip().split('=', 1)
                producer_conf[key.strip()] = value.strip()

    if args.kafka_bootstrap:
        producer_conf['bootstrap.servers'] = args.kafka_bootstrap

    collConf = CollectorConfig()
    collConf.state_topic = args.topic
    collConf.tx_topic = args.topic_tx
    collConf.consumer_config = consumer_conf
    collConf.producer_config = producer_conf
    collect(collConf)

if __name__ == "__main__":
    main()
