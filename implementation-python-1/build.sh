#!/bin/bash
#
# build.sh: A script to build the ktxinsights Python package.
#
# This script creates a distributable wheel file in the `dist/` directory.

set -e

# Change to the directory where this script is located
cd "$(dirname "$0")"

echo "--- Building ktxinsights Package ---"

# Ensure the build tool is installed
pip install --upgrade build

# Remove any previous builds
rm -rf dist/ build/ src/ktxinsights.egg-info/

# Run the build process
python3 -m build

echo "--- Build Complete ---"
echo "Package is available in the dist/ directory."

echo "--- Installing ktxinsights Package ---"
pip install dist/*.whl --force-reinstall
echo "--- Installation Complete ---"
