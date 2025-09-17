#!/bin/bash
#
# run_minimal_local_analysis_with_errors.sh: A script to run the minimal analysis test cycle with errors locally.

set -e

# --- 1. Setup ---
SCENARIO_SCRIPT="scenarios/00_minimal_with_errors.sh"
SCENARIO_NAME=$(basename "$SCENARIO_SCRIPT" .sh)
EVENTS_FILE="scenarios/$SCENARIO_NAME/events.jsonl"
GROUND_TRUTH_FILE="scenarios/$SCENARIO_NAME/report/report_stats.json"

echo "--- Minimal Local Analysis Setup ---"
echo "Scenario to analyze: $SCENARIO_NAME"
echo "----------------------------"

# Activate virtual environment
source venv/bin/activate

# --- 2. Generate Scenario Data ---
echo -e "\n[Step 1/4] Generating scenario data..."
bash "$SCENARIO_SCRIPT"

# --- 3. Start Monitoring Services in the Background ---
echo -e "\n[Step 2/4] Starting monitoring services in file-reading mode..."
pkill -f ktx-aggregate || true
sleep 2

ktx-aggregate --file "$EVENTS_FILE" --abort-timeout-s 5 &
AGGREGATOR_PID=$!
echo "Transaction Aggregator started with PID $AGGREGATOR_PID"

# Give the aggregator a moment to start up and begin processing
echo "Waiting for initial processing... (5s)"
sleep 5

# --- 4. Run Mid-Stream Comparison ---
echo -e "\n[Step 3/5] Comparing live metrics mid-stream (snapshot)..."
ktx-compare --ground-truth-file "$PWD/$GROUND_TRUTH_FILE" --out-dir "$PWD/$SCENARIO_DIR/report"

# Wait for the file processing to complete
echo "Waiting for event processing to finish... (20s)"
sleep 20

# --- 5. Run Final Comparison ---
echo -e "\n[Step 4/5] Comparing final live metrics with ground truth..."
ktx-compare --ground-truth-file "$PWD/$GROUND_TRUTH_FILE" --out-dir "$PWD/$SCENARIO_DIR/report"

# --- 6. Cleanup ---
echo -e "\n[Step 5/5] Cleaning up background processes..."
kill $AGGREGATOR_PID
echo "Cleanup complete."

echo -e "\n--- Minimal Local Analysis Complete ---"
