"""
Compare the ground truth of a generated scenario with the live metrics
captured by the Transaction Aggregator.
"""

import json
import requests
from typing import Dict, Any

def parse_prometheus_metrics(text: str) -> Dict[str, Any]:
    """A simple parser for Prometheus text format."""
    metrics = {
        "transaction_lifetime": {"sum": 0, "count": 0, "buckets": {}},
        "transactions_by_state": {},
        "transactional_integrity_lag": 0,
        "high_watermark_open_txn": 0,
        "low_watermark_unresolved_txn": 0,
    }
    for line in text.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        
        parts = line.split()
        name_labels, value = parts[0], float(parts[1])
        
        if "ktxinsights_transaction_lifetime_seconds_sum" in name_labels:
            metrics["transaction_lifetime"]["sum"] = value
        elif "ktxinsights_transaction_lifetime_seconds_count" in name_labels:
            metrics["transaction_lifetime"]["count"] = value
        elif "ktxinsights_transactions_by_state" in name_labels:
            state = name_labels.split('{state="')[1].split('"')[0]
            metrics["transactions_by_state"][state] = value
        elif "ktxinsights_transactional_integrity_lag_seconds" in name_labels:
            metrics["transactional_integrity_lag"] = value
        elif "ktxinsights_high_watermark_open_transactions_timestamp_seconds" in name_labels:
            metrics["high_watermark_open_txn"] = value
        elif "ktxinsights_low_watermark_unresolved_transactions_timestamp_seconds" in name_labels:
            metrics["low_watermark_unresolved_txn"] = value

    return metrics

def fetch_live_metrics(url: str) -> Dict[str, Any]:
    """Fetch and parse metrics from the aggregator's Prometheus endpoint."""
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return parse_prometheus_metrics(response.text)
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to fetch metrics from {url}: {e}")

def load_ground_truth(file_path: str) -> Dict[str, Any]:
    """Load the ground truth stats from a scenario's JSON report."""
    with open(file_path, 'r') as f:
        return json.load(f)

def compare_metrics(ground_truth: Dict[str, Any], live_metrics: Dict[str, Any], out_dir: str = None):
    """Compare ground truth with live metrics and print a report."""
    
    gt_dur = ground_truth["transaction_durations"]
    live_dur = live_metrics["transaction_lifetime"]
    live_states = live_metrics["transactions_by_state"]
    til = live_metrics["transactional_integrity_lag"]
    high_wm = live_metrics["high_watermark_open_txn"]
    low_wm = live_metrics["low_watermark_unresolved_txn"]

    # --- Comparison ---
    avg_live_dur = (live_dur["sum"] / live_dur["count"]) if live_dur["count"] > 0 else 0
    overhead_ms = (avg_live_dur - gt_dur["avg"]) * 1000 if gt_dur["avg"] > 0 else 0
    
    total_closed_live = live_states.get("closed", 0)
    total_aborted_live = live_states.get("aborted", 0)
    total_verified_aborted_live = live_states.get("verified_aborted", 0)
    total_processed_live = total_closed_live + total_aborted_live + total_verified_aborted_live
    
    ti_ratio = (total_closed_live / total_processed_live) * 100 if total_processed_live > 0 else 100

    print("="*50)
    print(" Scenario Performance Analysis")
    print("="*50)
    
    print("\n--- Transaction Counts ---")
    print(f"  - Expected Successful: {gt_dur['count']}")
    print(f"  - Measured Successful: {int(total_closed_live)}")
    print(f"  - Measured Aborted:    {int(total_aborted_live)}")
    print(f"  - Discrepancy (Aborted/Unexpected): {int(total_processed_live - gt_dur['count'])}")

    print("\n--- Average Transaction Duration ---")
    print(f"  - Benchmark (Ground Truth): {gt_dur['avg']:.3f}s")
    print(f"  - Live Measurement:         {avg_live_dur:.3f}s")
    print(f"  - Kafka Overhead (Delta):   {overhead_ms:+.1f}ms")

    print("\n--- Latency Percentiles (Ground Truth) ---")
    print(f"  - P90: {gt_dur['p90']:.3f}s")
    print(f"  - P95: {gt_dur['p95']:.3f}s")
    print(f"  - P99: {gt_dur['p99']:.3f}s")
    print("\n(Note: Live percentile data requires a more advanced Prometheus query)")

    print("\n--- Transactional Integrity ---")
    print(f"  - Transactional Integrity Ratio: {ti_ratio:.2f}%")
    if high_wm > 0 and low_wm > 0:
        from datetime import datetime
        high_wm_dt = datetime.fromtimestamp(high_wm).strftime('%Y-%m-%d %H:%M:%S')
        low_wm_dt = datetime.fromtimestamp(low_wm).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  - High Watermark (Newest Open):    {high_wm_dt}")
        print(f"  - Low Watermark (Oldest Unresolved): {low_wm_dt}")
    print(f"  - Transactional Integrity Lag (TIL): {til:.2f}s")
    print("    (Time window of uncertainty between oldest and newest open transactions)")
    
    print("="*50)

    if out_dir:
        import os
        os.makedirs(out_dir, exist_ok=True)
        report_path = os.path.join(out_dir, "comparison_report.html")
        
        html = f"""
        <html>
            <head>
                <title>Scenario Performance Analysis</title>
                <style>
                    body {{ font-family: sans-serif; }}
                    table {{ border-collapse: collapse; width: 60%; }}
                    th, td {{ border: 1px solid #dddddd; text-align: left; padding: 8px; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <h1>Scenario Performance Analysis</h1>
                <h2>Transaction Counts</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Expected Successful</td><td>{gt_dur['count']}</td></tr>
                    <tr><td>Measured Successful</td><td>{int(total_closed_live)}</td></tr>
                    <tr><td>Measured Aborted</td><td>{int(total_aborted_live)}</td></tr>
                    <tr><td>Discrepancy</td><td>{int(total_processed_live - gt_dur['count'])}</td></tr>
                </table>

                <h2>Average Transaction Duration</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Benchmark (Ground Truth)</td><td>{gt_dur['avg']:.3f}s</td></tr>
                    <tr><td>Live Measurement</td><td>{avg_live_dur:.3f}s</td></tr>
                    <tr><td>Kafka Overhead (Delta)</td><td>{overhead_ms:+.1f}ms</td></tr>
                </table>

                <h2>Transactional Integrity</h2>
                <table>
                    <tr><th>Metric</th><th>Value</th></tr>
                    <tr><td>Transactional Integrity Ratio</td><td>{ti_ratio:.2f}%</td></tr>
                    <tr><td>High Watermark (Newest Open)</td><td>{high_wm_dt if high_wm > 0 else 'N/A'}</td></tr>
                    <tr><td>Low Watermark (Oldest Unresolved)</td><td>{low_wm_dt if low_wm > 0 else 'N/A'}</td></tr>
                    <tr><td>Transactional Integrity Lag (TIL)</td><td>{til:.2f}s</td></tr>
                </table>
            </body>
        </html>
        """
        with open(report_path, 'w') as f:
            f.write(html)
        print(f"\\nWrote HTML report to {report_path}")
