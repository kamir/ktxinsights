Let us review the exercise with critical eyes.
The app, which produces the messages outside the Kafka cluster does open tx and inside the cluster, when listening on the topics, we are not sure when a tx is closed. How can we determine, when a tx is closed while we keep reading the non committed messages?


Short version: if you read with isolation.level=read_uncommitted, you cannot know for sure that a business transaction is closed until the broker writes the commit marker for the producer’s transaction. Uncommitted data can still be aborted. So you either (a) wait for commit visibility (read_committed) or (b) add an out-of-band signal that is not subject to the producer’s transaction.

Below are practical patterns that teams use, with trade-offs and a recommended setup.

What’s fundamentally possible
	•	Kafka commit truth lives in the broker’s transaction markers. Clients only see the “final state” when consuming with read_committed.
	•	With read_uncommitted, you can observe progress (good for live telemetry), but you cannot prove closure until commit (or abort) actually happens.

Options to determine “closed” while still observing in-flight data

A) Dual-consumer validation (monitor + validator)
	•	Monitor consumer: read_uncommitted to see all step/status events instantly. Maintains an in-flight map keyed by txn_id: first-seen timestamp, last activity, last step.
	•	Validator consumer: separate group with read_committed, lagging slightly behind. It confirms which of the previously seen records actually made it into a committed transaction.
	•	Logic:
	•	Mark a transaction TentativelyClosed when you observe the “last step/close” event via the monitor.
	•	Promote to Closed when the validator reaches the same offsets and sees those records (committed).
	•	If the validator never sees them (because the producer aborted), mark Aborted and clear it from “open”.
	•	Pros: No producer changes; precise truth from the committed view.
	•	Cons: Slight complexity (two consumers and reconciliation by (topic, partition, offset) or by record keys/timestamps).

B) Out-of-band audit/status topic (commit-anchored)

Have the producer send start/heartbeat/close for each txn_id to a separate topic designed for monitoring.

Two safe variants:
	1.	Post-commit close: After commitTransaction() succeeds, produce a non-transactional txn_closed audit event.
	•	Consumers can trust that “close” means really closed (commit already succeeded).
	•	You still get in-flight visibility from read_uncommitted on the data topics.
	2.	Same-transaction control topic: Emit txn_open/step/txn_close into a dedicated control topic inside the same transaction as the data.
	•	Consumers use read_committed on the control topic only to know the authoritative state, while they can watch data topics with read_uncommitted for progress.
	•	Guarantees atomic visibility: control and data commit together.

	•	Pros: Very clear semantics; minimal consumer complexity.
	•	Cons: Requires a small producer change. Variant (1) introduces a slight ordering race on the wire (the audit event may arrive before all committed data becomes visible to some consumers), but since the commit already succeeded, it’s still a truthful “closed” signal.

C) Heartbeats + timeout inference (best-effort)
	•	Producer emits periodic txn_heartbeat messages to a status topic outside the data transaction.
	•	If last heartbeat is older than a threshold and you saw the “last step”, infer LikelyClosed (or LikelyStuck if you didn’t see the last step).
	•	Later, confirm via validator (Option A) or by seeing the audit close (Option B).
	•	Pros: Great for live SLO monitoring and alerting on “open age”.
	•	Cons: Heuristic; still needs a source of truth for final closure.

D) Kafka Streams session-window tracker (inference engine)
	•	Build a Streams/KTable keyed by txn_id, with session windows that close after no activity for X seconds.
	•	Classify states: Open, Quiet (about to close), Closed (confirmed) if you combine with A or B.
	•	Pros: Simple operational model; nice for dashboards.
	•	Cons: Still needs confirmation source for “closed vs aborted”.

⸻

Recommended setup (balanced, low-risk)
	1.	Keep your monitor on read_uncommitted for instantaneous progress (open age, step gaps).
	2.	Add a tiny audit topic:
	•	Emit txn_open as soon as you start.
	•	After the producer’s commitTransaction() returns success, emit a non-transactional txn_closed audit message with: txn_id, first_event_ts, last_event_ts, duration_ms.
	3.	Run a validator consumer on read_committed (data or control topic) to reconcile tentative closures and flag aborts.
	4.	In your aggregator, model states:
	•	Open (saw open; no close; last activity age = now – last event)
	•	TentativelyClosed (monitor saw last step/close)
	•	Closed (validator confirmed commit OR audit close arrived)
	•	Aborted (validator never sees committed records for those offsets)

This gives you:
	•	Real-time visibility (open durations, outliers)
	•	Authoritative closure detection
	•	Abort detection (no more “ghost closed” transactions)

⸻

Minimal Spring for Kafka sketch (audit close after commit)

// Pseudocode: outline only
@Service
public class TxnProducer {

  private final KafkaTemplate<String, TxEvent> txTemplate;      // transactional
  private final KafkaTemplate<String, AuditEvent> auditTemplate; // non-transactional

  public void runBusinessTxn(String txnId, List<Step> steps) {
    txTemplate.executeInTransaction(kt -> {
      kt.send("workflow.steps", txnId, TxEvent.open(txnId));
      for (Step s: steps) {
        // ... do work ...
        kt.send("workflow.steps", txnId, TxEvent.stepDone(txnId, s.no()));
      }
      kt.send("workflow.transactions", txnId, TxEvent.close(txnId));
      return null;
    });
    // At this point, the transaction has been committed successfully
    auditTemplate.send("workflow.audit",
        txnId,
        AuditEvent.closed(txnId, /*durationMs*/ /*timestamps*/));
  }
}

	•	If you prefer atomic control data, put the control topic in the same transaction and let the validator (read_committed) be your truth source.

⸻

What if producer changes are impossible?

Use Option A (dual consumers) only:
	•	Track all in-flight transactions from read_uncommitted (progress + tentative closure).
	•	Confirm closure by a lagging read_committed group reaching the offsets for those records.
	•	If confirmation never happens within a timeout window ⇒ Aborted.

⸻

Summary
	•	With read_uncommitted alone, you can’t prove closure.
	•	Add either a commit-anchored audit signal (simple and robust) or a validator consumer (no producer change) — ideally both.
	•	This gives you real-time monitoring and accurate classification (Closed vs Aborted), enabling reliable outlier detection and alerts.
