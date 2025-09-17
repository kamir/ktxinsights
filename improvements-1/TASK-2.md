# TASK-2: Add Coordinator Collector Details to the Paper

The paper is currently light on the operational details of the `CoordinatorCollector`. Adding this information will make the toolkit seem more robust and production-ready.

**Action:** Add a new section to the paper that details the following for the `CoordinatorCollector`:

*   **Permissions:** The required ACLs for the Kafka principal running the collector (e.g., `DESCRIBE` on the cluster).
*   **Overhead:** A discussion of the expected overhead, which should be minimal as it's a lightweight polling mechanism.
*   **Sampling:** An explanation of how the polling interval can be configured to balance data freshness with the load on the Kafka brokers.
*   **Restricted Environments:** A discussion of how the collector would behave in an environment with restricted permissions (e.g., it would gracefully fail and log an error, and the aggregator would fall back to its timeout-based mechanism for detecting aborted transactions).


### 2. Renaming "Transactional Watermarks"

This is another excellent point. The term "watermark" is already heavily used in Kafka, and overloading it could cause confusion.

*   **Plan:** I will rename "Transactional Watermarks" to something more descriptive, such as **"Business Transaction Timestamps"** or **"Transaction Lifecycle Timestamps."** I will also add a clarification that these are based on the timestamps of the business events themselves, not on Kafka's internal offset watermarks.

