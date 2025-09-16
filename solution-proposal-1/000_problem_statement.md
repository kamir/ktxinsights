# Problem Statement: The Kafka Transaction Observability Gap

## 1. Situation Analysis

Modern distributed systems increasingly rely on Apache Kafka for asynchronous communication. While Kafka's transactional capabilities (`EOS`, Exactly-Once Semantics) provide strong guarantees for data integrity across multiple topics, they introduce a critical **observability gap**. The state of a low-level Kafka transaction (e.g., `Ongoing`, `PrepareCommit`, `Aborted`) is managed by the broker's transaction coordinator and is disconnected from the business-level workflow it represents.

This creates a black box where:
- **Application developers** cannot easily determine if a multi-step business process (e.g., an order fulfillment workflow) has successfully completed or failed within a transaction.
- **SREs and Platform Engineers** can see infrastructure-level metrics (commit rates, consumer lag) but cannot correlate them to specific business transaction failures.
- **Debugging is reactive and inefficient.** When a business process fails, teams must manually correlate application logs, Kafka consumer offsets, and broker metrics to reconstruct the event sequence, wasting valuable time and resources.

## 2. The Core Problem

The fundamental problem is the **lack of a unified view that correlates high-level business transaction semantics with low-level Kafka infrastructure state.**

This manifests in several critical ways:
- **Inability to Proactively Detect "Stuck" Transactions:** A business workflow might be stalled due to an application bug, a slow downstream service, or a misconfigured producer. Without correlation, these appear simply as "long-running" transactions at the broker level, with no clear business impact until an SLA is breached.
- **Ambiguous Failure Scenarios:** When a Kafka transaction is aborted, it's nearly impossible to determine *which* specific business workflow failed and *why* without extensive, manual log analysis.
- **Misattribution of Delays:** Delays in business processes can be caused by application logic (e.g., slow database calls), Kafka consumer lag, or broker-level issues (e.g., ISR churn, high commit latency). Without a correlated view, root cause analysis is guesswork.
- **Lack of Business-Centric SLAs:** It is difficult to define and monitor meaningful SLAs for business workflows (e.g., "99.9% of order fulfillments must complete within 5 seconds") when the completion state is not directly observable.

## 3. Impact

This observability gap leads to:
- **Increased Mean Time to Resolution (MTTR):** Debugging sessions are prolonged and require cross-functional expertise.
- **Reduced System Reliability:** "Stuck" transactions can hold locks, consume resources, and lead to cascading failures.
- **Poor User Experience:** Business processes fail silently or are significantly delayed, impacting end-users.
- **Inability to Make Data-Driven Improvements:** Without clear visibility into workflow performance and failure modes, it is difficult to prioritize engineering efforts.

## 4. The Challenge

The challenge is to build a solution that bridges this gap by creating a **single source of truth** for transaction state. This system must ingest data from both the Kafka infrastructure (transaction coordinator, consumer groups) and the application (business events), correlate them in near real-time, and expose the unified state through actionable dashboards, metrics, and alerts.
