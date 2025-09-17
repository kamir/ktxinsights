import argparse
from ktxinsights.replay import create_kafka_producer, read_jsonl, replay_events

def main():
    parser = argparse.ArgumentParser(description="Replay a Kafka event scenario from a JSONL file.")
    parser.add_argument("--file", type=str, required=True, help="Path to the events.jsonl file to replay.")
    parser.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers (e.g., localhost:9092).")
    parser.add_argument("--config-file", type=str, help="Path to Confluent Cloud configuration file.")
    parser.add_argument("--speed-factor", type=float, default=1.0, help="Speed multiplier for the replay (e.g., 2.0 for 2x speed).")
    parser.add_argument("--topic-txn", type=str, default="workflow.transactions", help="Topic for transaction open/close events.")
    parser.add_argument("--topic-steps", type=str, default="workflow.steps", help="Topic for step-related events.")
    args = parser.parse_args()

    # Read all events into memory to allow for sorting and timing calculations
    events = sorted(read_jsonl(args.file), key=lambda x: x['ts_ms'])

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

    producer = create_kafka_producer(conf)
    replay_events(producer, events, args.speed_factor, args.topic_txn, args.topic_steps)

if __name__ == "__main__":
    main()
