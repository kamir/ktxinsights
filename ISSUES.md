# Known Issues

This file is used to track known issues and limitations of the Kafka Transactions Insights (KTX) project. Please refer to this document before reporting new issues.

## Metrics Exporter Startup

The metrics exporter in the `ktx-aggregator` service may take a few seconds to start up and be ready to serve metrics. If you attempt to access the `/metrics` endpoint immediately after starting the service, you might encounter erroneous data.
