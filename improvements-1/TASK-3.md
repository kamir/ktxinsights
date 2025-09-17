# TASK-3: Add a Baseline Comparison to the Paper

The paper makes claims of superiority, but it doesn't currently provide a concrete, quantitative comparison.

**Action:** Create a new test scenario called `04_hanging_transaction`. This scenario will simulate a transaction that opens but never closes, and it will be designed so that it does *not* trigger any alerts in standard monitoring tools like KMinion (e.g., no consumer lag, no unusual throughput). Then:

1.  Create a new local analysis script for this scenario.
2.  Add a new appendix to the paper that shows the output of `ktx-compare` for this scenario, clearly identifying the aborted transaction.
3.  In the same appendix, include screenshots or example output from a tool like KMinion or the Confluent Control Center, showing that they do *not* detect this issue.
4.  Add a detailed explanation of why `ktxinsights` is able to catch this type of "business-level" failure while the other tools, which focus on infrastructure-level metrics, cannot.


### 3. Coordinator Collector Details

The paper is currently light on the operational details of the `CoordinatorCollector`. Adding this information will make the toolkit seem more robust and production-ready.

*   **Plan:** I will add a new section to the paper that details the following for the `CoordinatorCollector`:
    *   **Permissions:** The required ACLs for the Kafka principal running the collector (e.g., `DESCRIBE` on the cluster).
    *   **Overhead:** A discussion of the expected overhead, which should be minimal as it's a lightweight polling mechanism.
    *   **Sampling:** An explanation of how the polling interval can be configured to balance data freshness with the load on the Kafka brokers.
    *   **Restricted Environments:** A discussion of how the collector would behave in an environment with restricted permissions (e.g., it would gracefully fail and log an error, and the aggregator would fall back to its timeout-based mechanism for detecting aborted transactions).
