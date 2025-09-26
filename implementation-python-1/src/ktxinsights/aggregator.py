"""
Transaction Aggregator for the Kafka Transaction Insight System.
"""

import time
from datetime import datetime
import threading

from confluent_kafka import Consumer, KafkaException

from ktxinsights.collector import TransactionInfo

from prometheus_client import Counter, Histogram, Gauge

# active transaction info by txn_id
active_tx_info: dict[str, TransactionInfo] = {}

# Event for clean shutdown of all threads
stop_event = threading.Event()

# Lock for thread synchronization
lock = threading.Lock()

class Aggregator:
    abort_timeout_s: int

    def __init__(self, abort_timeout_s: int = 60):
        self.abort_timeout_s = abort_timeout_s

        # Prometheus metrics

        # total number of uncommitted events for each (assumed) open transaction
        self.TX_EVENTS = Gauge(
            'ktx_producer_lag_nr_total',
            'Total number of uncommitted events for open transactions',
        )

        # duration of completed transactions from the first event to the last event
        self.TX_DURATION = Histogram(
            'ktx_tx_duration_seconds',
            'Duration of completed transactions in seconds'
        )

        # number of active transactions being tracked
        self.TX_ACTIVE = Gauge(
            'ktx_active_transactions',
            'Number of active transactions being tracked'
        )
    
        # other events like outliers, errors, etc.
        self.OUTLIER_EVENTS = Counter(
            'ktx_outlier_events_total',
            'Total number of outlier events detected',
            ['reason']
        )

    def process_event(self, tx_info: TransactionInfo):
        if tx_info.tx_state == "open":
            active_tx_info[tx_info.tx_id] = tx_info

        if tx_info.tx_state == "closed":
            if tx_info.tx_id in active_tx_info:
                del active_tx_info[tx_info.tx_id]
            # Update transaction duration histogram
            self.TX_DURATION.observe(tx_info.tx_duration_s)

    def update_tx_metrics(self):
        # Update number of uncommitted events and active transactions
        self.TX_EVENTS.set(sum(tx.event_count for tx in active_tx_info.values() if tx.tx_state == "open"))
        self.TX_ACTIVE.set(len(active_tx_info))

def consumer_tx_state(agr: Aggregator, state_topic: str, consumer_config: dict):
    consumer = Consumer(consumer_config)
    consumer.subscribe([state_topic])
    try:
        print("[DEBUG] Starting transaction state consumer...")
        while not stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            # Extract txn_id from message key
            txn_id = msg.key().decode("utf-8") if msg.key() else None
            # Extract transaction info from message value
            try:
                txn_info = msg.value().decode("utf-8") if msg.value() else None
                tx_info = TransactionInfo("").from_json(txn_info) if txn_info else None
            except Exception as e:
                print(f"[ERROR] Failed to decode message value: {e}")
                continue
            if tx_info is not None and tx_info.isValid():
                with lock:
                    agr.process_event(tx_info)
                    agr.update_tx_metrics()
                print(f"[DEBUG] transaction state consumer received message with txn_id: {txn_id}")
            else:
                print(f"[WARNING] Invalid transaction info received for txn_id: {txn_id}")
    except Exception as e:
        print(f"[ERROR] transaction state consumer: {e}")
        stop_event.set()
    finally:
        consumer.close()

def abort_stale_transactions(agr: Aggregator):
    while not stop_event.is_set():
        time.sleep(5)
        now = datetime.now()
        to_abort = []
        with lock:
            for tx_info in active_tx_info.values():
                if tx_info.isTimedOut(agr.abort_timeout_s, now):
                    to_abort.append(tx_info.tx_id)
            for abort_tx_id in to_abort:
                print(f"[INFO] Aborting stale transaction: {abort_tx_id}")
                del active_tx_info[abort_tx_id]
                agr.OUTLIER_EVENTS.labels(reason="aborted_transaction").inc()
                agr.update_tx_metrics()

def aggregate(aggregator: Aggregator, state_topic: str, consumer_config: dict):
    consumer_config.update({
        'group.id': 'ktx-aggregator-group',
        #'auto.offset.reset': 'earliest',
        #'enable.auto.commit': False,
        'auto.offset.reset': 'latest',
    })

    thread1 = threading.Thread(target=consumer_tx_state, args=(aggregator, state_topic, consumer_config,))
    thread2 = threading.Thread(target=abort_stale_transactions, args=(aggregator,))

    thread1.start()
    thread2.start()

    try:
        while thread1.is_alive() and thread2.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[INFO] KeyboardInterrupt detected")
    finally:
        stop_event.set()

    print("[INFO] Shutting down Aggregator...")
    thread1.join()
    thread2.join()
