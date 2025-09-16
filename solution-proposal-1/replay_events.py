#!/usr/bin/env python3
"""
Replay a previously generated workflow scenario from a JSONL file to Kafka.

This script reads a JSONL file containing transaction events and publishes
them to the appropriate Kafka topics, preserving the original timing of the
events to faithfully reproduce the workload scenario.
"""

import argparse
import json
import sys
import time
from typing import List

try:
    from confluent_kafka import Producer
except Exception:
    Producer = None

def create_kafka_producer(bootstrap_servers: str):
    """Create a Kafka producer instance."""
    if Producer is None:
        raise RuntimeError("confluent-kafka is not installed. Please run `pip install confluent-kafka`.")
    return Producer({
        "bootstrap.servers": bootstrap_servers,
        "socket.keepalive.enable": True,
        "acks": "all",
    })

def read_jsonl(path: str):
    """Read a JSONL file and yield each line as a dictionary."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                sys.stderr.write(f"Warning: Skipping malformed JSON line: {line}\n")
                continue

def replay_events(producer: Producer, events: List[dict], speed_factor: float, topic_txn: str, topic_steps: str):
    """Replay events to Kafka, preserving relative timing."""
    print(f"Starting replay of {len(events)} events with speed factor {speed_factor}x...")

    if not events:
        print("No events to replay.")
        return

    start_time = time.time()
    original_start_ts = events[0]['ts_ms']
    events_sent = 0

    def delivery_callback(err, msg):
        nonlocal events_sent
        if err:
            sys.stderr.write(f"[KAFKA-ERROR] {err} for {msg.topic()}\n")
        else:
            events_sent += 1

    for event in events:
        # Determine the target topic based on the event type
        event_type = event.get("type", "")
        if "transaction" in event_type:
            topic = topic_txn
        else:
            topic = topic_steps

        # Calculate the delay needed to preserve original timing
        original_current_ts = event['ts_ms']
        original_delta_ms = original_current_ts - original_start_ts
        target_replay_time = start_time + (original_delta_ms / 1000.0) / speed_factor

        # Sleep if we are ahead of schedule
        sleep_duration = target_replay_time - time.time()
        if sleep_duration > 0:
            time.sleep(sleep_duration)

        # Produce the message
        producer.produce(
            topic=topic,
            value=json.dumps(event, ensure_ascii=False).encode("utf-8"),
            callback=delivery_callback
        )
        producer.poll(0) # Non-blocking poll to trigger delivery callbacks

    print("All events have been produced. Flushing producer...")
    producer.flush()
    print(f"Replay complete. {events_sent} events successfully sent.")

def main():
    parser = argparse.ArgumentParser(description="Replay a Kafka event scenario from a JSONL file.")
    parser.add_argument("--file", type=str, required=True, help="Path to the events.jsonl file to replay.")
    parser.add_argument("--kafka-bootstrap", type=str, required=True, help="Kafka bootstrap servers (e.g., localhost:9092).")
    parser.add_argument("--speed-factor", type=float, default=1.0, help="Speed multiplier for the replay (e.g., 2.0 for 2x speed).")
    parser.add_argument("--topic-txn", type=str, default="workflow.transactions", help="Topic for transaction open/close events.")
    parser.add_argument("--topic-steps", type=str, default="workflow.steps", help="Topic for step-related events.")
    args = parser.parse_args()

    # Read all events into memory to allow for sorting and timing calculations
    events = sorted(read_jsonl(args.file), key=lambda x: x['ts_ms'])

    producer = create_kafka_producer(args.kafka_bootstrap)
    replay_events(producer, events, args.speed_factor, args.topic_txn, args.topic_steps)

if __name__ == "__main__":
    main()
