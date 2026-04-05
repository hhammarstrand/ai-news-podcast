#!/bin/bash
# Local pipeline runner for AI News Podcast
# Usage: ./run_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="${PODCAST_OUTPUT_DIR:-$SCRIPT_DIR/output}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=== AI News Podcast Pipeline ==="
echo "Timestamp: $TIMESTAMP"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR/$TIMESTAMP"

# Run the pipeline
cd "$SCRIPT_DIR/pipeline"
python -m src.main 2>&1

echo ""
echo "=== Pipeline complete ==="
echo "Output: $OUTPUT_DIR/$TIMESTAMP"