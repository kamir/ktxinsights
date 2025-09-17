graph TD
    subgraph "Producers"
        A[ktx-simulate]
        B[ktx-replay]
    end

    subgraph "Kafka Topics"
        C[workflow.transactions]
        D[workflow.steps]
        E[ktxinsights.coordinator.state]
    end

    subgraph "Consumers"
        F[Monitor Consumer]
        G[Validator Consumer]
        H[Coordinator Consumer]
    end

    A --> C
    A --> D
    B --> C
    B --> D

    C --> F
    D --> F
    C --> G
    D --> G
    E --> H
```

**Which Consumer Reads from Which Topic:**

*   **Monitor Consumer (`isolation.level=read_uncommitted`):** Reads from `workflow.transactions` and `workflow.steps` to get a real-time view of all events, including those in uncommitted transactions.
*   **Validator Consumer (`isolation.level=read_committed`):** Reads from `workflow.transactions` and `workflow.steps` to get a view of only committed transactions.
*   **Coordinator Consumer:** Reads from `ktxinsights.coordinator.state` to get the state of ongoing transactions directly from the Kafka brokers.
