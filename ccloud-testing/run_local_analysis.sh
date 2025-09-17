#!/bin/bash
#
# run_local_analysis.sh: A script to run a full analysis test cycle locally
# without connecting to Kafka.

set -e

# --- 1. Setup ---
if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_events.jsonl>"
    exit 1
fi

EVENTS_FILE=$1
SCENARIO_DIR=$(dirname "$EVENTS_FILE")
GROUND_TRUTH_FILE="$SCENARIO_DIR/report/report_stats.json"

echo "--- Local Analysis Setup ---"
echo "Event file to analyze: $EVENTS_FILE"
echo "----------------------------"

# Activate virtual environment
source venv/bin/activate

# --- 2. Generate Ground Truth ---
echo -e "\n[Step 1/4] Generating ground truth report..."
ktx-report --file "$EVENTS_FILE" --out-dir "$SCENARIO_DIR/report"

# --- 3. Start Monitoring Services in the Background ---
echo -e "\n[Step 2/4] Starting monitoring services in file-reading mode..."
pkill -f ktx-aggregate || true
sleep 2

ktx-aggregate --file "$EVENTS_FILE" &
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

echo -e "\n--- Local Analysis Complete ---"
