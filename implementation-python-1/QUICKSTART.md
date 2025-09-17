# Quickstart Guide: Applying `ktxinsights` to Your Application

This guide provides a step-by-step process for integrating the `ktxinsights` toolkit with your own Kafka-based application.

## 1. Instrument Your Application

The core of the `ktxinsights` toolkit is the event stream it consumes. To use the toolkit, you must instrument your application to produce events that conform to the expected format.

### Event Schema

Your application should produce two types of events:

*   **Transaction Events:** These mark the beginning and end of a business transaction.
    *   `type`: `transaction_open` or `transaction_close`
    *   `txn_id`: A unique identifier for the transaction.
    *   `ts_ms`: The timestamp in milliseconds.
*   **Step Events:** These mark the beginning and end of each step within a transaction.
    *   `type`: `step_open` or `step_done`
    *   `txn_id`: The ID of the parent transaction.
    *   `step`: The step number (e.g., 1, 2, 3).
    *   `ts_ms`: The timestamp in milliseconds.

### Example

Here is an example of how you might instrument a simple order processing application:

```python
import json
from confluent_kafka import Producer

producer = Producer({'bootstrap.servers': 'localhost:9092'})

def process_order(order_id):
    txn_id = f"order_{order_id}"

    # 1. Emit transaction_open event
    producer.produce("workflow.transactions", json.dumps({
        "type": "transaction_open",
        "txn_id": txn_id,
        "ts_ms": int(time.time() * 1000)
    }))

    # 2. Emit step events
    for step in range(1, 5):
        producer.produce("workflow.steps", json.dumps({
            "type": "step_open",
            "txn_id": txn_id,
            "step": step,
            "ts_ms": int(time.time() * 1000)
        }))

        # ... do some work ...

        producer.produce("workflow.steps", json.dumps({
            "type": "step_done",
            "txn_id": txn_id,
            "step": step,
            "ts_ms": int(time.time() * 1000)
        }))

    # 3. Emit transaction_close event
    producer.produce("workflow.transactions", json.dumps({
        "type": "transaction_close",
        "txn_id": txn_id,
        "ts_ms": int(time.time() * 1000)
    }))

    producer.flush()
```

## 2. Configure and Run the Monitoring Services

Once your application is instrumented, you can run the `ktxinsights` monitoring services to analyze the event stream.

### Step 2.1: Create a Configuration File

Copy one of the templates from the `config/` directory and fill in the connection details for your Kafka cluster.

### Step 2.2: Start the Services

Open two separate terminals to run the aggregator and the collector.

**Terminal 1: Start the Transaction Aggregator**
```bash
ktx-aggregate --config-file config/your_config.properties
```

**Terminal 2: Start the Coordinator Collector**
```bash
ktx-collect --config-file config/your_config.properties
```

## 3. Observe the Results

With the monitoring services running, you can view the live metrics from the aggregator:

```bash
curl http://localhost:8000/metrics
```

Look for the `ktxinsights_transactions_by_state` gauge to see your application's transactions moving through the state machine in real-time. You can also use these metrics to build dashboards and alerts in your monitoring system of choice.
