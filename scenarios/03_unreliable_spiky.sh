#!/bin/bash
#
# Scenario 03: Unreliable or "Spiky" System
# - Simulates a system that performs well on average but suffers
#   from frequent, severe hiccups.

set -e
SCENARIO_DIR="scenarios/03_unreliable_spiky"
EVENTS_FILE="$SCENARIO_DIR/events.jsonl"
REPORT_DIR="$SCENARIO_DIR/report"

# Create directory for this scenario's output
mkdir -p "$SCENARIO_DIR"

echo "--- Running Scenario 03: Unreliable, Spiky ---"

# Step 1: Generate the event data
echo "Generating event data..."
./venv/bin/python3 solution-proposal-1/event-flow-simulation.py \
    --samples 625 \
    --concurrency 20 \
    --outlier-prob 0.05 \
    --outlier-ms 20000 \
    > "$EVENTS_FILE"

# Step 2: Generate the ground truth report
echo "Generating ground truth report..."
./venv/bin/python3 solution-proposal-1/generate_report.py \
    --file "$EVENTS_FILE" \
    --out-dir "$REPORT_DIR"

echo "Scenario 03 complete. Report generated in $REPORT_DIR"
