kminion is great for the infrastructure-side truth around Kafka topics, partitions, and consumer groups. It won’t tell you “this business transaction is closed” (it doesn’t read payloads or transaction markers), but it can prove or disprove the underlying conditions that create your symptoms: producer slowdowns, stalled partitions, growing consumer lag, ISR issues, etc. Use it alongside your app/business exporter (the one we built) to get both layers:
	•	kminion → infra/SLO signals (topics/partitions/offsets/lag/replication health)
	•	your exporter → business signals (open age per txn, outliers, closed/aborted counts)

Here’s how it helps—concretely.

What kminion gives you (useful here)
	•	Per-partition end offsets and per-consumer-group committed offsets → compute lag precisely.
	•	Rates of new messages per topic/partition (via rate(increase(end_offset))) → detect producer slowdowns/stalls.
	•	Time since last movement of a partition’s end offset → detect stalled producers on status/control topics.
	•	Replication/ISR health (under-replicated, offline partitions) → explain systemic slowdowns unrelated to your app.
	•	Consumer group state (no members, rebalances) → explain “mysterious” gaps while you read.

Limitation: kminion does not expose transactional markers or payload content; it cannot assert “tx closed.” Treat it as ground truth for the pipes, not the business semantics.

Patterns that work well

1) See producer slowdowns that masquerade as “long open transactions”

Use your status/control topic (e.g., workflow.steps or workflow.audit) as a canary.
	•	Partition stall detection

# No new records for 5m on any partition of the status topic
max by (topic, partition)(
  absent_over_time( derivative(kminion_topic_partition_end_offset{topic="workflow.steps"}[5m]) > 0 [5m:] )
)

If you prefer a simpler approximation:

# “Almost zero” produce rate over 5m
sum by (topic)(
  rate(kminion_topic_partition_end_offset{topic="workflow.steps"}[5m])
) < 0.01

Alert: “Status topic stalled → transactions might appear ‘open’ only because no new events are produced.”

2) Confirm “commit visibility” lags independently of your app

Point a validator consumer group (read_committed) at your control/data topics. kminion shows its lag:

# Validator lag too high for too long
max by (topic, consumer_group)(
  kminion_consumer_group_lag{consumer_group="validator-rc"}
) > 1000

If the validator keeps lagging, your monitor (read_uncommitted) will see progress, but the cluster’s committed view lags—explains why “closed” can’t be confirmed yet.

3) Detect intermittent 15s outliers at the pipe level

Your simulator injects 15s pauses between steps. You can see this as bursty produce patterns:

# High variance in produce rate → possible long gaps between bursts
stddev_over_time(
  rate(kminion_topic_partition_end_offset{topic="workflow.steps"}[1m])
[10m:]) > some_threshold

It won’t label “outlier transaction”, but when you correlate with your business exporter’s outlier counter, you’ll know whether the outliers are app-logic vs pipe-level.

4) Prove it’s the cluster, not the app

Use kminion’s broker/replication metrics to rule in/out cluster issues:
	•	Under-replicated partitions spike → expect higher produce latency and commit visibility delays.
	•	Controller changes / broker down → temporary lag explosions are expected.

Create a single Grafana dashboard:
	•	Row 1: kminion topic end offset rate, validator group lag, ISR health.
	•	Row 2: your exporter open transactions gauge, txn duration histogram, inter-step outlier counter.

When the business outlier counter spikes without kminion anomalies → likely app-level (slow external call, lock contention, etc.). When both spike → pipe/cluster contributing.

Suggested alerts (practical)
	•	Status topic stalled
	•	Expr: produce rate to workflow.steps < threshold for ≥ 5m
	•	Meaning: Producers not emitting; open-age may grow.
	•	Validator lag high
	•	Expr: kminion_consumer_group_lag{consumer_group="validator-rc"} > N for ≥ 2m
	•	Meaning: Commit visibility delayed; don’t trust “tentative closed” yet.
	•	ISR degraded
	•	Expr: under-replicated partitions > 0 for ≥ 1m
	•	Meaning: Broker health degrading; expect higher latencies.
	•	Rebalance flapping
	•	Expr: high churn in consumer group members over 10m
	•	Meaning: Intermittent gaps due to rebalances, not app bugs.

How it fits your design
	•	Keep your monitor on read_uncommitted and your validator on read_committed.
	•	Emit audit/close from the producer (post-commit or in control topic).
	•	Use kminion to:
	•	Prove that messages are (or aren’t) flowing.
	•	Quantify how far the validator is behind.
	•	Explain anomalies via cluster health signals.

This combination gives you:
	•	Live UX (monitor),
	•	Ground truth (validator + audit),
	•	Root cause visibility (kminion).

If you want, I can sketch a minimal Grafana dashboard JSON wiring kminion + your exporter, and a couple of PromQL recording rules so your alerts don’t recompute heavy expressions.
