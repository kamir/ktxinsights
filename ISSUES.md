# Known Issues

This file is used to track known issues and limitations of the Kafka Transactions Insights (KTX) project. Please refer to this document before reporting new issues.

## Metrics Exporter Startup

The metrics exporter in the `ktx-aggregator` service may take a few seconds to start up and be ready to serve metrics. If you attempt to access the `/metrics` endpoint immediately after starting the service, you might encounter erroneous data.


## Aggregator using auto.offset.reset=latest

The aggregator Consumer is currently using 'auto.offset.reset=latest', this means it needs to run at least until every current transaction is commited or aborted for the producer lag to have correct data. We should set this to auto.offset.reset=latest and wait with the metrics exporter startup until it's in sync instead of exposing "temporary" metrics.

## Consumer Group Ids are Hardcoded

The committed and uncommitted Consumer in `ktx-collect` use hardcoded  / prefixed Group Ids, it would be nicer to make them configurable.

## Replay Producer use fixed TX Timeout

Replay Producer sets `transaction.timeout.ms` explicitly to 60s so very slow replays might break.