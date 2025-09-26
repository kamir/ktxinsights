"""
Coordinator Collector for the Kafka Transaction Insight System.

This service connects to the Kafka cluster using the Admin API to fetch
information about ongoing transactions directly from the transaction coordinator.
It then publishes this data to an internal topic for consumption by the aggregator.
"""
from confluent_kafka import Consumer, Producer, KafkaException
import threading
from datetime import datetime
import queue
import time

class CollectorConfig:
    # State topic to publish collected state information
    state_topic: str
    # Transaction topic to listen to for events with txn_id headers
    tx_topic: str

    # generic Consumer configuration for connecting to Kafka
    consumer_config: dict
    # generic Producer configuration for connecting to Kafka
    producer_config: dict

class TransactionInfo:
    # Transaction ID
    tx_id: str
    # Transaction state: "open" or "closed", no "aborted" state tracked for now
    tx_state: str
    # first event timestamp
    tx_start: str
    # current event timestamp
    tx_now: str
    # tx_now - tx_start
    tx_duration_s: float
    # number of events seen for this transaction
    event_count: int

    def __init__(self, tx_id: str):
        '''Initialize a new TransactionInfo instance.'''
        self.tx_id = tx_id
        self.tx_state = "open"
        now = datetime.now()
        self.tx_start = now.isoformat()
        self.tx_now = self.tx_start
        self.tx_duration_s = 0
        self.event_count = 1

    def increment(self):
        '''Increment the event count and update the current timestamp and duration.'''
        self.event_count += 1
        now = datetime.now()
        self.tx_now = now.isoformat()
        self.tx_duration_s = (datetime.fromisoformat(self.tx_now) - datetime.fromisoformat(self.tx_start)).total_seconds()
        return self

    def close(self):
        '''Mark the transaction as closed and update the current timestamp and duration.'''
        self.tx_state = "closed"
        now = datetime.now()
        self.tx_now = now.isoformat()
        self.tx_duration_s = (now - datetime.fromisoformat(self.tx_start)).total_seconds()
        return self

    def to_dict(self):
        '''Convert the transaction info to a dictionary.'''
        return {
            "tx_id": self.tx_id,
            "tx_state": self.tx_state,
            "tx_start_ts_iso_utc": self.tx_start,
            "tx_now_ts_iso_utc": self.tx_now,
            "tx_duration_s": self.tx_duration_s,
            "tx_event_count": self.event_count
        }

    def to_json(self):
        '''Convert the transaction info to a JSON string.'''
        import json
        return json.dumps(self.to_dict())

    def from_dict(self, data: dict):
        '''Populate fields from a dictionary.'''
        self.tx_id = data.get("tx_id", self.tx_id)
        self.tx_state = data.get("tx_state", self.tx_state)
        self.tx_start = data.get("tx_start_ts_iso_utc", self.tx_start)
        self.tx_now = data.get("tx_now_ts_iso_utc", self.tx_now)
        self.tx_duration_s = data.get("tx_duration_s", self.tx_duration_s)
        self.event_count = data.get("tx_event_count", self.event_count)
        return self

    def from_json(self, json_str: str):
        '''Populate fields from a JSON string.'''
        import json
        data = json.loads(json_str)
        return self.from_dict(data)

    def isValid(self):
        '''Check if the transaction info has a valid transaction ID.'''
        try:
            return (self.tx_id is not None and self.tx_id != "") \
                and (self.tx_state in ["open", "closed"]) \
                and (self.event_count > 0) \
                and (self.tx_duration_s >= 0) \
                and (self.tx_start is not None and self.tx_start != "") \
                and (self.tx_now is not None and self.tx_now != "") \
                and (datetime.fromisoformat(self.tx_now) >= datetime.fromisoformat(self.tx_start))
        except Exception:
            return False     

    def isTimedOut(self, abort_timeout_s: int, now: datetime = None):
        '''Check if the transaction has timed out based on the abort timeout.'''
        try:
            if now is None:
                now = datetime.now()
            event_time = datetime.fromisoformat(self.tx_now)
            return (now - event_time).total_seconds() > abort_timeout_s
        except Exception:
            return False

# Shared dictionary to store the last seen time for each txn_id
active_tx_info: dict[str, TransactionInfo] = {}
command_queue = queue.Queue()


# Event for clean shutdown of all threads
stop_event = threading.Event()


# Lock for thread synchronization
lock = threading.Lock()

def consumer_uncommitted(collConf: CollectorConfig, consumer_config: dict):
    consumer = Consumer(consumer_config)
    consumer.subscribe([collConf.tx_topic])
    try:
        print("[DEBUG] Starting uncommitted consumer...")
        while not stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            # Extract txn_id from the message headers
            txn_id = None
            for header, value in msg.headers():
                if header == 'txn_id':
                    txn_id = value.decode('utf-8')
                    break
            if txn_id:
                with lock:
                    if txn_id not in active_tx_info:
                        active_tx_info[txn_id] = TransactionInfo(txn_id)
                    else:
                        active_tx_info[txn_id] = active_tx_info[txn_id].increment()
                    command_queue.put((txn_id, active_tx_info[txn_id].to_json()))
            print(f"[DEBUG] Uncommitted consumer received message with txn_id: {txn_id}")
    except Exception as e:
        print(f"[ERROR] Uncommitted consumer: {e}")
        stop_event.set()
    finally:
        consumer.close()

def consumer_committed(collConf: CollectorConfig, consumer_config: dict):
    consumer = Consumer(consumer_config)
    consumer.subscribe([collConf.tx_topic])
    try:
        print("[DEBUG] Starting committed consumer...")
        while not stop_event.is_set():
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())
            # Extract txn_id from the message headers
            txn_id = None
            for header, value in msg.headers():
                if header == 'txn_id':
                    txn_id = value.decode('utf-8')
                    break
            if txn_id:
                with lock:
                    if txn_id in active_tx_info:
                        command_queue.put((txn_id, active_tx_info[txn_id].close().to_json()))
                        del active_tx_info[txn_id]
                    else:
                        print(f"[DEBUG] Committed txn_id {txn_id} not found in active transactions.")
            print(f"[DEBUG] Committed consumer received message with txn_id: {txn_id}")
    except Exception as e:
        print(f"[ERROR] Committed consumer: {e}")
        stop_event.set()
    finally:
        consumer.close()

def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR] Delivery failed for {msg.key()}: {err}")
        # Optional: raise Exception(err)
    else:
        print(f"[DEBUG] Message delivered to {msg.topic()} [k:{msg.key()} - p:{msg.partition()}]")

def producer(collConf: CollectorConfig, producer_config: dict):
    producer = Producer(producer_config)
    try:
        print("[DEBUG] Starting producer...")
        while not stop_event.is_set():
            while not command_queue.empty():
                event, tx_info = command_queue.get()
                producer.produce(collConf.state_topic, key=event, value=tx_info, callback=delivery_report)
            producer.flush()
            producer.poll(0)
            time.sleep(1)
    except Exception as e:
        print(f"[ERROR] Producer: {e}")
        stop_event.set()
    finally:
        producer.flush()

def collect(collConf: CollectorConfig):
    print("Starting Collector service...")

    config_uncommitted = {
        **collConf.consumer_config,
        'auto.offset.reset': 'latest',
        'isolation.level': 'read_uncommitted'
    }
    if 'group.id' not in config_uncommitted:
        config_uncommitted['group.id'] = 'ktx-uncommitted-group'
    else:
        config_uncommitted['group.id'] += '-uncommitted'

    config_committed = {
        **collConf.consumer_config,
        'auto.offset.reset': 'latest',
        'isolation.level': 'read_committed'
    }
    if 'group.id' not in config_committed:
        config_committed['group.id'] = 'ktx-committed-group'
    else:
        config_committed['group.id'] += '-committed'

    producer_config = {
        **collConf.producer_config,
        'acks': 'all',
        "socket.keepalive.enable": True,
    }

    thread1 = threading.Thread(target=consumer_uncommitted, args=(collConf, config_uncommitted,))
    thread2 = threading.Thread(target=consumer_committed, args=(collConf, config_committed,))
    thread3 = threading.Thread(target=producer, args=(collConf, producer_config,))

    thread1.start()
    thread2.start()
    thread3.start()

    try:
        while thread1.is_alive() or thread2.is_alive() or thread3.is_alive():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("[INFO] KeyboardInterrupt detected")
    finally:
        stop_event.set()

    print("[INFO] Shutting down Collector...")
    thread1.join()
    thread2.join()
    thread3.join()
