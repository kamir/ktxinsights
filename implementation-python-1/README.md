# Transaction Insights (`txinsights`)

This project is a Python package for gaining visibility into Kafka-based business transactions. It provides tools to simulate, replay, and monitor event streams to understand the performance and reliability of your workflows.

## Project Structure

-   `pyproject.toml`: Defines the package metadata, dependencies, and entry points.
-   `src/txinsights/`: The main package directory containing the core logic.
    -   `simulate.py`: Logic for generating event data.
    -   `replay.py`: Logic for replaying event data to Kafka.
    -   `aggregator.py`: Logic for consuming and aggregating event data.
    -   `report.py`: Logic for generating visual reports.
    -   `cli/`: Sub-package containing the command-line entry points.

## Installation

It is highly recommended to install this package in a virtual environment.

1.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Install the Package in Editable Mode:**
    Installing in editable mode (`-e`) allows you to modify the source code and have the changes immediately reflected without reinstalling.
    ```bash
    pip install -e .
    ```
    This command reads the `pyproject.toml` file, installs all dependencies, and sets up the command-line tools.

## Command-Line Tools

Once installed, the following command-line tools will be available in your environment:

### `tx-simulate`
Generates simulated transaction data.
```bash
# Example: Generate 100 samples and print to stdout
tx-simulate --samples 100

# Example: Generate 500 samples and send to Kafka
tx-simulate --samples 500 --kafka-bootstrap localhost:9092
```

### `tx-replay`
Replays a previously generated `events.jsonl` file to Kafka.
```bash
# Example: Replay a scenario at 1x speed
tx-replay --file path/to/events.jsonl --kafka-bootstrap localhost:9092

# Example: Replay at double speed
tx-replay --file path/to/events.jsonl --kafka-bootstrap localhost:9092 --speed-factor 2.0
```

### `tx-aggregate`
Runs the transaction aggregator to monitor a Kafka stream and expose Prometheus metrics.
```bash
# Example: Connect to Kafka and start the metrics server on port 8000
tx-aggregate --kafka-bootstrap localhost:9092 --listen-port 8000
```

### `tx-report`
Generates a visual HTML report from an `events.jsonl` file.
```bash
# Example: Generate a report from a specific events file
tx-report --file path/to/events.jsonl --out-dir path/to/report
```

### `tx-collect`
Runs the Coordinator Collector to fetch and publish the state of ongoing transactions from the Kafka brokers.
```bash
# Example: Connect to Kafka and start the collector
tx-collect --kafka-bootstrap localhost:9092
```

## Development Workflow

1.  Activate your virtual environment: `source venv/bin/activate`
2.  Install the package: `pip install -e .`
3.  Use the `tx-*` commands to run the tools.
4.  Modify the source code in `src/txinsights/` as needed.
