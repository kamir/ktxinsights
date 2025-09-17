#!/bin/bash
#
# run_ccloud_test.sh: A script to run a full end-to-end test of the
# `txinsights` toolkit against a Confluent Cloud cluster.
#
# Usage:
#   ./run_ccloud_test.sh <path_to_ccloud.properties> <scenario_script>
#
# Example:
#   ./run_ccloud_test.sh ccloud.properties ../scenarios/03_unreliable_spiky.sh

set -e

# --- 1. Validate Inputs ---
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <path_to_ccloud.properties> <scenario_script>"
    exit 1
fi

CCLOUD_PROPS_ORIG=$1
CCLOUD_PROPS="ccloud-testing/ccloud_converted.properties"
SCENARIO_SCRIPT=$2
SCENARIO_NAME=$(basename "$SCENARIO_SCRIPT" .sh)

if [ ! -f "$CCLOUD_PROPS" ]; then
    echo "Error: Confluent Cloud properties file not found at '$CCLOUD_PROPS'"
    exit 1
fi

if [ ! -f "$SCENARIO_SCRIPT" ]; then
    echo "Error: Scenario script not found at '$SCENARIO_SCRIPT'"
    exit 1
fi

# --- 2. Extract Kafka Bootstrap Server ---
BOOTSTRAP_SERVER=$(grep -E "^bootstrap.servers=" "$CCLOUD_PROPS" | cut -d'=' -f2)
if [ -z "$BOOTSTRAP_SERVER" ]; then
    echo "Error: 'bootstrap.servers' not found in '$CCLOUD_PROPS'"
    exit 1
fi

echo "--- Test Setup ---"
echo "Confluent Cloud Properties: $CCLOUD_PROPS_ORIG"
echo "Bootstrap Server: $BOOTSTRAP_SERVER"
echo "Scenario to run: $SCENARIO_NAME"
echo "--------------------"

# --- 3. Convert Properties File ---
echo "Converting Confluent Cloud properties file for compatibility..."
python3 ccloud-testing/convert_properties.py "$CCLOUD_PROPS_ORIG" "$CCLOUD_PROPS"

# --- 4. Kill any lingering processes ---
echo "Cleaning up any lingering processes..."
pkill -f tx-aggregate || true
pkill -f tx-collect || true

# --- 5. Activate Virtual Environment ---
# Assumes the venv is in the project root
source venv/bin/activate

# --- 5a. Build and Install the Package ---
echo "\nBuilding and installing the txinsights package..."
(cd implementation-python-1 && ./build.sh && pip install dist/*.whl --force-reinstall)

# --- 5a. Create a properties file specifically for the Java tools ---
echo "\nCreating properties file for Java tools..."
CCLOUD_PROPS_FOR_TOOLS="ccloud-testing/ccloud_tools.properties"

USERNAME=$(grep -E "^sasl.username=" "$CCLOUD_PROPS" | cut -d'=' -f2)
PASSWORD=$(grep -E "^sasl.password=" "$CCLOUD_PROPS" | cut -d'=' -f2)

cat > "$CCLOUD_PROPS_FOR_TOOLS" << EOF
bootstrap.servers=$BOOTSTRAP_SERVER
security.protocol=SASL_SSL
sasl.mechanism=PLAIN
sasl.jaas.config=org.apache.kafka.common.security.plain.PlainLoginModule required username="$USERNAME" password="$PASSWORD";
EOF

# --- 5b. Create Kafka Topics ---
echo "\nCreating Kafka topics if they don't exist..."
kafka-topics --bootstrap-server $BOOTSTRAP_SERVER --command-config $CCLOUD_PROPS_FOR_TOOLS --create --if-not-exists --topic workflow.transactions --partitions 1
kafka-topics --bootstrap-server $BOOTSTRAP_SERVER --command-config $CCLOUD_PROPS_FOR_TOOLS --create --if-not-exists --topic workflow.steps --partitions 1
kafka-topics --bootstrap-server $BOOTSTRAP_SERVER --command-config $CCLOUD_PROPS_FOR_TOOLS --create --if-not-exists --topic txinsights.coordinator.state --partitions 1
rm $CCLOUD_PROPS_FOR_TOOLS

# --- 4. Generate Scenario Data (if not already present) ---
echo "\n[Step 1/3] Generating scenario data..."
# The scenario script will create a directory like `scenarios/01_high_throughput`
$SCENARIO_SCRIPT
EVENTS_FILE="scenarios/$SCENARIO_NAME/events.jsonl"
echo "Scenario data generated at '$EVENTS_FILE'"

# --- 5. Start Monitoring Services in the Background ---
echo "\n[Step 2/3] Starting monitoring services..."

# Start the aggregator
venv/bin/tx-aggregate --kafka-bootstrap "$BOOTSTRAP_SERVER" --config-file "$CCLOUD_PROPS" &
AGGREGATOR_PID=$!
echo "Transaction Aggregator started with PID $AGGREGATOR_PID"

# Start the collector (Note: requires admin credentials to be configured)
# For now, we assume it might fail gracefully if not configured.
venv/bin/tx-collect --kafka-bootstrap "$BOOTSTRAP_SERVER" --config-file "$CCLOUD_PROPS" &
COLLECTOR_PID=$!
echo "Coordinator Collector started with PID $COLLECTOR_PID"

# Give the services a moment to start up
sleep 5

# --- 6. Replay the Scenario to Confluent Cloud ---
echo "\n[Step 3/3] Replaying scenario to Confluent Cloud..."
venv/bin/tx-replay --file "$EVENTS_FILE" --kafka-bootstrap "$BOOTSTRAP_SERVER" --config-file "$CCLOUD_PROPS"

echo "\n--- Test Complete ---"
echo "Replay finished. The monitoring services are still running."
echo "You can view live metrics at http://localhost:8000/metrics"
echo "Press Ctrl+C to stop the monitoring services."

# --- 7. Cleanup ---
# This function will be called when the script exits (e.g., via Ctrl+C)
cleanup() {
    echo "\nCleaning up background processes..."
    kill $AGGREGATOR_PID
    kill $COLLECTOR_PID
    echo "Cleanup complete."
}
trap cleanup EXIT

# Keep the script alive to allow for metric observation
wait
