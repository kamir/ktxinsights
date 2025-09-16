# Kafka Transaction Insight System

This directory contains a proof-of-concept implementation for a Kafka Transaction Insight System, as detailed in the accompanying architecture and requirements documents.

## 1. Components

- `000_problem_statement.md`: Defines the core problem this solution addresses.
- `001_requirements.md`: Outlines the requirements for the system.
- `002_solution_architecture.md`: Describes the overall architecture.
- `event-flow-simulation.py`: A Python script to generate realistic test data scenarios.
- `replay_events.py`: A script to replay a generated scenario to Kafka with high fidelity.
- `transaction_aggregator.py`: The core service that consumes events and exposes Prometheus metrics.

## 2. Workflow for Reproducible Testing

The recommended workflow separates data generation from test execution to ensure that your measurements are always based on a consistent, known workload.

**Step 1: Generate and Persist a Scenario (Run Once)**
First, use a scenario script to generate the event data and the ground truth report. This creates a static test asset. For example, to generate the "high-throughput" scenario:
```bash
./scenarios/01_high_throughput.sh
```
This creates the `scenarios/01_high_throughput` directory containing the `events.jsonl` file and a `report` sub-directory with the benchmark data.

**Step 2: Run the Live Monitor**
In one terminal, start the transaction aggregator. It will connect to Kafka and wait for events.
```bash
./venv/bin/python3 solution-proposal-1/transaction_aggregator.py --kafka-bootstrap localhost:9092
```

**Step 3: Replay the Scenario for Testing (Run as Needed)**
In a second terminal, use the `replay_events.py` script to publish the previously generated scenario to Kafka.
```bash
./venv/bin/python3 solution-proposal-1/replay_events.py \
    --file scenarios/01_high_throughput/events.jsonl \
    --kafka-bootstrap localhost:9092
```
The aggregator will process the events, and you can observe the live metrics at `http://localhost:8000/metrics`. You can repeat this step as many times as needed for consistent testing.

## 3. Setup and Installation

### Prerequisites
- Python 3.10+
- An accessible Kafka cluster (or Docker for a local setup)

### Dependencies
Install the required Python libraries using pip:
```bash
pip install confluent-kafka prometheus-client
```

## 4. Next Steps

With the aggregator running, you can now:
- Configure a Prometheus instance to scrape the `http://localhost:8000/metrics` endpoint.
- Import the Prometheus data source into Grafana to build dashboards based on the `txinsights_*` metrics.
- Set up alerts in Alertmanager based on the metrics to detect stuck transactions, high latency, or other anomalies.

## 5. Generating a Visual Report

For offline analysis, you can generate a visual HTML report from an `events.jsonl` file. This is useful for sharing the results of a specific simulation run.

**Step 1: Ensure you have an `events.jsonl` file**
If you haven't already, generate one using the event simulator:
```bash
python3 solution-proposal-1/event-flow-simulation.py --samples 200 > events.jsonl
```

**Step 2: Run the report generator**
Execute the `generate_report.py` script, pointing it to your events file. The report will be saved in a `report` directory by default.
```bash
python3 solution-proposal-1/generate_report.py --file events.jsonl
```

**Step 3: View the Report**
Open the generated `report/report.html` file in your web browser to see the histograms and summary statistics for the transaction stream.
