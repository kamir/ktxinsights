# How to Generate Workload Scenarios

The `event-flow-simulation.py` script is a flexible tool designed to simulate a wide variety of workloads. By adjusting its command-line parameters, you can model different performance profiles, from high-throughput, low-latency systems to unreliable and "spiky" environments.

## Key Parameters for Workload Customization

### Core Workload Parameters
-   `--samples`: Controls the **total volume** of transactions.
-   `--concurrency`: Defines the number of transactions running **in parallel**, controlling the load intensity.
-   `--steps`: Sets the number of steps within each transaction, defining the **complexity** of the workflow.

### Latency and Performance Parameters
-   `--pre-min` & `--pre-max`: Defines the random delay range *before* each step, simulating **"work time"**.
-   `--inter-min` & `--inter-max`: Defines the random delay range *between* steps, simulating **"wait time"** or network latency.

### Reliability and Anomaly Parameters
-   `--outlier-prob`: The probability (0.0 to 1.0) that a step will experience a massive delay, controlling the **frequency of anomalies**.
-   `--outlier-ms`: The duration of the outlier delay, controlling the **severity of anomalies**.

---

## Example Workload Scenario Configurations

By combining these parameters, you can create distinct and reproducible workload profiles for testing.

### 1. High-Throughput, Low-Latency System
This scenario simulates a fast, efficient system under heavy concurrent load.

**Parameters:**
```bash
--samples 500 \
--concurrency 50 \
--pre-max 200 \
--inter-max 100 \
--outlier-prob 0.001
```

### 2. Slow, Complex Workflow
This scenario simulates a process with significant work at each stage and a higher number of steps, but lower concurrency.

**Parameters:**
```bash
--samples 100 \
--concurrency 10 \
--steps 10 \
--pre-min 1000 \
--pre-max 4000 \
--inter-min 500 \
--inter-max 1500
```

### 3. Unreliable or "Spiky" System
This scenario simulates a system that performs well on average but suffers from frequent, severe hiccups.

**Parameters:**
```bash
--samples 200 \
--concurrency 20 \
--outlier-prob 0.05 \
--outlier-ms 20000
```

By creating shell scripts for these profiles, you can easily generate different datasets to test how your monitoring and aggregation system behaves under various conditions.
