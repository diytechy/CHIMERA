#!/bin/bash

# ============================================================================
# pack.sh
# Creates the Terra configuration package zip file
# Package name is read from pack.yml "id:" field
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ARTIFACTS_DIR="$REPO_ROOT/.artifacts"

cd "$REPO_ROOT"

# Read package name from pack.yml
if [[ ! -f "pack.yml" ]]; then
    echo "[ERROR] pack.yml not found in repository root"
    exit 1
fi

PACK_ID=$(grep -m1 "^id:" pack.yml | sed 's/id:[[:space:]]*//' | tr -d '\r')

if [[ -z "$PACK_ID" ]]; then
    echo "[ERROR] Could not read 'id:' from pack.yml"
    exit 1
fi

OUTPUT_FILE="$ARTIFACTS_DIR/${PACK_ID}.zip"

echo "Package name: $PACK_ID"

# Create artifacts directory if it doesn't exist
mkdir -p "$ARTIFACTS_DIR"

# Remove existing zip if present
rm -f "$OUTPUT_FILE"

# Check if zip is available
if ! command -v zip &> /dev/null; then
    echo "[ERROR] 'zip' command not found."
    echo "Please install zip: sudo apt-get install zip"
    exit 1
fi

# Create zip file excluding hidden files/folders
zip -r "$OUTPUT_FILE" * -x ".*" -x "*/.*"

echo "Package created: $OUTPUT_FILE"
