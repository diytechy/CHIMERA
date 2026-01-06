# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This project contains an updated configuration for Origen, which is packaged into a zip folder to be available to the Terra plugin for minecraft.  This plugin is used for world generation.  These configurations are used to define various parameters that control how this world generation occurs.

This world is templated for the most recent Terra version 7.0 build (https://github.com/PolyhedralDev/Terra).  Older documentation related to configuration development can be referenced from https://terra.polydev.org/config/development/index.html

The core "build" for this repository is intended to be a batch script "AuditAndPackage.bat" which would trigger additional scripts (powershell or  python) to audit the various configuration files for formatting errors, package the required folders for the package into a zip folder, create a table (csv) of the biomes and their respective attributes, and create a .md or .adoc file containing suggestions for improvements (SuggestedImprovements.md or SuggestedImprovements.adoc)  Claude should create the necessary files to perform this build if they do not already exist.

## Architecture

### Core Components

1. **Price Data Sources** (`prices/providers/*.yml`): YAML files containing model pricing information for each provider
2. **Data Pipeline** (`prices/src/prices/`): Python modules that build, validate, and process pricing data
3. **Python Package** (`packages/python/`): Published package for end users to calculate costs
4. **External Data Integration**: Tools to pull and compare prices from external sources

### Key Directories

- `prices/`: Core pricing data and build tools
  - `providers/`: YAML files with provider-specific pricing
  - `src/prices/`: Python package for data processing
  - `data.json` and `data_slim.json`: Built JSON files (DO NOT EDIT DIRECTLY)
- `packages/python/`: Published Python package for users
- `tests/`: Python Test suite
- `scratch/`: Development/testing files IGNORE THESE FILES

## Important Notes

- **NEVER** edit any of yaml configuration files directly before building the package file, only edit them after as suggested changes so they can be reviewed and confirmed before being rolled into a package.

### Development Workflow


### Testing


### Code Style

