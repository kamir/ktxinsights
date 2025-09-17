Here are the main, battle-tested options to export Kafka consumer lag as Prometheus metrics, plus when to use which and how to start fast.

The shortlist
	1.	Kafka Lag Exporter (a.k.a. kafka-lag-exporter)

	•	Purpose-built Prometheus exporter for consumer group lag and lag-as-seconds (residence time). Good docs, Helm chart, Strimzi examples.  ￼
	•	Recent releases continue; community issues active.  ￼
Best for: Quick Prometheus/Grafana setup focused on lag & latency per group/topic/partition.

	2.	Burrow (LinkedIn)

	•	A service that evaluates consumer status from __consumer_offsets, exposes HTTP API (and notifiers); you pair it with a small exporter (or scrape Burrow-Prometheus bridge) to get metrics. Great for SLOs without hand-tuned thresholds.  ￼
Best for: Robust “is this group healthy?” judgments across many clusters; alerting without brittle thresholds.

	3.	KMinion (Redpanda Data)

	•	A feature-rich Prometheus exporter covering broker, topic, consumer group lag (per-topic/per-partition granularity), and an optional end-to-end round-trip latency probe topic. Ships community Grafana dashboards.  ￼
Best for: One exporter to cover infra + lag (and a synthetic produce/consume probe) in one place.

JMX exporter + broker metrics alone generally won’t give you group lag directly; you still need one of the above (or custom math).  ￼

⸻

Quick choices (rule of thumb)
	•	You just want lag/lag-seconds fast: pick Kafka Lag Exporter.
	•	You want a health service with smart status + notifications: add Burrow.
	•	You want infra + lag + synthetic probe from one exporter: choose KMinion.

⸻

Fast start (copy/paste)

A) Kafka Lag Exporter (Docker)

docker run --rm -p 8000:8000 \
  -e KAFKA_BROKERS=broker1:9092 \
  -e POLL_INTERVAL_MS=10000 \
  -e METRICS_PORT=8000 \
  seglo/kafka-lag-exporter:latest
# Prometheus target: http://host:8000/metrics

Grafana dashboards and Helm/Strimzi examples are in the repo. It also exposes residence time (seconds) estimates per group/topic/partition.  ￼

B) Burrow (service) + metrics

# Run burrow (configure ZK/Kafka/Clusters in burrow.toml)
docker run --rm -p 8000:8000 \
  -v $(pwd)/burrow.toml:/etc/burrow/burrow.toml \
  linkedin/burrow:latest
# Scrape via a small Prometheus bridge or poll Burrow’s HTTP and export.

Burrow calculates consumer status from committed offsets without per-metric thresholds.  ￼

C) KMinion (Prometheus exporter)

docker run --rm -p 8080:8080 \
  -e KM_BROKERS=broker1:9092 \
  -e KM_SASL_ENABLED=false \
  -e KM_TLS_ENABLED=false \
  -e KM_METRICS_SERVER_ADDRESS=:8080 \
  redpandadata/kminion:latest
# Prometheus target: http://host:8080/metrics

Enable its built-in probe to measure end-to-end latency across your cluster, and use the published Grafana dashboards.  ￼

⸻

Useful PromQL snippets
	•	Total lag per consumer group

sum by (consumer_group) (kafka_consumergroup_group_lag)

(Adjust metric names per exporter; KMinion and kafka-lag-exporter expose different names.)  ￼
	•	Lag as seconds (if not provided):
Approximate with end-offset rate:

sum by (consumer_group) (group_lag)
  / clamp_min(sum by (topic) (rate(topic_end_offset[5m])), 0.001)

Some exporters (kafka-lag-exporter) expose residence time directly; otherwise you compute it.  ￼
	•	Alert: validator group lag too high

max by (consumer_group) (kminion_consumer_group_lag{consumer_group="validator-rc"}) > 1000

Tune thresholds per throughput.  ￼

⸻

How this helps your use-case (open/closed transaction visibility)
	•	Use one of these exporters (I’d start with KMinion or Kafka Lag Exporter) to watch:
	•	Per-group lag on your validator (read_committed) consumer—when it spikes, commit visibility is delayed (explains why “closed” isn’t yet confirmable).
	•	Produce rate / end offset rate on your status/control topic—when it stalls, your “open age” grows for non-application reasons.
	•	Pair with your business exporter (the one we wrote) to correlate:
	•	Infra signals (kminion/lag-exporter) vs
	•	Business signals (open transactions, tentative closures, outliers).
This makes it clear whether a delay is due to cluster/consumer lag or application workflow.

If you tell me your environment (Confluent/Strimzi/vanilla, auth, TLS) I can give you a ready Helm chart or Docker Compose for one of these, plus a Grafana dashboard wired to your topics and consumer groups.
