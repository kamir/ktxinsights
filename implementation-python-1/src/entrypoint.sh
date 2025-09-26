#!/bin/bash
set -e

if [ "$KTX_MODE" = "aggregator" ]; then
    exec python -m ktxinsights.cli.aggregate
elif [ "$KTX_MODE" = "collector" ]; then
    exec python -m ktxinsights.cli.collect
else
    echo "Unknown KTX_MODE: $KTX_MODE"
    exit 1
fi
