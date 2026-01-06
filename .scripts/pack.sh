#!/bin/bash

# Sets up the files to be included in the release
# Creates Overworld.zip in .artifacts folder

set -e

SCRIPT_DIR=""
REPO_ROOT=""
ARTIFACTS_DIR="/.artifacts"
OUTPUT_FILE="/Overworld.zip"

cd ""

# Create artifacts directory if it doesnt
