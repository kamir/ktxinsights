# Transaction Insights (`ktxinsights`)

`ktxinsights` is a lightweight, open-source toolkit for monitoring business transactions in Apache Kafka.

## Overview

This toolkit provides a suite of tools to help you understand the performance and reliability of your transactional Kafka applications. It is designed to bridge the gap between low-level Kafka metrics and high-level business workflows.

## Features

*   **Dual-Consumer Architecture:** Correlates `read_uncommitted` and `read_committed` event streams to track the complete lifecycle of business transactions.
*   **Transactional Watermarks:** A novel set of metrics to quantify the "transactional integrity" of your system in real-time.
*   **Generate then Replay:** A validation methodology that uses a ground-truth benchmark to precisely quantify the performance overhead of your Kafka infrastructure.
*   **Coordinator Collector:** A service that connects to the Kafka cluster's Admin API to fetch the list of ongoing transactions directly from the transaction coordinator.

## Configuration

The `ktxinsights` toolkit can be configured to connect to different Kafka environments. All configuration files are located in the `config/` directory.

To configure a new environment, copy one of the templates and fill in the required details.

### Environments

*   `config/ccloud.properties.template`: For connecting to a Confluent Cloud cluster.
*   `config/local.properties.template`: For connecting to a standard local Kafka installation.
*   `config/cp-all-in-one.properties.template`: For connecting to a local `cp-all-in-one` Docker-based environment.

## Usage

### Running a Local Analysis

The `run_local_analysis.sh` script provides a self-contained way to test the toolkit without connecting to a live Kafka cluster.

```bash
./ccloud-testing/run_local_analysis.sh
```

This script will:
1.  Generate a test scenario.
2.  Run the `ktx-aggregate` service in file-reading mode.
3.  Run the `ktx-compare` service to generate a console report and an HTML report.

### Running Against a Live Kafka Cluster

The `run_analysis_test.sh` script can be used to run the toolkit against a live Kafka cluster.

```bash
./ccloud-testing/run_analysis_test.sh <path_to_config.properties> <scenario_script>
```

Example:
```bash
./ccloud-testing/run_analysis_test.sh config/ccloud.properties scenarios/01_high_throughput.sh
```

This will start all the necessary services, replay the chosen scenario to your Kafka cluster, and generate a comparison report.
