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
import uuid

from confluent_kafka import Producer

def create_kafka_producer(config: dict):
    """Create a Kafka producer instance."""

    # Default settings that can be overridden by the config file
    default_conf = {
        "socket.keepalive.enable": True,
        "acks": "all",
        "transaction.timeout.ms": 60000,
    }
    default_conf.update(config)
    return Producer(default_conf)

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

def __send_txn_event(producer: Producer, topic_txn: str, event: dict, txn_id: str, delivery_callback):
    print(f"[DEBUG] Sending transaction event for txn_id {txn_id} at ts {event['ts_ms']}")
    headers = [("txn_id", str(txn_id).encode("utf-8"))]
    producer.produce(
        topic=topic_txn,
        key="tx_event",
        value=json.dumps(event, ensure_ascii=False).encode("utf-8"),
        headers=headers if headers else None,
        callback=delivery_callback
    )
    # wait for message delivery
    producer.flush()
    # poll to trigger delivery callbacks
    producer.poll(0)

def replay_events(conf: dict[str,str], events: List[dict], speed_factor: float, topic_txn: str, randomize_tx_id: bool = False):
    """Replay events to Kafka, preserving relative timing."""

    print(f"Starting replay of {len(events)} events with speed factor {speed_factor}x...")

    if not events:
        print("No events to replay.")
        return

    producers: dict[str, Producer] = {}
    if randomize_tx_id:
        txn_id_map: dict[str, str] = {}

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
        # Calculate the delay needed to preserve original timing
        original_current_ts = event['ts_ms']
        original_delta_ms = original_current_ts - original_start_ts
        target_replay_time = start_time + (original_delta_ms / 1000.0) / speed_factor

        # check if txn_id exists, randomize if randomize_tx_id is enabled
        txn_id = event.get('txn_id')
        if txn_id is None:
            print(f"[WARN] Event at ts {event['ts_ms']} missing txn_id. Skipping.")
            continue
        if randomize_tx_id:
            if txn_id not in txn_id_map:
                new_txn_id = str(uuid.uuid4())
                txn_id_map[txn_id] = new_txn_id
                print(f"[INFO] Mapping original txn_id {txn_id} to new random txn_id {new_txn_id}")
            txn_id = txn_id_map[txn_id]

        # check for transaction_open event to create a new producer if needed and start a transaction
        # !! be aware that we do NOT close previous transactions automatically, this is an explicit generated
        # fault of the simulation tool and should be handled by the broker/coordinator
        if event.get("type") == "transaction_open":
            # create producer
            try:
                copyconf = conf.copy()
                copyconf.update({
                    "transactional.id": txn_id,
                })
                producers[txn_id] = create_kafka_producer(copyconf)
            except Exception as e:
                print(f"[WARN] init_transactions: {e}")

            # init transaction
            try:
                producers[txn_id].init_transactions()
                print(f"[INFO] Transaction initialized at event ts {event['ts_ms']}")
            except Exception as e:
                print(f"[ERROR] init_transactions: {e}, removing producer for txn_id {txn_id}")
                producers.pop(txn_id, None)
                continue

            # start transaction
            try:
                producers[txn_id].begin_transaction()
                print(f"[INFO] Transaction started at event ts {event['ts_ms']}")
            except Exception as e:
                print(f"[ERROR] begin_transaction: {e}, removing producer for txn_id {txn_id}")
                producers.pop(txn_id, None)
                continue

        # check if producer for txn_id exists and use it for current event
        if txn_id is not None:
            producer = producers.get(txn_id)
            if producer is None:
                print(f"[WARN] No producer found for txn_id {txn_id}. Skipping event at ts {event['ts_ms']}.")
                continue

        # wait until the target replay time
        sleep_duration = target_replay_time - time.time()
        if sleep_duration > 0:
            print(f"[DEBUG] Sleeping for {sleep_duration} seconds to preserve event timing.")
            time.sleep(sleep_duration)

        # send event
        __send_txn_event(producer, topic_txn, event, txn_id, delivery_callback)

        # end transaction if event type is transaction_close
        if event.get("type") == "transaction_close":
            try:
                producer.commit_transaction()
                print(f"[INFO] Transaction committed at event ts {event['ts_ms']}")
                # remove producer from dict after commit
                producers.pop(txn_id, None)
            except Exception as e:
                print(f"[ERROR] commit_transaction: {e}")

    print(f"Replay complete. {events_sent} events successfully sent.")
