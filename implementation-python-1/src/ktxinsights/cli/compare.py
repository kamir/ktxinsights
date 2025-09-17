import argparse
import os
from ktxinsights.compare import fetch_live_metrics, load_ground_truth, compare_metrics

def main():
    parser = argparse.ArgumentParser(description="Compare scenario ground truth with live metrics.")
    parser.add_argument("--ground-truth-file", required=True, help="Path to the scenario's report_stats.json file.")
    parser.add_argument("--metrics-url", default="http://localhost:8000/metrics", help="URL of the aggregator's Prometheus metrics endpoint.")
    parser.add_argument("--out-dir", help="Directory to save the HTML comparison report.")
    args = parser.parse_args()

    try:
        print(f"Loading ground truth from {args.ground_truth_file}...")
        ground_truth = load_ground_truth(args.ground_truth_file)
        
        print(f"Fetching live metrics from {args.metrics_url}...")
        live_metrics = fetch_live_metrics(args.metrics_url)
        
        compare_metrics(ground_truth, live_metrics, args.out_dir)

    except (RuntimeError, FileNotFoundError) as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()
