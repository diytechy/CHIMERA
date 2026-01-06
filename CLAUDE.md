# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This project contains an updated configuration for Origen, which is packaged into a zip folder to be available to the Terra plugin for minecraft.  This plugin is used for world generation.  These configurations are used to define various parameters that control how this world generation occurs.

This world is templated for the most recent Terra version 7.0 build (https://github.com/PolyhedralDev/Terra).  Older documentation related to configuration development can be referenced from https://terra.polydev.org/config/development/index.html

The core "build" for this repository is intended to be a batch script ".scripts/AuditAndPackage.bat" which is described further below.

## Architecture

### Key Directories

- `biomes/`: Refer to README.md in this directory.
- `biome-distribution/`: Refer to README.md in this directory.
- `features/`: Refer to README.md in this directory.
- `math/`: Refer to README.md in this directory.
- `palettes/`: Refer to README.md in this directory.
- `structures/`: Refer to README.md in this directory.
- `.scripts/`: Includes various files that perform different checks.

### Key Files

- `.scripts/AuditAndPackage.bat`: The triggered batch file to trigger the expected processes from a windows environment.  The script should follow the high level steps:
1. Make the package
2. Create the biome table
3. Audit the yml files for formatting ( linting)

For simplicity, it may make sense for this batch file to simply call pack.sh and check-biomes.sh using wsl, but the batch file should provide proper feedback to the user if dependencies are not available.  As a fallback it could also trigger additional scripts (powershell, python, bash files).

Claude should create the necessary files to perform this build if they do not already exist.

- `pack.yml`: The main definition file, that tells the Terra plugin how to generate the world, where the primary key file is called out at "biomes:".

- `.scripts/check-biomes.sh`: The main bash file that originally just validated color definitions per biome.  This would also likely be a good place to generate the BiomeTable.csv.

- `.scripts/BiomeTable.csv`: A table the lists the different biomes and their properties.

The expectation of this able is to have the following columns, but other columns might provide good context:

BiomeID, Extends, Color, Precipitation, Temperature, Elevation

Each row would correspond to a biome file (stored in the folder "biomes").
A valid biome file can be verified by seeing the "type: BIOME" key value pair.
BiomeID would be found from the ID key in the biome file.
Extends would be found from the "extends" key in the biomme file.
Color would be found from the "color" key in the biome file.
The climate would be 
Precipitation would just be a flag indicating if the biome is prescribed a precipitation designation in precipitation.yml
Temperature would just be a flag indicating if the biome is prescribed a precipitation designation in temperature.yml
Elevation would just be a flag indicating if the biome is prescribed a precipitation designation in elevation.yml
Additional columns should also be created for each preset (Each yml file in the "presets" folder), indicating if that biome will be generated as a part of the respective preset, note this also will then require the full definition described in "stages" and "extrusions" to derive which biomes will ultimately be generated and if they are a part of the preset.

## Important Notes

- **NEVER** edit any of yaml configuration files directly before building the package file, only edit them after as suggested changes so they can be reviewed and confirmed before being rolled into a package.

### Development Workflow


### Testing


### Code Style

### Implement & Refine
 
   * Write clean, idiomatic TypeScript (or other requested language) with inline comments and clear variable names.
   * Adhere to best practices around modularity, error handling, and security.
 
### Document & Explain
 
   * Provide concise, step‑by‑step instructions for any setup or deployment.
   * Embed helpful comments and docstrings.
   * When introducing new concepts (e.g. a Terraform provider), include a 1–2 sentence definition.

### Style & Format Guidelines
 
* **Clarity First**: Short sentences, minimal jargon, **bold** key commands or config snippets.
* **Step‑by‑Step**: Use numbered lists. Each step must be a standalone action.
* **Code Blocks**: Wrap code in fenced blocks with language tags.
* **Ask Before You Leap**: If any assumption is unclear (e.g. target Node version, cloud region), request clarification.
* **Encouraging Tone**: Be supportive, forward‑thinking, and sprinkle in quick, clever humor (e.g., “Let’s squash this bug like it owes us money!”).
* **Accessibility**: Offer extra background for beginners, but clearly label “Advanced Tips” sections for experts.