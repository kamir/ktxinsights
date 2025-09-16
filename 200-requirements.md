Topic Transaction Insights – Combined Solution Requirements

1) Vision

Provide end-to-end transaction visibility in Kafka that bridges infrastructure-level truth (transaction coordinator state, commit/abort rates, consumer lag) with business-level truth (workflow transactions, steps, duration, outliers). The system must answer:
	•	Is the transaction open/committed/aborted at the broker?
	•	Which workflow (txn_id) is affected? How long has it been open?
	•	Are delays caused by cluster issues, consumer lag, or application logic?

2) Goals & Non‑Goals

Goals
	•	Correlate Kafka transaction state with application workflow events in near real-time.
	•	Detect stuck/long-running transactions and aborts reliably.
	•	Quantify commit visibility (read_committed) vs progress (read_uncommitted).
	•	Provide actionable alerts and dashboards (Prometheus + Grafana).

Non‑Goals (initial)
	•	Forensics on message payloads beyond keys/headers needed for correlation.
	•	Cross-cluster replication insight (covered later via CDC/Mirrormaker metrics).

3) Personas
	•	SRE / Platform Engineer: cares about broker/coordinator health and commit latency.
	•	Data/Streaming Engineer: correlates workflow steps with Kafka transactions.
	•	Team Lead / Analyst: reviews SLA breaches, outliers, and trend reports.

4) Key Use Cases
	1.	Open TX Age Monitor: Show all broker‑level open transactions with age; correlate to workflows.
	2.	Commit Confirmation Lag: Identify when read_committed consumers trail read_uncommitted monitor.
	3.	Aborted TX Detection: Flag application workflows whose data never appears as committed.
	4.	Outlier Analysis: Detect 15s+ inter-step gaps; attribute to app vs infra causes.
	5.	Root Cause Panel: Single place to see TX state, consumer lag, ISR health, and workflow status.

5) Data Sources & Signals
	•	Broker / Coordinator:
	•	JMX: transaction-coordinator metrics (counts, latency, state distribution).
	•	Internal log: _transaction_state topic / Admin API for open TX list (producerId, epoch, state, start timestamp).
	•	Topic/Partition:
	•	End-offset progression (kminion or equivalent) to measure produce rate/stalls.
	•	Consumer-group lag (read_committed validator vs monitor group).
	•	Application (Business):
	•	txn_open/step/txn_close control or audit topic, or step events in data topics.
	•	Optional heartbeats txn_heartbeat for live age monitoring.

6) Correlation Model

Entity: BusinessTransaction
	•	Identifiers: txn_id (business), producerId, producerEpoch (infra), optional headers for mapping.
	•	Timestamps: first_seen_ms, last_activity_ms, commit_ms, abort_ms.
	•	Offsets: per (topic,partition) range touched (if available) for validator reconciliation.
	•	Derived fields: open_age_ms, duration_ms, state.

States (authoritative + inferred):
	•	Open (broker shows ongoing OR monitor sees activity without commit).
	•	TentativelyClosed (monitor saw final step/close event but commit unconfirmed).
	•	Closed (validator observed committed events OR audit close after commit).
	•	Aborted (validator never sees the tentative close events as committed; broker shows abort).
	•	Stuck (Open with open_age_ms > threshold and no recent activity/heartbeat).

7) Functional Requirements
	1.	Ingestion:
	•	Collect broker JMX metrics (Prometheus JMX exporter).
	•	Read _transaction_state (via Admin API or internal consumer) at configurable intervals.
	•	Consume application control/audit topic(s) and optional step events.
	•	Consume kminion (or similar) metrics for end offsets and consumer lag.
	2.	State Builder / Reconciler:
	•	Maintain in-memory + durable store (e.g., RocksDB/LevelDB or PostgreSQL) of BusinessTransaction.
	•	Reconcile monitor (read_uncommitted) with validator (read_committed) by (topic,partition,offset) or idempotent keys.
	•	Merge coordinator state (open/prepare/commit/abort) with business signals.
	3.	Outlier & SLA Engine:
	•	Compute inter-step gaps, transaction duration percentiles, and flag outliers (e.g., ≥ 15000 ms).
	•	Detect commit visibility lag: validator lag per topic/group.
	4.	APIs:
	•	REST/GraphQL to query transactions by state, age, id, topic.
	•	Endpoints for histograms/percentiles and current SLO status.
	5.	Exporters:
	•	Prometheus metrics namespace txinsights_* (see §9).
	6.	Dashboards & Alerts:
	•	Grafana dashboards for broker TX health, open-age tables, outlier trends, validator lag.
	•	Alertmanager rules (see §10).

8) Implementation Sketch
	•	Collectors (Go or Python):
	•	coordinator-collector: polls Admin API / _transaction_state for open TX list; exposes metrics + posts to aggregator.
	•	business-collector: consumes control/audit topic(s) (read_uncommitted), optional step events, emits business metrics/events.
	•	validator-collector: consumes read_committed, confirms commits, tags aborts.
	•	Aggregator / Correlator (service):
	•	Builds the unified state machine per txn_id.
	•	Persists summaries
	•	Serves API and Prometheus metrics (or separate exporter process).
	•	Storage:
	•	Hot state: in-memory with periodic snapshots.
	•	Durable: PostgreSQL / SQLite for history & reports.

9) Prometheus Metrics (examples)

# Counts & states
txinsights_open_transactions{cluster="A"}  
txinsights_stuck_transactions{cluster="A"} 
txinsights_aborted_transactions_total{cluster="A"}

# Durations (histograms in seconds)
# - transaction duration (open->commit)
# - commit visibility lag (monitor last offset -> validator visibility)
txinsights_tx_duration_seconds_bucket{...}
txinsights_commit_visibility_lag_seconds_bucket{...}

# Inter-step gaps / outliers
txinsights_interstep_gap_seconds_bucket{...}
txinsights_interstep_outliers_total{...}

# Reconciliation health
txinsights_transactions_tentative{...}
txinsights_transactions_confirmed{...}

10) Alerts (Alertmanager)
	•	Open TX Age High
	•	Expr: txinsights_open_transactions{age_bin="gt_15m"} > 0 for 5m
	•	Action: page SRE
