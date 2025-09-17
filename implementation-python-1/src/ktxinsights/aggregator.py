"""
Transaction Aggregator for the Kafka Transaction Insight System.

This service consumes workflow events from Kafka using a dual-consumer strategy
to build a stateful view of each transaction and expose the aggregated
data as Prometheus metrics.
"""

import argparse
import json
import sys
import time
import threading
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
    "ktxinsights_events_total",
    "Total events ingested by type",
    labelnames=("type",),
)

INTER_STEP_GAP = Histogram(
    "ktxinsights_inter_step_gap_seconds",
    "Inter-step wait (seconds)",
    buckets=(0.1, 0.5, 1, 2, 5, 10, 15, 20, 30),
)

OUTLIERS = Counter(
    "ktxinsights_inter_step_outliers_total",
    "Count of inter-step gaps above threshold",
)

INJECTED_OUTLIERS = Counter(
    "ktxinsights_injected_outliers_total",
    "Count of gaps marked as outlier_injected by producer",
)

TXN_STATE_GAUGE = Gauge(
    "ktxinsights_transactions_by_state",
    "Number of transactions currently in a given state",
    labelnames=("state",),
)

# Initialize gauges for all possible states
TXN_STATE_GAUGE.labels("open").set(0)
TXN_STATE_GAUGE.labels("tentatively_closed").set(0)
TXN_STATE_GAUGE.labels("closed").set(0)
TXN_STATE_GAUGE.labels("aborted").set(0)
TXN_STATE_GAUGE.labels("verified_aborted").set(0)

TXN_LIFETIME = Histogram(
    "ktxinsights_transaction_lifetime_seconds",
    "End-to-end lifetime of a transaction from open to terminal state (closed or aborted)",
    buckets=(0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55),
)

TIL_GAUGE = Gauge(
    "ktxinsights_transactional_integrity_lag_seconds",
    "Time delta between the newest open and oldest unresolved transaction",
)

HIGH_WATERMARK_OPEN_TXN_GAUGE = Gauge(
    "ktxinsights_high_watermark_open_transactions_timestamp_seconds",
    "Timestamp of the most recently opened transaction that is not yet resolved",
)

LOW_WATERMARK_UNRESOLVED_TXN_GAUGE = Gauge(
    "ktxinsights_low_watermark_unresolved_transactions_timestamp_seconds",
    "Timestamp of the oldest transaction that is not yet resolved",
)


# ---------------------------
# Aggregation Logic
# ---------------------------
class TransactionState:
    """Models the state of a single business transaction."""
    def __init__(self, txn_id: str, open_ts: int):
        self.txn_id = txn_id
        self.state = "open"  # open, tentatively_closed, closed, aborted, verified_aborted
        self.open_ts = open_ts
        self.tentative_close_ts: Optional[int] = None
        self.close_ts: Optional[int] = None
        self.last_update_ts = open_ts

    def tentatively_close(self, ts: int):
        if self.state == "open":
            print(f"[{self.txn_id}] State change: open -> tentatively_closed")
            self.state = "tentatively_closed"
            self.tentative_close_ts = ts
            self.last_update_ts = ts
            TXN_STATE_GAUGE.labels("open").dec()
            TXN_STATE_GAUGE.labels("tentatively_closed").inc()

    def confirm_close(self, ts: int):
        if self.state == "tentatively_closed":
            print(f"[{self.txn_id}] State change: tentatively_closed -> closed")
            self.state = "closed"
            self.close_ts = ts
            self.last_update_ts = ts
            TXN_STATE_GAUGE.labels("tentatively_closed").dec()
            TXN_STATE_GAUGE.labels("closed").inc()
            TXN_LIFETIME.observe((self.close_ts - self.open_ts) / 1000.0)

    def abort(self, ts: int):
        if self.state in ("open", "tentatively_closed"):
            print(f"[{self.txn_id}] State change: {self.state} -> aborted")
            previous_state = self.state
            self.state = "aborted"
            self.last_update_ts = ts
            TXN_STATE_GAUGE.labels(previous_state).dec()
            TXN_STATE_GAUGE.labels("aborted").inc()
            TXN_LIFETIME.observe((self.last_update_ts - self.open_ts) / 1000.0)

    def verify_abort(self, ts: int):
        if self.state in ("open", "tentatively_closed"):
            print(f"[{self.txn_id}] State change via Coordinator: {self.state} -> verified_aborted")
            previous_state = self.state
            self.state = "verified_aborted"
            self.last_update_ts = ts
            TXN_STATE_GAUGE.labels(previous_state).dec()
            TXN_STATE_GAUGE.labels("verified_aborted").inc()
            TXN_LIFETIME.observe((self.last_update_ts - self.open_ts) / 1000.0)


class Aggregator:
    def __init__(self, outlier_ms: int = 15000, abort_timeout_s: int = 300):
        self.transactions: Dict[str, TransactionState] = {}
        self.outlier_threshold_ms = outlier_ms
        self.abort_timeout_s = abort_timeout_s
        self._lock = threading.Lock()

    def process_event(self, ev: dict, consumer_type: str):
        """Process an event from either the monitor or validator consumer."""
        et = ev.get("type")
        txn_id = ev.get("txn_id")
        if not et or not txn_id:
            return

        EVENT_COUNT.labels(et).inc()

        with self._lock:
            if consumer_type == "coordinator":
                # Events from the coordinator collector are handled differently
                # They provide a ground truth about what is *not* on the broker
                open_txn_ids = set(ev.get("open_transaction_ids", []))
                now = int(time.time() * 1000)
                
                # Find transactions that are no longer open according to the coordinator
                for txn_id, txn in self.transactions.items():
                    if txn.state in ("open", "tentatively_closed") and txn_id not in open_txn_ids:
                        txn.verify_abort(now)
                return

            if et == "transaction_open":
                if txn_id not in self.transactions:
                    self.transactions[txn_id] = TransactionState(txn_id, int(ev["ts_ms"]))
                    TXN_STATE_GAUGE.labels("open").inc()

            elif et == "transaction_close":
                txn = self.transactions.get(txn_id)
                if txn:
                    if consumer_type == "monitor":
                        txn.tentatively_close(int(ev["ts_ms"]))
                    elif consumer_type == "validator":
                        txn.confirm_close(int(ev["ts_ms"]))

            elif et == "inter_step_wait":
                planned = ev.get("planned_wait_ms")
                if planned is not None:
                    gap_seconds = float(planned) / 1000.0
                    INTER_STEP_GAP.observe(gap_seconds)
                    if ev.get("outlier_injected"):
                        INJECTED_OUTLIERS.inc()
                    if planned >= self.outlier_threshold_ms:
                        OUTLIERS.inc()

    def check_for_aborted_transactions(self):
        """Periodically check for timeouts and update watermarks."""
        while True:
            time.sleep(self.abort_timeout_s / 4)
            now = int(time.time() * 1000)
            
            with self._lock:
                # Check for aborts
                for txn in list(self.transactions.values()):  # Iterate over a copy
                    # Case 1: A transaction was tentatively closed but never validated.
                    if txn.state == "tentatively_closed":
                        if txn.tentative_close_ts and (now - txn.tentative_close_ts) / 1000.0 > self.abort_timeout_s:
                            txn.abort(now)
                    # Case 2: A transaction was opened but never even tentatively closed.
                    elif txn.state == "open":
                        if (now - txn.open_ts) / 1000.0 > self.abort_timeout_s:
                            print(f"[{txn.txn_id}] State change: open -> aborted (timeout)")
                            txn.abort(now)
                
                # Update watermarks
                open_transactions = [
                    t for t in self.transactions.values() 
                    if t.state in ("open", "tentatively_closed")
                ]
                
                if open_transactions:
                    high_watermark = max(t.open_ts for t in open_transactions)
                    low_watermark = min(t.open_ts for t in open_transactions)
                    high_watermark_ts_sec = high_watermark / 1000.0
                    low_watermark_ts_sec = low_watermark / 1000.0
                    til_seconds = high_watermark_ts_sec - low_watermark_ts_sec
                    
                    TIL_GAUGE.set(til_seconds)
                    HIGH_WATERMARK_OPEN_TXN_GAUGE.set(high_watermark_ts_sec)
                    LOW_WATERMARK_UNRESOLVED_TXN_GAUGE.set(low_watermark_ts_sec)
                else:
                    TIL_GAUGE.set(0)
                    # If there are no open transactions, the watermarks are undefined,
                    # but setting them to 0 is a reasonable default for Prometheus.
                    HIGH_WATERMARK_OPEN_TXN_GAUGE.set(0)
                    LOW_WATERMARK_UNRESOLVED_TXN_GAUGE.set(0)

                # Clean up very old completed/aborted transactions
                old_ids = [
                    tid for tid, t in self.transactions.items()
                    if t.state in ("closed", "aborted") and (now - t.last_update_ts) / 1000.0 > 300
                ]
                for tid in old_ids:
                    del self.transactions[tid]

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

def kafka_consumer_worker(
    kafka_config: dict,
    topics: List[str],
    group_id: str,
    isolation_level: str,
    aggregator: Aggregator,
    consumer_type: str,
):
    """A worker function for a single Kafka consumer running in a thread."""
    if Consumer is None:
        raise RuntimeError("confluent-kafka not installed.")
    
    config = kafka_config.copy()
    config.update({
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
        "isolation.level": isolation_level,
    })
    consumer = Consumer(config)
    consumer.subscribe(topics)
    print(f"[{consumer_type.upper()}] Consumer started for group '{group_id}' with isolation level '{isolation_level}'")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                sys.stderr.write(f"[{consumer_type.upper()}-ERROR] {msg.error()}\n")
                continue
            try:
                ev = json.loads(msg.value().decode("utf-8"))
                aggregator.process_event(ev, consumer_type)
            except Exception as e:
                sys.stderr.write(f"[{consumer_type.upper()}-DESER-ERROR] {e}\n")
    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()
        print(f"[{consumer_type.upper()}] Consumer closed.")
