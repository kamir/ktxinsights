import argparse
from txinsights.report import generate_report

def main():
    parser = argparse.ArgumentParser(description="Create latency charts from workflow events (JSONL).")
    parser.add_argument("--file", type=str, required=True, help="Path to events.jsonl file")
    parser.add_argument("--out-dir", type=str, default="report", help="Output directory for the report")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Outlier threshold for info text (ms)")
    args = parser.parse_args()

    generate_report(args.file, args.out_dir, args.outlier_ms)

if __name__ == "__main__":
    main()
