Great — here’s a compact consumer/aggregator that ingests the simulated events (from a JSON-Lines file/stdin or from Kafka), computes latency distributions, flags outliers, and prints a readable report with percentiles.

It pairs with the simulator I sent earlier.

⸻

aggregate_workflows.py

#!/usr/bin/env python3
"""
Aggregate latency metrics from simulated (or real) workflow events.

Supports:
- JSON Lines from --file (or stdin)
- Kafka topics via --kafka-bootstrap

Event types expected (from the simulator):
  transaction_open, step_open, step_done, inter_step_wait, transaction_close

Outputs:
- Counts, durations, inter-step gap stats, outliers
- Top slow transactions
- Optional CSV dumps
"""

import argparse
import json
import sys
import time
from collections import defaultdict, deque
from statistics import mean, median
from typing import Dict, List, Optional, Tuple

try:
    from confluent_kafka import Consumer
except Exception:
    Consumer = None  # Optional


# ---------------------------
# Utilities
# ---------------------------
def pct(vals: List[float], p: float) -> float:
    """Compute percentile p in [0,100] using simple nearest-rank on sorted list."""
    if not vals:
        return 0.0
    arr = sorted(vals)
    k = max(1, int(round(p / 100.0 * len(arr))))
    return float(arr[k - 1])


def fmt_ms(ms: float) -> str:
    return f"{ms:.1f} ms"


def fmt_s(ms: float) -> str:
    return f"{ms/1000.0:.3f} s"


def now_ms() -> int:
    return int(time.time() * 1000)


# ---------------------------
# Aggregation state
# ---------------------------
class Aggregator:
    def __init__(self, outlier_ms: int = 15000, derive_inter_step: bool = False):
        # Transaction-level
        self.txn_open_ts: Dict[str, int] = {}
        self.txn_close_ts: Dict[str, int] = {}
        self.txn_durations: List[float] = []

        # Step-level
        # For deriving inter-step gaps if needed
        self.last_step_done_ts: Dict[str, int] = {}
        self.inter_step_gaps: List[float] = []
        self.inter_step_outliers: int = 0
        self.outlier_threshold_ms = outlier_ms

        # For direct outlier flag from events
        self.injected_outliers_seen: int = 0

        # Counts
        self.counts = defaultdict(int)

        # If True, compute gaps by difference between consecutive step boundaries
        self.derive_inter_step = derive_inter_step

        # Keep top slow txns
        self.slowest: List[Tuple[str, float]] = []  # (txn_id, duration_ms)
        self._max_slowest_kept = 10

    def _maybe_record_slowest(self, txn_id: str, dur_ms: float):
        self.slowest.append((txn_id, dur_ms))
        self.slowest.sort(key=lambda x: x[1], reverse=True)
        if len(self.slowest) > self._max_slowest_kept:
            self.slowest.pop()

    def on_event(self, ev: dict):
        et = ev.get("type")
        self.counts[f"type:{et}"] += 1

        if et == "transaction_open":
            txn = ev["txn_id"]
            self.txn_open_ts[txn] = int(ev["ts_ms"])

        elif et == "transaction_close":
            txn = ev["txn_id"]
            ts = int(ev["ts_ms"])
            self.txn_close_ts[txn] = ts
            if txn in self.txn_open_ts:
                dur = ts - self.txn_open_ts[txn]
                self.txn_durations.append(dur)
                self._maybe_record_slowest(txn, dur)

        elif et == "inter_step_wait":
            # If the simulator publishes this, prefer planned_wait_ms for stats of intended waits
            planned = ev.get("planned_wait_ms")
            if planned is not None:
                gap = float(planned)
                self.inter_step_gaps.append(gap)
                if ev.get("outlier_injected"):
                    self.injected_outliers_seen += 1
                if gap >= self.outlier_threshold_ms:
                    self.inter_step_outliers += 1

        elif et == "step_done" and self.derive_inter_step:
            # Derive gap from previous done to next step open (requires tracking elsewhere)
            txn = ev["txn_id"]
            ts = int(ev["ts_ms"])
            # store last done; next step_open will compute gap
            self.last_step_done_ts[txn] = ts

        elif et == "step_open" and self.derive_inter_step:
            txn = ev["txn_id"]
            ts = int(ev["ts_ms"])
            prev_done_ts = self.last_step_done_ts.get(txn)
            if prev_done_ts is not None:
                gap = ts - prev_done_ts
                self.inter_step_gaps.append(float(gap))
                if gap >= self.outlier_threshold_ms:
                    self.inter_step_outliers += 1

    def summarize(self) -> str:
        lines = []
        total_events = sum(v for k, v in self.counts.items() if k.startswith("type:"))

        lines.append("=== Aggregation Summary ===")
        lines.append(f"Total events: {total_events}")
        lines.append("Event counts:")
        for k in sorted(self.counts):
            if k.startswith("type:"):
                lines.append(f"  {k[5:]}: {self.counts[k]}")

        # Transactions
        n_txn = len(self.txn_durations)
        lines.append("")
        lines.append(f"Transactions closed: {n_txn}")
        if n_txn:
            durations = self.txn_durations
            lines.append(f"  avg:  {fmt_ms(mean(durations))}  ({fmt_s(mean(durations))})")
            lines.append(f"  med:  {fmt_ms(median(durations))}")
            lines.append(f"  p90:  {fmt_ms(pct(durations, 90))}")
            lines.append(f"  p95:  {fmt_ms(pct(durations, 95))}")
            lines.append(f"  p99:  {fmt_ms(pct(durations, 99))}")
            lines.append("  Top slow transactions:")
            for txn_id, dur in self.slowest:
                lines.append(f"    {txn_id}: {fmt_ms(dur)}")

        # Inter-step gaps
        n_gaps = len(self.inter_step_gaps)
        lines.append("")
        lines.append(f"Inter-step gaps observed: {n_gaps}")
        if n_gaps:
            gaps = self.inter_step_gaps
            lines.append(f"  avg:  {fmt_ms(mean(gaps))}")
            lines.append(f"  med:  {fmt_ms(median(gaps))}")
            lines.append(f"  p90:  {fmt_ms(pct(gaps, 90))}")
            lines.append(f"  p95:  {fmt_ms(pct(gaps, 95))}")
            lines.append(f"  p99:  {fmt_ms(pct(gaps, 99))}")
            lines.append(f"  outliers ≥ {fmt_ms(self.outlier_threshold_ms)}: {self.inter_step_outliers}")
            if self.injected_outliers_seen:
                lines.append(f"  injected_outliers_seen (from events): {self.injected_outliers_seen}")

        return "\n".join(lines)

    def dump_csv(self, txn_csv: Optional[str], gap_csv: Optional[str]) -> None:
        if txn_csv:
            with open(txn_csv, "w", encoding="utf-8") as f:
                f.write("txn_id,duration_ms\n")
                # We only stored durations; re-derive mapping from slowest plus all
                # For simplicity, reconstruct from open/close tables
                for txn, open_ts in self.txn_open_ts.items():
                    close_ts = self.txn_close_ts.get(txn)
                    if close_ts is None:
                        continue
                    f.write(f"{txn},{close_ts - open_ts}\n")
        if gap_csv:
            with open(gap_csv, "w", encoding="utf-8") as f:
                f.write("gap_ms\n")
                for g in self.inter_step_gaps:
                    f.write(f"{int(g)}\n")


# ---------------------------
# Input readers
# ---------------------------
def read_jsonl(file_path: Optional[str]):
    stream = sys.stdin if not file_path else open(file_path, "r", encoding="utf-8")
    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # tolerate junk
                continue
    finally:
        if file_path:
            stream.close()


def read_kafka(bootstrap: str, topics: List[str], group_id: str, max_events: Optional[int], idle_timeout_s: float):
    if Consumer is None:
        raise RuntimeError("confluent-kafka not installed. `pip install confluent-kafka`")

    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
        "session.timeout.ms": 20000,
    })
    consumer.subscribe(topics)

    seen = 0
    last_msg_ms = now_ms()
    try:
        while True:
            msg = consumer.poll(0.2)
            if msg is None:
                if (now_ms() - last_msg_ms) > idle_timeout_s * 1000:
                    break
                continue
            if msg.error():
                continue
            last_msg_ms = now_ms()
            try:
                ev = json.loads(msg.value().decode("utf-8"))
                yield ev
                seen += 1
                if max_events and seen >= max_events:
                    break
            except Exception:
                continue
    finally:
        consumer.close()


# ---------------------------
# CLI
# ---------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Aggregate workflow events (JSONL or Kafka) into latency stats.")
    src = p.add_mutually_exclusive_group(required=False)
    src.add_argument("--file", type=str, help="Path to JSONL events (defaults to stdin if omitted)")
    src.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers (host:port)")
    p.add_argument("--kafka-topics", type=str, nargs="+",
                   default=["workflow.transactions", "workflow.steps"],
                   help="Kafka topics to consume (when Kafka mode is used)")
    p.add_argument("--kafka-group", type=str, default="workflow-aggregator",
                   help="Kafka consumer group id")
    p.add_argument("--kafka-max-events", type=int, default=None,
                   help="Stop after N events (Kafka mode)")
    p.add_argument("--kafka-idle-timeout", type=float, default=5.0,
                   help="Stop after this many seconds with no new messages (Kafka mode)")
    p.add_argument("--derive-inter-step", action="store_true",
                   help="Derive inter-step gaps from step_done -> next step_open (if inter_step_wait not present)")
    p.add_argument("--outlier-ms", type=int, default=15000, help="Gap threshold for outliers (ms)")
    p.add_argument("--txn-csv", type=str, default=None, help="Write per-transaction durations to CSV")
    p.add_argument("--gap-csv", type=str, default=None, help="Write inter-step gaps to CSV")
    return p.parse_args()


def main():
    args = parse_args()

    aggr = Aggregator(outlier_ms=args.outlier_ms, derive_inter_step=args.derive_inter_step)

    if args.kafka_bootstrap:
        events = read_kafka(
            bootstrap=args.kafka_bootstrap,
            topics=args.kafka_topics,
            group_id=args.kafka_group,
            max_events=args.kafka_max_events,
            idle_timeout_s=args.kafka_idle_timeout,
        )
    else:
        events = read_jsonl(args.file)

    for ev in events:
        aggr.on_event(ev)

    # Results
    print(aggr.summarize())

    # Optional CSV
    aggr.dump_csv(args.txn_csv, args.gap_csv)


if __name__ == "__main__":
    main()


⸻

How to use

A) Aggregate from a JSON-Lines file (produced by the simulator)

# 1) Run the simulator and collect events
python simulate_workflows.py --samples 100 > events.jsonl

# 2) Aggregate
python aggregate_workflows.py --file events.jsonl

B) Aggregate directly from Kafka

pip install confluent-kafka

# Produce events (simulator)
python simulate_workflows.py \
  --kafka-bootstrap localhost:9092 \
  --topic-steps workflow.steps \
  --topic-txn workflow.transactions

# Consume & aggregate (aggregator)
python aggregate_workflows.py \
  --kafka-bootstrap localhost:9092 \
  --kafka-topics workflow.transactions workflow.steps \
  --kafka-group wf-agg-1 \
  --kafka-idle-timeout 5

Optional outputs
	•	CSV of per-transaction durations:

python aggregate_workflows.py --file events.jsonl --txn-csv txn_durations.csv


	•	CSV of inter-step gaps:

python aggregate_workflows.py --file events.jsonl --gap-csv gaps.csv



Notes
	•	By default, inter-step gap stats use the simulator’s inter_step_wait event and its planned_wait_ms. If your producer doesn’t emit that, pass --derive-inter-step to compute gaps from step_done → next step_open.
	•	Outliers are counted where gap ≥ --outlier-ms (default 15000 ms). You’ll also see how many injected outliers the simulator flagged.

If you want, I can add a tiny Prometheus exporter or a Matplotlib report that visualizes the latency histograms.
