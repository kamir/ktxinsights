#!/usr/bin/env python3
"""
Transaction Aggregator for the Kafka Transaction Insight System.

This service consumes workflow events (from Kafka or JSONL), correlates them
to build a stateful view of each transaction, and exposes the aggregated
data as Prometheus metrics.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from prometheus_client import start_http_server, Counter, Histogram, Gauge

try:
    from confluent_kafka import Consumer
except Exception:
    Consumer = None  # optional

# ---------------------------
# Prometheus Metrics Definition
# ---------------------------
EVENT_COUNT = Counter(
    "txinsights_events_total",
    "Total events ingested by type",
    labelnames=("type",),
)

TXN_DURATION = Histogram(
    "txinsights_transaction_duration_seconds",
    "Transaction duration from open to close (seconds)",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55),
)

INTER_STEP_GAP = Histogram(
    "txinsights_inter_step_gap_seconds",
    "Inter-step wait (seconds)",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 15, 20, 30),
)

OUTLIERS = Counter(
    "txinsights_inter_step_outliers_total",
    "Count of inter-step gaps above threshold",
)

INJECTED_OUTLIERS = Counter(
    "txinsights_injected_outliers_total",
    "Count of gaps marked as outlier_injected by producer",
)

OPEN_TXN_GAUGE = Gauge(
    "txinsights_open_transactions",
    "Number of transactions currently open",
)

# ---------------------------
# Aggregation Logic
# ---------------------------
class Aggregator:
    def __init__(self, outlier_ms: int = 15000):
        self.txn_open_ts: Dict[str, int] = {}
        self.outlier_threshold_ms = outlier_ms
        self.counts = defaultdict(int)

    def on_event(self, ev: dict):
        et = ev.get("type")
        if not et:
            return

        self.counts[f"type:{et}"] += 1
        EVENT_COUNT.labels(et).inc()

        if et == "transaction_open":
            txn = ev["txn_id"]
            self.txn_open_ts[txn] = int(ev["ts_ms"])
            OPEN_TXN_GAUGE.inc()

        elif et == "transaction_close":
            txn = ev["txn_id"]
            ts = int(ev["ts_ms"])
            if txn in self.txn_open_ts:
                dur_ms = ts - self.txn_open_ts.pop(txn)
                TXN_DURATION.observe(dur_ms / 1000.0)
                OPEN_TXN_GAUGE.dec()

        elif et == "inter_step_wait":
            planned = ev.get("planned_wait_ms")
            if planned is not None:
                gap_seconds = float(planned) / 1000.0
                INTER_STEP_GAP.observe(gap_seconds)
                if ev.get("outlier_injected"):
                    INJECTED_OUTLIERS.inc()
                if planned >= self.outlier_threshold_ms:
                    OUTLIERS.inc()

# ---------------------------
# Input Readers
# ---------------------------
def now_ms() -> int:
    return int(time.time() * 1000)

def read_jsonl_stream(fp):
    for line in fp:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue

def read_kafka_stream(bootstrap: str, topics: List[str], group_id: str):
    if Consumer is None:
        raise RuntimeError("confluent-kafka not installed. `pip install confluent-kafka`")
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
        "session.timeout.ms": 20000,
    })
    consumer.subscribe(topics)
    try:
        while True:
            msg = consumer.poll(0.5)
            if msg is None:
                continue
            if msg.error():
                sys.stderr.write(f"[KAFKA-ERROR] {msg.error()}\n")
                continue
            try:
                ev = json.loads(msg.value().decode("utf-8"))
                yield ev
            except Exception as e:
                sys.stderr.write(f"[DESER-ERROR] {e}\n")
                continue
    finally:
        consumer.close()

# ---------------------------
# Main Execution
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="Kafka Transaction Aggregator and Prometheus Exporter.")
    src = parser.add_mutually_exclusive_group(required=False)
    src.add_argument("--file", type=str, help="Read from JSONL file (stream). If omitted, read stdin.")
    src.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    parser.add_argument("--kafka-topics", type=str, nargs="+",
                        default=["workflow.transactions", "workflow.steps"])
    parser.add_argument("--kafka-group", type=str, default="txinsights-aggregator")
    parser.add_argument("--listen-port", type=int, default=8000, help="Port for /metrics endpoint")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Gap threshold for outliers (ms)")
    args = parser.parse_args()

    # Start Prometheus HTTP server
    start_http_server(args.listen_port)
    print(f"Prometheus metrics exposed on port {args.listen_port}")

    # Initialize aggregator
    aggregator = Aggregator(outlier_ms=args.outlier_ms)

    # Determine input stream
    if args.kafka_bootstrap:
        print(f"Consuming from Kafka ({args.kafka_bootstrap}) on topics: {args.kafka_topics}")
        stream = read_kafka_stream(args.kafka_bootstrap, args.kafka_topics, args.kafka_group)
    elif args.file:
        print(f"Reading from file: {args.file}")
        fp = open(args.file, "r", encoding="utf-8")
        stream = read_jsonl_stream(fp)
    else:
        print("Reading from stdin...")
        stream = read_jsonl_stream(sys.stdin)

    # Ingestion loop
    print("Starting event ingestion loop...")
    for ev in stream:
        aggregator.on_event(ev)

    print("Finished processing events. Metrics server is running.")
    # Keep the script running to serve metrics
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
