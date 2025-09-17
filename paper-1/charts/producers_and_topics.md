graph TD
    subgraph "Producers"
        A[ktx-simulate]
        B[ktx-replay]
        C[ktx-collect]
    end

    subgraph "Kafka Topics"
        D[workflow.transactions]
        E[workflow.steps]
        F[ktxinsights.coordinator.state]
    end

    A --> D
    A --> E
    B --> D
    B --> E
    C --> F
```

**When is a Producer Writing to Which Topic:**

*   **`ktx-simulate` & `ktx-replay`:** These tools produce events to the `workflow.transactions` and `workflow.steps` topics. `ktx-simulate` can produce directly to Kafka, while `ktx-replay` reads from a file and produces to Kafka.
*   **`ktx-collect`:** This tool produces the state of ongoing transactions to the `ktxinsights.coordinator.state` topic.
