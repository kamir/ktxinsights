graph TD
    subgraph "Data Generation"
        A[ktx-simulate] --> B[events.jsonl]
    end

    subgraph "Ground Truth"
        B --> C[ktx-report] --> D[report_stats.json]
    end

    subgraph "Live Analysis"
        B --> E[ktx-replay] --> F[Kafka]
        F --> G[ktx-aggregate] --> H[Prometheus Metrics]
        F --> I[ktx-collect] --> E
    end

    subgraph "Comparison"
        D --> J[ktx-compare]
        H --> J
    end
```

**What Components are Included in the Analysis:**

*   **`ktx-simulate`:** Generates the `events.jsonl` file.
*   **`ktx-report`:** Generates the ground-truth `report_stats.json` file from the `events.jsonl` file.
*   **`ktx-replay`:** Replays the `events.jsonl` file to a Kafka cluster.
*   **`ktx-aggregate`:** Consumes from Kafka and exposes live metrics.
*   **`ktx-collect`:** Fetches coordinator state from Kafka and publishes it to a topic for the aggregator.
*   **`ktx-compare`:** Compares the ground-truth `report_stats.json` with the live metrics from the aggregator.
