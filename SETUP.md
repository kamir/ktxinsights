# Setup ktx-collect and ktx-aggregate for CCloud / CP

This guide will help you set up the `ktx-collect` and `ktx-aggregate` tools to work with Confluent Cloud (CCloud) or Confluent Platform (CP). These tools are part of the `ktxinsights` package, which provides insights into Kafka transactions.

## Prerequisites
- Python 3 or higher
- Docker or compatible
- Confluent Cloud account or Confluent Platform installation (example: CP All-in-One)

## Step 1: Install the `ktxinsights` Package

Clone the repository:

```bash
git clone https://github.com/kamir/ktxinsights.git
```

## Step 2: Integrate with Confluent Cloud or Confluent Platform (cp-all-in-one in this example)

Clone the cp-all-in-one repository if you haven't already:

```bash
git clone https://github.com/confluentinc/cp-all-in-one.git
cd cp-all-in-one/cp-all-in-one
```

Copy the `implementation-python-1` and `scenarios` source code into the `cp-all-in-one` directory.

Create a `docker-compose.override.yml` file to include the `ktxinsights` services:

```yaml
services:
  # [OPTIONAL] Python environment for development and testing
  py-dev:
    image: python:3
    volumes:
      - .:/app:cached
    # Overrides default command so things don't shut down after the process ends.
    command: sleep infinity
    tty: true

  ktx-aggregator:
    build:
      context: ./implementation-python-1/src
      dockerfile: Dockerfile
    environment:
      - KTX_MODE=aggregator
      # Prometheus metrics listen port
      - KTX_LISTEN_PORT=8080
      # Timeout in seconds to consider a transaction aborted
      - ABORT_TIMEOUT_S=60
      - KAFKA_BOOTSTRAP=broker:29092
    ports:
      - "8080:8080"
    volumes:
      - ./implementation-python-1/src:/app

  ktx-collector:
    build:
      context: ./implementation-python-1/src
      dockerfile: Dockerfile
    environment:
      - KTX_MODE=collector
      # Topic to check for ongoing transactions
      - KTX_TOPIC_TX=ktx.transaction
      - KAFKA_BOOTSTRAP=broker:29092
    volumes:
      - ./implementation-python-1/src:/app
```
Make sure to adjust the `KAFKA_BOOTSTRAP` environment variable to point to your Kafka broker(s) in Confluent Cloud or your Confluent Platform setup.

If you're using Confluent Cloud, you'll need to setup authentication (producer/consumer configs) and provide them in the `docker-compose.override.yml` file as environment variables as well as the configuration file f.e. mounting them as volumes.

The following Environment variables can be used to configure `ktx-collector`:

| Environment Variable | Description | Default |
|----------------------|-------------|---------|
| KTX_TOPIC_TX         | Topic to listen for transaction events | ktx.tx |
| KTX_TOPIC            | Topic to publish coordinator state to | ktx.state |
| KAFKA_BOOTSTRAP      | Kafka bootstrap servers | None (required) |
| CONSUMER_CONFIG      | Path to Confluent Cloud consumer config file | None |
| PRODUCER_CONFIG      | Path to Confluent Cloud producer config file | None |


The following Environment variables can be used to configure `ktx-aggregator`:

| Environment Variable   | Description                                         | Default      |
|-----------------------|-----------------------------------------------------|--------------|
| KTX_TOPIC             | Topic for transaction state                         | ktx.state    |
| KAFKA_BOOTSTRAP       | Kafka bootstrap servers                            | None |
| CONSUMER_CONFIG       | Path to Confluent Cloud consumer config file        | None         |
| KTX_LISTEN_PORT       | Port for Prometheus /metrics endpoint               | 8000         |
| ABORT_TIMEOUT_S       | Timeout in seconds to consider a transaction aborted| 60           |


## Step 3: Create Topics
The tools require two topics for application events and one for the collector's output.
1.  Navigate to the "Topics" section of your cluster.
2.  Create a topic for transaction events, using the default settings:
    `ktx.tx`
3.  Create a topic for the collector's output (if needed), using the default settings:
    `ktx.state`

## Step 4: Running the Services
You can now start the services using Docker Compose:

```bash
docker compose up -d ktx-collector ktx-aggregator
```

## Step 5: Run Reply Tool

You can run the Reply Tool using the following command:

```bash
# Start a development container & enter it
docker compose up -d py-dev
docker compose exec -it py-dev bash

# Setup Python environment
cd /app/implementation-python-1/

python3 -m venv venv
source venv/bin/activate
pip install -e .

# Run the replayer
ktx-replay --kafka-bootstrap broker:29092 \
	--topic-tx ktx.transaction \
	--file ../scenarios/00_minimal/events.jsonl
```

## Step 6: Check Metrics

You can check the Prometheus metrics exposed by the `ktx-aggregator` service by navigating to `http://localhost:8080/metrics` in your web browser.
