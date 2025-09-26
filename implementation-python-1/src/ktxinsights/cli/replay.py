import argparse
from ktxinsights.replay import read_jsonl, replay_events

def main():
    parser = argparse.ArgumentParser(description="Replay a Kafka event scenario from a JSONL file.")
    parser.add_argument("--file", type=str, required=True, help="Path to the events.jsonl file to replay.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers (e.g., localhost:9092).")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--speed-factor", type=float, default=1.0, help="Speed multiplier for the replay (e.g., 2.0 for 2x speed).")
    parser.add_argument("--topic-tx", type=str, default="ktxinsights.tx", help="Topic for transaction open/close events.")
    parser.add_argument("--randomize-tx-id", type=bool, default=False, help="Enable random transaction IDs.")
    args = parser.parse_args()

    # read all events into memory to allow for sorting and timing calculations
    events = sorted(read_jsonl(args.file), key=lambda x: x['ts_ms'])

    if not args.kafka_bootstrap and not args.config_file:
        parser.error("Either --kafka-bootstrap or --config-file must be provided.")

    # setup base producer configuration
    conf: dict[str,str] = {}
    if args.config_file:
        with open(args.config_file) as f:
            for line in f:
                if line.startswith('#') or not line.strip():
                    continue
                key, value = line.strip().split('=', 1)
                conf[key.strip()] = value.strip()
    
    if args.kafka_bootstrap:
        conf['bootstrap.servers'] = args.kafka_bootstrap

    # check for confluent-kafka sdk
    try:
        from confluent_kafka import Producer    
    except Exception:
        if Producer is None:
            raise RuntimeError("confluent-kafka is not installed. Please run `pip install confluent-kafka`.")

    # Start the replay
    replay_events(conf, events, args.speed_factor, args.topic_tx, args.randomize_tx_id)

if __name__ == "__main__":
    main()
