#!/bin/bash
#
# build_paper.sh: A script to convert the markdown paper into a PDF.
#
# This script uses pandoc and a LaTeX engine to create a professional-looking
# PDF document from the paper.md file.

set -e

# Change to the directory where this script is located
cd "$(dirname "$0")"

echo "--- Building Paper PDF ---"

# Check if pandoc is installed
if ! command -v pandoc &> /dev/null
then
    echo "Error: pandoc is not installed. Please install it to build the paper."
    echo "On macOS with Homebrew: brew install pandoc"
    exit 1
fi

# Convert the markdown file to PDF
pandoc ktxinsights_paper.md \
    --pdf-engine=xelatex \
    -o ktxinsights_paper.pdf \
    -V geometry:"margin=1in" \
    -V fontsize=12pt \
    --top-level-division=chapter \
    --table-of-contents

echo "--- Build Complete ---"
echo "PDF is available at paper-1/ktxinsights_paper.pdf"
