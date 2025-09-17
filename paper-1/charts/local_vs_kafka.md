graph TD
    subgraph "Local Mode"
        A[ktx-simulate] --> B[events.jsonl]
        B --> C[ktx-aggregate --file]
    end

    subgraph "Kafka Mode"
        D[ktx-simulate] --> E[events.jsonl]
        E --> F[ktx-replay] --> G[Kafka]
        G --> H[ktx-aggregate]
    end
```

**Compare the mode with and without Kafka - what are the differences?**

*   **Local Mode:** The `ktx-aggregate` service reads events directly from a file. This is useful for testing the core logic of the aggregator and for generating reports without the need for a running Kafka cluster.
*   **Kafka Mode:** The `ktx-replay` service reads events from a file and produces them to a Kafka cluster. The `ktx-aggregate` service then consumes these events from Kafka. This mode provides a more realistic test of the entire system, including the performance overhead of the Kafka cluster itself.
