#!/bin/bash
#
# Scenario 02: Slow, Complex Workflow
# - More steps per transaction
# - Lower concurrency
# - Long processing times per step

set -e
SCENARIO_DIR="scenarios/02_slow_complex"
EVENTS_FILE="$SCENARIO_DIR/events.jsonl"
REPORT_DIR="$SCENARIO_DIR/report"

# Create directory for this scenario's output
mkdir -p "$SCENARIO_DIR"

echo "--- Running Scenario 02: Slow, Complex ---"

# Step 1: Generate the event data
echo "Generating event data..."
./venv/bin/python3 solution-proposal-1/event-flow-simulation.py \
    --samples 100 \
    --concurrency 10 \
    --steps 10 \
    --pre-min 1000 \
    --pre-max 4000 \
    --inter-min 500 \
    --inter-max 1500 \
    > "$EVENTS_FILE"

# Step 2: Generate the ground truth report
echo "Generating ground truth report..."
./venv/bin/python3 solution-proposal-1/generate_report.py \
    --file "$EVENTS_FILE" \
    --out-dir "$REPORT_DIR"

echo "Scenario 02 complete. Report generated in $REPORT_DIR"
