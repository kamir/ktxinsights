#!/bin/bash
#
# run_analysis_test.sh: A script to run a full analysis test cycle.
#
# This script automates the process of:
# 1. Starting the monitoring services.
# 2. Replaying a scenario to Kafka.
# 3. Comparing the live metrics with the ground truth.

set -e

# --- 1. Validate Inputs ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <path_to_config.properties> <scenario_script>"
    exit 1
fi

CONFIG_FILE=$1
SCENARIO_SCRIPT=$2
SCENARIO_NAME=$(basename "$SCENARIO_SCRIPT" .sh)
GROUND_TRUTH_FILE="scenarios/$SCENARIO_NAME/report/report_stats.json"

# --- 2. Setup ---
echo "--- Test Setup ---"
echo "Kafka Properties: $CONFIG_FILE"
echo "Scenario to analyze: $SCENARIO_NAME"
echo "--------------------"

# Activate virtual environment
source venv/bin/activate

# --- 3. Start Monitoring Services in the Background ---
echo -e "\n[Step 1/4] Starting monitoring services..."
pkill -f ktx-aggregate || true
pkill -f ktx-collect || true
sleep 2

ktx-aggregate --config-file "$CONFIG_FILE" &
AGGREGATOR_PID=$!
echo "Transaction Aggregator started with PID $AGGREGATOR_PID"

ktx-collect --config-file "$CONFIG_FILE" &
COLLECTOR_PID=$!
echo "Coordinator Collector started with PID $COLLECTOR_PID"

# Give the services a moment to start up
sleep 5

# --- 4. Replay the Scenario ---
echo -e "\n[Step 2/4] Replaying scenario to Kafka..."
ktx-replay --file "scenarios/$SCENARIO_NAME/events.jsonl" --config-file "$CONFIG_FILE"

# Wait for the aggregator to process the final messages
echo "Waiting for final event processing... (50s)"
sleep 50

# --- 5. Run the Comparison ---
echo -e "\n[Step 3/4] Comparing live metrics with ground truth..."
ktx-compare --ground-truth-file "$GROUND_TRUTH_FILE"

# --- 6. Cleanup ---
echo -e "\n[Step 4/4] Cleaning up background processes..."
kill $AGGREGATOR_PID
kill $COLLECTOR_PID
echo "Cleanup complete."

echo -e "\n--- Analysis Test Complete ---"
