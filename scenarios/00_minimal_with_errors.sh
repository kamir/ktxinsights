#!/bin/bash
#
# Scenario 00: Minimal Viable Scenario with Errors
# - 10 samples with 2 failures (20% failure rate)
# - Fixed wait times for predictable results
# - No outliers

set -e

# Determine the project root directory based on the script's location
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_ROOT=$( cd -- "$(dirname "$SCRIPT_DIR")" &> /dev/null && pwd )

SCENARIO_DIR="$PROJECT_ROOT/scenarios/00_minimal_with_errors"
EVENTS_FILE="$SCENARIO_DIR/events.jsonl"
REPORT_DIR="$SCENARIO_DIR/report"

# Create directory for this scenario's output
mkdir -p "$SCENARIO_DIR"

echo "--- Running Scenario 00: Minimal With Errors ---"

# Step 1: Generate the event data
echo "Generating event data..."
"$PROJECT_ROOT/venv/bin/python3" "$PROJECT_ROOT/solution-proposal-1/event-flow-simulation.py" \
    --samples 10 \
    --concurrency 1 \
    --pre-min 100 \
    --pre-max 100 \
    --inter-min 50 \
    --inter-max 50 \
    --outlier-prob 0 \
    --failure-prob 0.2 \
    > "$EVENTS_FILE"

# Step 2: Generate the ground truth report
echo "Generating ground truth report..."
"$PROJECT_ROOT/venv/bin/python3" "$PROJECT_ROOT/solution-proposal-1/generate_report.py" \
    --file "$EVENTS_FILE" \
    --out-dir "$REPORT_DIR"

echo "Scenario 00 with errors complete. Report generated in $REPORT_DIR"
