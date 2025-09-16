# Solution Architecture: Kafka Transaction Insight System

## 1. Architectural Vision

The proposed solution is a multi-component, event-driven architecture designed to provide a unified and real-time view of business transactions running on Kafka. It is built on the principles of separation of concerns, scalability, and observability. The system ingests data from multiple sources, correlates it to build a comprehensive state model, and exposes this state through industry-standard monitoring and alerting tools.

## 2. Core Components

The architecture consists of four main components: the **Event Simulator**, the **Event Replayer**, the **Transaction Aggregator**, and the **Monitoring Stack**.



### 2.1. Event Simulator (`event-flow-simulation.py`)

- **Purpose:** A standalone Python script responsible for generating realistic test data. This component is crucial for development, testing, and validation of the entire system.
- **Responsibilities:**
    - Simulate a configurable number of concurrent business transactions, each consisting of multiple steps.
    - Introduce random delays and occasional outliers to mimic real-world conditions.
    - Emit structured JSON events to a set of Kafka topics, representing the lifecycle of each business transaction (`transaction_open`, `step_open`, `step_done`, `transaction_close`).
    - Each event is tagged with a unique `txn_id` for correlation.
- **Technology:** Python, `asyncio`, `confluent-kafka`.

### 2.2. Event Replayer (`replay_events.py`)

- **Purpose:** A standalone Python script responsible for replaying a persisted event scenario to Kafka. This component is crucial for reproducible testing.
- **Responsibilities:**
    - Read a persisted `events.jsonl` file.
    - Publish the events to the appropriate Kafka topics.
    - Preserve the original timing and delays between events by reading their timestamps and inserting corresponding `sleep` calls.
    - Optionally allow for adjusting the replay speed.
- **Technology:** Python, `confluent-kafka`.

### 2.3. Transaction Aggregator (`transaction-aggregator.py`)

- **Purpose:** The core of the system, responsible for consuming, correlating, and analyzing the event streams.
- **Responsibilities:**
    - **Dual-Consumer Strategy:**
        - **Monitor Consumer:** Consumes business events with `isolation.level=read_uncommitted` to get an immediate view of in-flight transactions.
        - **Validator Consumer:** Consumes the same topics with `isolation.level=read_committed` to get a lagging but authoritative view of committed data.
    - **State Management:**
        - Maintains an in-memory state machine for each business transaction, tracking its state (`Open`, `TentativelyClosed`, `Closed`, `Aborted`, `Stuck`).
        - Correlates business events with Kafka transaction metadata (future enhancement, via Admin API).
    - **Metric Calculation:**
        - Computes KPIs such as transaction duration, open age, and inter-step gaps.
        - Detects and flags outliers.
    - **Prometheus Exporter:**
        - Exposes the aggregated state and KPIs via a `/metrics` endpoint for consumption by Prometheus.
- **Technology:** Python, `confluent-kafka`, `prometheus_client`.

### 2.3. Monitoring Stack

- **Purpose:** The user-facing component of the system, responsible for data visualization and alerting.
- **Components:**
    - **Prometheus:**
        - Scrapes the `/metrics` endpoint of the Transaction Aggregator.
        - Stores the time-series data.
        - Evaluates alerting rules.
    - **Grafana:**
        - Queries Prometheus to visualize the data in pre-built dashboards.
        - Provides interactive panels for exploring transaction health, identifying outliers, and diagnosing issues.
    - **Alertmanager:**
        - Receives alerts from Prometheus.
        - Manages alert routing, grouping, and notification to the appropriate channels (e.g., Slack, PagerDuty).
- **Technology:** Prometheus, Grafana, Alertmanager.

## 3. Data Flow

1.  The **Event Simulator** is run *once* to generate a persistent `events.jsonl` file for a specific workload scenario.
2.  The **Event Replayer** reads the `events.jsonl` file and publishes the events to Kafka, faithfully reproducing the original timing.
3.  The **Transaction Aggregator**'s `Monitor Consumer` reads these events in real-time, creating and updating the state of in-flight transactions.
3.  The `Validator Consumer` reads the same events after they have been committed, allowing the Aggregator to transition the state of transactions from `TentativelyClosed` to `Closed` or `Aborted`.
4.  The Aggregator continuously updates its internal state and exposes it as Prometheus metrics.
5.  **Prometheus** scrapes these metrics at regular intervals.
6.  **Grafana** queries Prometheus to populate its dashboards, providing a visual representation of the system's state.
7.  **Prometheus** evaluates its alerting rules and, if a condition is met, fires an alert to **Alertmanager**.
8.  **Alertmanager** sends a notification to the configured receivers.

## 4. Future Enhancements

- **Coordinator Collector:** A separate service that polls the Kafka Admin API to get a list of open transactions at the broker level. This data can be fed into the Aggregator to provide an even more accurate view of the system state.
- **Durable Storage:** For historical analysis and reporting, the Aggregator's state can be periodically snapshotted to a durable store like PostgreSQL or a time-series database.
