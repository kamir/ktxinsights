# User Manual: Transaction Insights (`txinsights`) Toolkit

## 1. Introduction

Welcome to the `txinsights` toolkit. This suite of tools is designed to provide deep visibility into your Kafka-based business transactions. By correlating application-level events with the internal state of the Kafka broker, `txinsights` helps you quickly identify performance bottlenecks, detect failed transactions, and understand the overall health of your event-driven workflows.

This manual will guide you through setting up a test environment using Confluent Cloud and running a full demonstration of the toolkit's capabilities.

## 2. Test Setup with Confluent Cloud

To effectively test the `txinsights` tools, you need a Kafka cluster. Confluent Cloud provides a fully managed service that is easy to set up.

### Step 2.1: Create a Confluent Cloud Cluster
1.  Log in to your Confluent Cloud account.
2.  Create a new "Basic" cluster. Give it a name (e.g., `txinsights-test-cluster`).
3.  Choose a cloud provider and region.
4.  Launch the cluster.

### Step 2.2: Create Topics
The tools require two topics for application events and one for the collector's output.
1.  Navigate to the "Topics" section of your cluster.
2.  Create the following three topics, using the default settings:
    *   `workflow.transactions`
    *   `workflow.steps`
    *   `txinsights.coordinator.state`

### Step 2.3: Generate API Keys
You will need two sets of API keys: one for the application (simulator, replayer) and one for the collector, which requires administrative permissions.

**1. Application API Key (Read/Write)**
1.  Go to "API keys" under your cluster settings.
2.  Create a new key with "Global access".
3.  **Important:** Save the generated Key and Secret. You will need them for your configuration.

**2. Collector API Key (Admin)**
1.  Go to the "Cloud API keys" section of your Confluent Cloud account (this is different from the cluster-level keys).
2.  Create a new key with the "Cloud Admin" role.
3.  **Important:** Save this Key and Secret as well.

### Step 2.4: Create a Configuration File
For ease of use, create a configuration file named `ccloud.properties` in your project root. This file will store your connection details. **Remember to add this file to your `.gitignore` to avoid committing credentials.**

```properties
# ccloud.properties

# Kafka Cluster Connection
bootstrap.servers=<YOUR_CCLOUD_BOOTSTRAP_SERVER>
security.protocol=SASL_SSL
sasl.mechanisms=PLAIN
sasl.username=<YOUR_APPLICATION_API_KEY>
sasl.password=<YOUR_APPLICATION_API_SECRET>

# Schema Registry (if needed, not required for this tool)
# schema.registry.url=<YOUR_SCHEMA_REGISTRY_URL>
# basic.auth.credentials.source=USER_INFO
# basic.auth.user.info=<SR_API_KEY>:<SR_API_SECRET>
```

## 3. Running a Full Test Cycle

This section will guide you through a complete end-to-end test.

### Step 3.1: Install the Package
Ensure you have created a virtual environment and installed the `txinsights` package in editable mode:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Step 3.2: Generate a Test Scenario (Run Once)
First, generate the data and ground truth report for a specific workload. We'll use the "unreliable, spiky" scenario for this demonstration.
```bash
./scenarios/03_unreliable_spiky.sh
```
This will create the `scenarios/03_unreliable_spiky` directory containing the `events.jsonl` file and the benchmark report.

### Step 3.3: Start the Monitoring Services
Open two separate terminals to run the aggregator and the collector.

**Terminal 1: Start the Transaction Aggregator**
This service listens for application events and exposes the primary metrics.
```bash
tx-aggregate --kafka-bootstrap <YOUR_CCLOUD_BOOTSTRAP_SERVER> \
             --kafka-group tx-agg-demo-1
```

**Terminal 2: Start the Coordinator Collector**
This service connects to the Admin API to fetch broker-level transaction states.
```bash
tx-collect --kafka-bootstrap <YOUR_CCLOUD_BOOTSTRAP_SERVER>
```

### Step 3.4: Replay the Scenario to Confluent Cloud
With the monitors running, open a third terminal to replay the generated scenario.
```bash
tx-replay --file scenarios/03_unreliable_spiky/events.jsonl \
          --kafka-bootstrap <YOUR_CCLOUD_BOOTSTRAP_SERVER>
```
You will see log messages in the aggregator and collector terminals as they process the replayed events.

### Step 3.5: Observe the Results
While the replay is running, you can view the live metrics from the aggregator:
```bash
curl http://localhost:8000/metrics
```
Look for the `txinsights_transactions_by_state` gauge. You will see transactions moving through the `open`, `tentatively_closed`, and finally `closed` or `aborted` states, providing a real-time view of your workflow's health.
