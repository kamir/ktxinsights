Great, nuanced question — and it gets at the heart of what is and isn’t possible with Kafka’s transactional model.

⸻

What Lenses.io Actually Does

Lenses.io (now part of Celonis) provides a data observability layer over Kafka:
	•	It reads broker JMX metrics, topic metadata, and message payloads.
	•	For exactly-once semantics (EOS), it can surface:
	•	Producer IDs and their current transactional state (via Admin API + transaction coordinator metrics).
	•	Transaction start/commit/abort rates from broker metrics.
	•	The list of in-flight transactions (from the transaction log topic _transaction_state).
	•	Correlate producers, partitions, and uncommitted offsets.

So, in its UI, you can see something like:
	•	“Producer PID 1234 has 2 open transactions, last heartbeat at t=XYZ.”
	•	“5 transactions are pending commit, average open time = 8.3s.”
	•	“Aborted transactions count in last 5m = N.”

This is powerful because it gives you visibility into the coordinator state, not just topic offsets.

⸻

But — It Still Has Limitations

Lenses does not:
	•	Show you the contents of uncommitted transactions (unless you read with read_uncommitted yourself).
	•	Give you business-transaction closure semantics (e.g., “Workflow #42 is complete”), unless you encode that yourself in payloads.

It’s mostly infra-level transaction monitoring:
	•	How many are open, for how long.
	•	Are producers committing or aborting too often?
	•	Is the transaction coordinator overloaded?

⸻

Comparing to Your Problem

Your core challenge (as we discussed):
	•	You produce multiple workflow-step messages inside a transaction.
	•	You want to detect when a transaction is effectively closed even though you may be consuming with read_uncommitted.

Lenses.io would help with:
	•	Listing open TX and their age → you’d know “this producer TX has been open > 15m.”
	•	Detecting TX that never commit (potentially stuck producers).
	•	Alerting on too many open TX or long commit latency cluster-wide.

But it doesn’t solve:
	•	Determining that a particular workflow (identified by txn_id) has completed in business terms — you still need a control event or validator consumer for that.
	•	Real-time outlier detection per workflow across multiple steps.

⸻

Tracking Open, Non-Committed Transactions

Yes — using the Kafka Admin API and _transaction_state topic, or by reading the transaction coordinator metrics (as Lenses does), you can track:
	•	Transaction state: Ongoing, PrepareCommit, PrepareAbort, CompleteCommit, etc.
	•	Start timestamp and producerId / epoch.
	•	Open transaction count cluster-wide.

But this is still at producer-transaction granularity (a producer may group many messages / workflows into a single TX).
If you need per-workflow monitoring, you still need your app to include the workflow key or ID inside the message payload.

⸻

Verdict for Your Use Case
	•	Lenses’ transaction visibility would definitely complement your monitoring setup — it can show you open TX age and count, helping detect “stuck” producers early.
	•	It is not a full solution to your business requirement (per-workflow closure tracking), but it removes a blind spot: you’d know whether your cluster still sees a TX as open or already committed/aborted.

Think of it as:
	•	Cluster truth: Lenses / Admin API → “Is there still an open TX at broker level?”
	•	Application truth: Your monitor/validator/exporter → “Have all steps been produced and committed for workflow X?”

Combine them and you get both layers of insight.

⸻

Would you like me to show you how to query the _transaction_state topic or Admin API yourself, so you could build a lightweight internal dashboard (without buying Lenses)? This could be a good open-source way to get similar transaction-state insight.
