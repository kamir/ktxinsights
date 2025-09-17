Nice-to-have extensions

	•	Expose LSO stall diagnostics: per partition, track (time_lso_stalled_seconds) and the set of active transactional.ids responsible (sampled, not labeled per-id). This pinpoints where read_committed consumers will stop making progress.  ￼
	•	CLI parity with KIP-664 tool: add ktx tx list|describe|suspect|advise-abort commands that mirror kafka-transactions.sh output, but augmented with your business correlation.  ￼
	•	EOS tests for Streams: if you plan to cover Streams, add cases influenced by KIP-892 (state store semantics), showing recovery time and duplication checks under EOS. 