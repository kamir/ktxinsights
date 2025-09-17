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

VALIDATOR_LSO_LAG = Gauge(
    "ktxinsights_validator_lso_lag",
    "Lag between the validator consumer's position and the partition's LSO",
    labelnames=("topic", "partition"),
)

OPEN_TX_MAX_TIMESTAMP_GAUGE = Gauge(
    "ktxinsights_open_transaction_max_timestamp_seconds",
    "Timestamp of the most recently opened transaction that is not yet resolved (previously high_watermark)",
)

UNRESOLVED_TX_MIN_TIMESTAMP_GAUGE = Gauge(
    "ktxinsights_unresolved_transaction_min_timestamp_seconds",
    "Timestamp of the oldest transaction that is not yet resolved (previously low_watermark)",
)

UNRESOLVED_TRANSACTION_AGE_P95_SECONDS = Gauge(
    "ktxinsights_unresolved_transaction_age_p95_seconds",
    "The age of the 95th percentile oldest unresolved transaction, providing a robust measure of processing health.",
)


# ---------------------------
# Aggregation Logic
# ---------------------------
class TransactionState:
    """Models the state of a single business transaction, including all its constituent steps."""
    def __init__(self, txn_id: str, open_ts: int, producer_epoch: int, expected_steps: set):
        self.txn_id = txn_id
        self.producer_epoch = producer_epoch
        self.state = "open"  # open, tentatively_closed, closed, aborted, verified_aborted
        self.open_ts = open_ts
        self.last_update_ts = open_ts
        
        # State for multi-step transactions
        self.expected_steps = expected_steps
        self.observed_steps = set()
        self.is_closed = False

    def add_step(self, step_name: str, ts: int):
        """Records that a step of the transaction has been observed."""
        if step_name in self.expected_steps:
            self.observed_steps.add(step_name)
            self.last_update_ts = ts
            # If a step arrives after we thought the transaction was complete,
            # we must reopen it for reconsideration.
            if self.state == "tentatively_closed":
                self._revert_to_open()
            self._check_if_complete()
    
    def _revert_to_open(self):
        """Reverts a tentatively_closed transaction back to open state."""
        print(f"[{self.txn_id}] State change: tentatively_closed -> open (late step arrived)")
        self.state = "open"
        TXN_STATE_GAUGE.labels("tentatively_closed").dec()
        TXN_STATE_GAUGE.labels("open").inc()

    def tentatively_close(self, ts: int):
        """Marks the entire transaction as tentatively closed."""
        if self.state == "open":
            self.is_closed = True
            self.last_update_ts = ts
            self._check_if_complete()

    def _check_if_complete(self):
        """Checks if all expected steps have been observed and the transaction is marked as closed."""
        # This check is now idempotent. It can be called multiple times.
        if self.state == "open" and self.is_closed and self.observed_steps == self.expected_steps:
            print(f"[{self.txn_id}] State change: open -> tentatively_closed (all steps observed)")
            self.state = "tentatively_closed"
            TXN_STATE_GAUGE.labels("open").dec()
            TXN_STATE_GAUGE.labels("tentatively_closed").inc()

    def confirm_close(self, ts: int):
        if self.state == "tentatively_closed":
            print(f"[{self.txn_id}] State change: tentatively_closed -> closed")
            self.state = "closed"
            self.last_update_ts = ts
            TXN_STATE_GAUGE.labels("tentatively_closed").dec()
            TXN_STATE_GAUGE.labels("closed").inc()
            TXN_LIFETIME.observe((self.last_update_ts - self.open_ts) / 1000.0)

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
                # TODO: The set of expected steps should be configurable per transaction type.
                # For now, we'll use a hardcoded default.
                expected = {"stepA", "stepB", "stepC"}
                producer_epoch = ev.get("producer_epoch", -1)

                # Idempotency check: only create a new state if the epoch is higher
                existing_txn = self.transactions.get(txn_id)
                if not existing_txn or producer_epoch > existing_txn.producer_epoch:
                    self.transactions[txn_id] = TransactionState(
                        txn_id, int(ev["ts_ms"]), producer_epoch, expected
                    )
                    TXN_STATE_GAUGE.labels("open").inc()

            elif et == "transaction_step":
                txn = self.transactions.get(txn_id)
                step_name = ev.get("step_name")
                if txn and step_name:
                    txn.add_step(step_name, int(ev["ts_ms"]))

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
                    # Sort transactions by open timestamp to find min, max, and percentiles
                    sorted_transactions = sorted(open_transactions, key=lambda t: t.open_ts)
                    
                    # Min/Max and TIL calculation (the original, simple metric)
                    min_open_ts = sorted_transactions[0].open_ts
                    max_open_ts = sorted_transactions[-1].open_ts
                    til_seconds = (max_open_ts - min_open_ts) / 1000.0
                    TIL_GAUGE.set(til_seconds)
                    OPEN_TX_MAX_TIMESTAMP_GAUGE.set(max_open_ts / 1000.0)
                    UNRESOLVED_TX_MIN_TIMESTAMP_GAUGE.set(min_open_ts / 1000.0)

                    # P95 age calculation (the new, more robust metric)
                    p95_index = int(len(sorted_transactions) * 0.95)
                    p95_transaction = sorted_transactions[p95_index]
                    p95_age_seconds = (now - p95_transaction.open_ts) / 1000.0
                    UNRESOLVED_TRANSACTION_AGE_P95_SECONDS.set(p95_age_seconds)

                else:
                    # If there are no open transactions, all metrics are zero.
                    TIL_GAUGE.set(0)
                    OPEN_TX_MAX_TIMESTAMP_GAUGE.set(0)
                    UNRESOLVED_TX_MIN_TIMESTAMP_GAUGE.set(0)
                    UNRESOLVED_TRANSACTION_AGE_P95_SECONDS.set(0)

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

    last_lso_check = 0
    try:
        while True:
            msg = consumer.poll(1.0)

            # Periodically check LSO lag for the validator
            now = time.time()
            if consumer_type == "validator" and (now - last_lso_check) > 10:
                last_lso_check = now
                for tp in consumer.assignment():
                    try:
                        _low, high = consumer.get_watermark_offsets(tp, timeout=2)
                        committed = consumer.committed([tp], timeout=2)
                        
                        if committed and committed[0].offset > 0:
                            # confluent-kafka-python doesn't directly expose LSO.
                            # The high watermark for a read_committed consumer is effectively the LSO.
                            lso = high
                            lag = lso - committed[0].offset
                            VALIDATOR_LSO_LAG.labels(topic=tp.topic, partition=tp.partition).set(lag)
                    except Exception as e:
                        sys.stderr.write(f"[VALIDATOR-LSO-WARN] Could not get LSO lag for {tp}: {e}\n")

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
