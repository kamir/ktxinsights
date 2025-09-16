#!/bin/bash
#
# Scenario 01: High-Throughput, Low-Latency System
# - High concurrency to stress the system
# - Short work and wait times for fast processing
# - Very rare outliers

set -e
SCENARIO_DIR="scenarios/01_high_throughput"
EVENTS_FILE="$SCENARIO_DIR/events.jsonl"
REPORT_DIR="$SCENARIO_DIR/report"

# Create directory for this scenario's output
mkdir -p "$SCENARIO_DIR"

echo "--- Running Scenario 01: High-Throughput ---"

# Step 1: Generate the event data
echo "Generating event data..."
./venv/bin/python3 solution-proposal-1/event-flow-simulation.py \
    --samples 500 \
    --concurrency 50 \
    --pre-min 50 \
    --pre-max 200 \
    --inter-min 50 \
    --inter-max 100 \
    --outlier-prob 0.001 \
    > "$EVENTS_FILE"

# Step 2: Generate the ground truth report
echo "Generating ground truth report..."
./venv/bin/python3 solution-proposal-1/generate_report.py \
    --file "$EVENTS_FILE" \
    --out-dir "$REPORT_DIR"

echo "Scenario 01 complete. Report generated in $REPORT_DIR"
