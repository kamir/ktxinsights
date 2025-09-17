Excellent—here are two add-ons that plug right into the simulator/aggregator flow:
	•	A Prometheus exporter that consumes events (JSONL or Kafka) and exposes live metrics.
	•	A Matplotlib report generator that reads a file of events and produces simple latency charts.

Both reuse the same event types you already have: transaction_open, step_open, step_done, inter_step_wait, transaction_close.

⸻

1) Prometheus Exporter (prometheus_exporter.py)
	•	Continuously consumes from Kafka or stdin/JSONL.
	•	Exposes metrics at http://0.0.0.0:8000/metrics (configurable).
	•	Uses Prometheus Histogram/Summary + Counters for:
	•	Transaction durations (seconds)
	•	Inter-step gaps (seconds)
	•	Event type counts
	•	Outliers (gaps ≥ threshold)

#!/usr/bin/env python3
"""
Prometheus exporter for workflow events.

Reads JSONL (stdin or --file) or Kafka topics (--kafka-bootstrap) continuously,
updates Prometheus metrics, and exposes them via an HTTP endpoint.

Example:
  # From Kafka
  python prometheus_exporter.py --kafka-bootstrap localhost:9092 \
    --kafka-topics workflow.transactions workflow.steps

  # From JSONL (tail -f style)
  tail -f events.jsonl | python prometheus_exporter.py
"""

import argparse
import json
import sys
import time
from typing import List, Optional

from prometheus_client import start_http_server, Counter, Histogram, Summary, Gauge

try:
    from confluent_kafka import Consumer
except Exception:
    Consumer = None  # optional

# ---------- Prometheus Metrics ----------
EVENT_COUNT = Counter(
    "wf_events_total",
    "Total events ingested by type",
    labelnames=("type",),
)

TXN_DURATION = Histogram(
    "wf_transaction_duration_seconds",
    "Transaction duration from open to close (seconds)",
    buckets=(
        0.5, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144  # Fibonacci-ish buckets, adjust as needed
    ),
)

INTER_STEP_GAP = Histogram(
    "wf_inter_step_gap_seconds",
    "Inter-step wait (seconds)",
    buckets=(0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 20, 30, 60),
)

OUTLIERS = Counter(
    "wf_inter_step_outliers_total",
    "Count of inter-step gaps above threshold",
)

INJECTED_OUTLIERS = Counter(
    "wf_injected_outliers_total",
    "Count of gaps marked as outlier_injected by producer",
)

OPEN_TXN_GAUGE = Gauge(
    "wf_open_transactions",
    "Number of transactions currently open (best effort)",
)

# ---------- State for durations ----------
txn_open_ts = {}  # txn_id -> ts_ms
outlier_threshold_ms_default = 15000


def now_ms() -> int:
    return int(time.time() * 1000)


def read_jsonl_stream(fp):
    for line in fp:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue


def read_kafka_stream(bootstrap: str, topics: List[str], group_id: str):
    if Consumer is None:
        raise RuntimeError("confluent-kafka not installed. `pip install confluent-kafka`")
    consumer = Consumer({
        "bootstrap.servers": bootstrap,
        "group.id": group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": True,
        "session.timeout.ms": 20000,
    })
    consumer.subscribe(topics)
    try:
        while True:
            msg = consumer.poll(0.5)
            if msg is None:
                continue
            if msg.error():
                continue
            try:
                ev = json.loads(msg.value().decode("utf-8"))
                yield ev
            except Exception:
                continue
    finally:
        consumer.close()


def process_event(ev: dict, outlier_threshold_ms: int):
    et = ev.get("type", "unknown")
    EVENT_COUNT.labels(et).inc()

    if et == "transaction_open":
        txn_id = ev.get("txn_id")
        ts = int(ev.get("ts_ms", now_ms()))
        if txn_id:
            txn_open_ts[txn_id] = ts
            OPEN_TXN_GAUGE.inc()

    elif et == "transaction_close":
        txn_id = ev.get("txn_id")
        ts = int(ev.get("ts_ms", now_ms()))
        if txn_id and txn_id in txn_open_ts:
            dur_ms = ts - txn_open_ts.pop(txn_id)
            TXN_DURATION.observe(dur_ms / 1000.0)
            OPEN_TXN_GAUGE.dec()

    elif et == "inter_step_wait":
        planned = ev.get("planned_wait_ms")
        if planned is not None:
            seconds = float(planned) / 1000.0
            INTER_STEP_GAP.observe(seconds)
            if ev.get("outlier_injected"):
                INJECTED_OUTLIERS.inc()
            if planned >= outlier_threshold_ms:
                OUTLIERS.inc()


def main():
    ap = argparse.ArgumentParser(description="Prometheus exporter for workflow events.")
    src = ap.add_mutually_exclusive_group(required=False)
    src.add_argument("--file", type=str, help="Read from JSONL file (stream). If omitted, read stdin.")
    src.add_argument("--kafka-bootstrap", type=str, help="Kafka bootstrap servers")
    ap.add_argument("--kafka-topics", type=str, nargs="+",
                    default=["workflow.transactions", "workflow.steps"])
    ap.add_argument("--kafka-group", type=str, default="wf-prom-exporter")
    ap.add_argument("--listen-port", type=int, default=8000, help="Port for /metrics")
    ap.add_argument("--outlier-ms", type=int, default=outlier_threshold_ms_default)
    args = ap.parse_args()

    # Start Prometheus HTTP server
    start_http_server(args.listen_port)

    # Input stream
    if args.kafka_bootstrap:
        stream = read_kafka_stream(args.kafka_bootstrap, args.kafka_topics, args.kafka_group)
    elif args.file:
        fp = open(args.file, "r", encoding="utf-8")
        stream = read_jsonl_stream(fp)
    else:
        stream = read_jsonl_stream(sys.stdin)

    # Ingest loop
    for ev in stream:
        process_event(ev, args.outlier_ms)


if __name__ == "__main__":
    main()

How to run
	•	From Kafka:

python prometheus_exporter.py --kafka-bootstrap localhost:9092 \
  --kafka-topics workflow.transactions workflow.steps --listen-port 8000

	•	From a JSONL stream:

tail -f events.jsonl | python prometheus_exporter.py --listen-port 8000

Prometheus scrape config (snippet)

scrape_configs:
  - job_name: 'workflow-events'
    static_configs:
      - targets: ['localhost:8000']


⸻

2) Matplotlib Report (report_plot.py)
	•	Reads events.jsonl (or stdin) produced by the simulator.
	•	Computes distributions and generates:
	•	Histogram: transaction durations (seconds)
	•	Histogram: inter-step gaps (seconds)
	•	Saves static PNGs and a minimal HTML summary page that embeds them.
	•	One chart per figure; no custom colors or styles.

#!/usr/bin/env python3
"""
Generate a simple Matplotlib report from workflow events (JSONL).

Outputs:
  - txn_durations.png
  - inter_step_gaps.png
  - report.html  (embeds the PNGs and basic stats)
"""

import argparse
import json
import sys
from statistics import mean, median
from pathlib import Path
import matplotlib.pyplot as plt

def pct(vals, p):
    if not vals:
        return 0.0
    arr = sorted(vals)
    k = max(1, int(round(p / 100.0 * len(arr))))
    return float(arr[k - 1])

def read_jsonl(path: str | None):
    stream = sys.stdin if not path else open(path, "r", encoding="utf-8")
    try:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except Exception:
                continue
    finally:
        if path:
            stream.close()

def main():
    ap = argparse.ArgumentParser(description="Create latency charts from workflow events (JSONL).")
    ap.add_argument("--file", type=str, default=None, help="Path to events.jsonl (or read stdin)")
    ap.add_argument("--out-dir", type=str, default="report_out", help="Output directory")
    ap.add_argument("--outlier-ms", type=int, default=15000, help="Outlier threshold for info")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Collect metrics
    txn_open_ts = {}
    txn_durations_ms = []
    inter_step_gaps_ms = []
    injected_outliers = 0
    outlier_count = 0

    for ev in read_jsonl(args.file):
        et = ev.get("type")
        if et == "transaction_open":
            txn_open_ts[ev["txn_id"]] = int(ev["ts_ms"])
        elif et == "transaction_close":
            tid = ev["txn_id"]
            ts = int(ev["ts_ms"])
            if tid in txn_open_ts:
                txn_durations_ms.append(ts - txn_open_ts.pop(tid))
        elif et == "inter_step_wait":
            planned = ev.get("planned_wait_ms")
            if planned is not None:
                inter_step_gaps_ms.append(float(planned))
                if planned >= args.outlier_ms:
                    outlier_count += 1
                if ev.get("outlier_injected"):
                    injected_outliers += 1

    # Convert to seconds
    txn_s = [x / 1000.0 for x in txn_durations_ms]
    gaps_s = [x / 1000.0 for x in inter_step_gaps_ms]

    # --- Plot 1: Transaction durations ---
    if txn_s:
        plt.figure()
        plt.hist(txn_s, bins=30)
        plt.xlabel("Transaction duration (s)")
        plt.ylabel("Count")
        plt.title("Transaction Durations")
        plt.tight_layout()
        plt.savefig(out / "txn_durations.png", dpi=120)
        plt.close()

    # --- Plot 2: Inter-step gaps ---
    if gaps_s:
        plt.figure()
        plt.hist(gaps_s, bins=30)
        plt.xlabel("Inter-step gap (s)")
        plt.ylabel("Count")
        plt.title("Inter-step Gaps")
        plt.tight_layout()
        plt.savefig(out / "inter_step_gaps.png", dpi=120)
        plt.close()

    # Basic stats
    def stat_block(vals):
        if not vals:
            return "n/a"
        return (
            f"n={len(vals)}; "
            f"avg={mean(vals):.3f}s; "
            f"med={median(vals):.3f}s; "
            f"p90={pct(vals,90):.3f}s; "
            f"p95={pct(vals,95):.3f}s; "
            f"p99={pct(vals,99):.3f}s"
        )

    txn_stats = stat_block(txn_s)
    gap_stats = stat_block(gaps_s)

    # HTML report
    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Workflow Latency Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; padding: 20px; line-height: 1.4; }}
h1 {{ margin-top: 0; }}
.card {{ border: 1px solid #ddd; border-radius: 10px; padding: 12px; margin: 12px 0; }}
img {{ max-width: 100%; height: auto; border: 1px solid #eee; border-radius: 6px; }}
.stat {{ color: #444; }}
</style>
</head>
<body>
<h1>Workflow Latency Report</h1>

<div class="card">
  <h2>Transaction Durations</h2>
  <p class="stat">{txn_stats}</p>
  {"<img src='txn_durations.png' alt='Transaction durations histogram' />" if txn_s else "<p>No transaction data found.</p>"}
</div>

<div class="card">
  <h2>Inter-step Gaps</h2>
  <p class="stat">{gap_stats}</p>
  <p>Outliers (≥ {args.outlier_ms/1000:.3f}s): {outlier_count}; Injected outliers: {injected_outliers}</p>
  {"<img src='inter_step_gaps.png' alt='Inter-step gaps histogram' />" if gaps_s else "<p>No gap data found.</p>"}
</div>

<footer style="margin-top:20px; color:#666; font-size:12px;">
  Generated by report_plot.py
</footer>
</body></html>"""

    (out / "report.html").write_text(html, encoding="utf-8")
    print(f"Wrote {out/'report.html'}")
    if txn_s:
        print(f"Wrote {out/'txn_durations.png'}")
    if gaps_s:
        print(f"Wrote {out/'inter_step_gaps.png'}")

if __name__ == "__main__":
    main()

How to run
	•	Generate charts from a file:

python report_plot.py --file events.jsonl --out-dir report_out
# Open report_out/report.html in a browser

	•	Or from stdin (e.g., pipe the simulator):

python simulate_workflows.py --samples 100 | python report_plot.py --out-dir report_out


⸻

Notes and integration tips
	•	The Prometheus exporter is ideal for long-running sims (Kafka mode), letting you scrape live metrics and build Grafana dashboards immediately (transaction duration histogram, inter-step gap histogram, outlier counters, open transactions gauge).
	•	The Matplotlib report is perfect for offline analysis (e.g., per test run); it creates minimal, dependency-light artifacts you can attach to tickets or share as static files.
	•	Thresholds (like the 15 s outlier) are configurable via CLI in both tools.
	•	Both tools are read-only and do not modify or acknowledge Kafka offsets in special ways (exporter uses enable.auto.commit=True; adjust if you want a different consumption behavior).

If you’d like, I can also add:
	•	A tiny percentile Prometheus Summary (in addition to Histogram) or custom buckets tuned to your observed ranges.
	•	A CSV export to accompany the Matplotlib charts (transaction durations and inter-step gaps), or a simple PDF export via headless browser.
