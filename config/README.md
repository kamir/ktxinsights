# ktxinsights Configuration

This directory contains configuration files for connecting the `ktxinsights` toolkit to different Kafka environments.

## Usage

1.  **Copy a Template:** Choose the template that matches your environment and make a copy. For example:
    ```bash
    cp ccloud.properties.template ccloud.properties
    ```
2.  **Edit the File:** Fill in the details (bootstrap servers, API keys, etc.) in your copied file.
3.  **Run the Tools:** Use the `--config-file` argument to point the `ktxinsights` tools to your configuration file. For example:
    ```bash
    ktx-replay --config-file config/ccloud.properties ...
    ```

## Environments

*   `ccloud.properties.template`: For connecting to a Confluent Cloud cluster.
*   `local.properties.template`: For connecting to a standard local Kafka installation.
*   `cp-all-in-one.properties.template`: For connecting to a local `cp-all-in-one` Docker-based environment.
