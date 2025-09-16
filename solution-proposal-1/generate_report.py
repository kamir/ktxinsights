#!/usr/bin/env python3
"""
Generate a simple Matplotlib report from workflow events (JSONL).

This script reads a JSONL file containing transaction events, calculates
key quality metrics, and generates a visual report with histograms
for transaction durations and inter-step gaps.

Outputs are saved to a specified directory (default: 'report').
"""

import argparse
import json
import sys
from statistics import mean, median
from pathlib import Path
import matplotlib.pyplot as plt

def pct(vals, p):
    """Calculate the p-th percentile of a list of values."""
    if not vals:
        return 0.0
    arr = sorted(vals)
    k = max(1, int(round(p / 100.0 * len(arr))))
    return float(arr[k - 1])

def read_jsonl(path: str | None):
    """Read a JSONL file or stdin and yield each line as a dictionary."""
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
    parser = argparse.ArgumentParser(description="Create latency charts from workflow events (JSONL).")
    parser.add_argument("--file", type=str, required=True, help="Path to events.jsonl file")
    parser.add_argument("--out-dir", type=str, default="report", help="Output directory for the report")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Outlier threshold for info text (ms)")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. Collect metrics from the event file ---
    txn_open_ts = {}
    txn_durations_ms = []
    inter_step_gaps_ms = []
    injected_outliers = 0
    outlier_count = 0

    print(f"Reading events from {args.file}...")
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

    # Convert to seconds for plotting
    txn_s = [x / 1000.0 for x in txn_durations_ms]
    gaps_s = [x / 1000.0 for x in inter_step_gaps_ms]

    # --- 2. Generate Plots ---
    # Plot 1: Transaction durations
    if txn_s:
        plt.figure(figsize=(10, 6))
        plt.hist(txn_s, bins=40, color='skyblue', edgecolor='black')
        plt.xlabel("Transaction duration (s)")
        plt.ylabel("Count")
        plt.title("Distribution of Transaction Durations")
        plt.grid(axis='y', alpha=0.75)
        plt.tight_layout()
        save_path = out_dir / "txn_durations.png"
        plt.savefig(save_path, dpi=120)
        plt.close()
        print(f"Saved transaction duration plot to {save_path}")

    # Plot 2: Inter-step gaps
    if gaps_s:
        plt.figure(figsize=(10, 6))
        plt.hist(gaps_s, bins=40, color='lightgreen', edgecolor='black')
        plt.xlabel("Inter-step gap (s)")
        plt.ylabel("Count")
        plt.title("Distribution of Inter-Step Gaps")
        plt.grid(axis='y', alpha=0.75)
        plt.tight_layout()
        save_path = out_dir / "inter_step_gaps.png"
        plt.savefig(save_path, dpi=120)
        plt.close()
        print(f"Saved inter-step gap plot to {save_path}")

    # --- 3. Generate HTML Report ---
    def stat_block(vals_s):
        if not vals_s:
            return "n/a"
        return (
            f"<b>Count:</b> {len(vals_s)} | "
            f"<b>Avg:</b> {mean(vals_s):.3f}s | "
            f"<b>Median:</b> {median(vals_s):.3f}s | "
            f"<b>P90:</b> {pct(vals_s, 90):.3f}s | "
            f"<b>P95:</b> {pct(vals_s, 95):.3f}s | "
            f"<b>P99:</b> {pct(vals_s, 99):.3f}s"
        )

    txn_stats = stat_block(txn_s)
    gap_stats = stat_block(gaps_s)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Transaction Stream Quality Report</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; margin: 40px; background-color: #f9f9f9; color: #333; }}
        .container {{ max-width: 900px; margin: auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a1a1a; }}
        .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 20px; margin-bottom: 20px; }}
        img {{ max-width: 100%; height: auto; border-radius: 6px; margin-top: 10px; }}
        .stat {{ font-size: 0.9em; color: #555; }}
        footer {{ margin-top: 30px; text-align: center; font-size: 0.8em; color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Transaction Stream Quality Report</h1>

        <div class="card">
            <h2>Transaction Durations</h2>
            <p class="stat">{txn_stats}</p>
            {"<img src='txn_durations.png' alt='Transaction durations histogram' />" if txn_s else "<p>No transaction data found.</p>"}
        </div>

        <div class="card">
            <h2>Inter-step Gaps</h2>
            <p class="stat">{gap_stats}</p>
            <p class="stat"><b>Outliers (≥ {args.outlier_ms/1000:.1f}s):</b> {outlier_count} | <b>Simulator-Injected Outliers:</b> {injected_outliers}</p>
            {"<img src='inter_step_gaps.png' alt='Inter-step gaps histogram' />" if gaps_s else "<p>No gap data found.</p>"}
        </div>

        <footer>Generated by generate_report.py</footer>
    </div>
</body>
</html>"""

    report_path = out_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    print(f"Wrote HTML report to {report_path}")

    # --- 4. Save Stats to JSON ---
    stats_data = {
        "transaction_durations": {
            "unit": "seconds",
            "count": len(txn_s),
            "avg": mean(txn_s) if txn_s else 0,
            "median": median(txn_s) if txn_s else 0,
            "p90": pct(txn_s, 90),
            "p95": pct(txn_s, 95),
            "p99": pct(txn_s, 99),
        },
        "inter_step_gaps": {
            "unit": "seconds",
            "count": len(gaps_s),
            "avg": mean(gaps_s) if gaps_s else 0,
            "median": median(gaps_s) if gaps_s else 0,
            "p90": pct(gaps_s, 90),
            "p95": pct(gaps_s, 95),
            "p99": pct(gaps_s, 99),
        },
        "outliers": {
            "threshold_ms": args.outlier_ms,
            "detected_count": outlier_count,
            "injected_count": injected_outliers,
        }
    }
    stats_path = out_dir / "report_stats.json"
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=4)
    print(f"Wrote stats JSON to {stats_path}")


if __name__ == "__main__":
    main()
