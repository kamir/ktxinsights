graph TD
    A[ktx-simulate] -->|Parameters| B(SimConfig)
    B --> C{samples}
    B --> D{concurrency}
    B --> E{steps}
    B --> F{delays}
    B --> G{outlier_prob}
    B --> H{failure_prob}

    subgraph "Output Event Stream"
        I[transaction_open]
        J[step_open]
        K[step_done]
        L[inter_step_wait]
        M[transaction_close]
    end

    A --> I
    A --> J
    A --> K
    A --> L
    A --> M
```

**How the Data Generator Works:**

The `ktx-simulate` tool generates a stream of events that mimic a real-world transactional workflow. It is configured with a `SimConfig` object that defines the characteristics of the generated data.

**Possible Patterns:**

*   **High-Throughput:** High `samples` and `concurrency`, low `delays`.
*   **Slow, Complex:** High `steps`, low `concurrency`, high `delays`.
*   **Unreliable/Spiky:** High `outlier_prob` and `outlier_ms`.
*   **Failing:** Non-zero `failure_prob`.
