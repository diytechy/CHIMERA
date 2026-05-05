## Repository Overview

This project contains a Terra world configuration, which is packaged into a zip folder to be available to the Terra plugin for minecraft.  This plugin is used for world generation and contains various functions and expressions to create detailed terrain as a function of a world seed and x,y,z coordinates.  These configurations are used to define various parameters that control how this world generation occurs.

This world is templated for the most recent Terra version 7.0 build (https://github.com/PolyhedralDev/Terra).  Older documentation related to configuration development can be referenced from https://terra.polydev.org/config/development/index.html

The core "build" for this repository is intended to be a batch script ".scripts/AuditAndPackage.bat" which is described further below.

## Architecture

### Key Directories

- `../Terra`: If available, this should contain the source code for Terra.
- `biomes/`: Refer to README.md in this directory.
- `biome-distribution/`: Refer to README.md in this directory.
- `features/`: Refer to README.md in this directory.
- `math/`: Refer to README.md in this directory.
- `palettes/`: Refer to README.md in this directory.
- `structures/`: Refer to README.md in this directory.
- `.scripts/`: Includes various files that perform different checks.

### Key Files

- `.scripts/AuditAndPackage.bat`: The main build script for Windows environment. The script performs three key steps:
  1. **Make the package** - Creates `.artifacts/ORIGEN2.zip` (via pack.sh or PowerShell fallback)
  2. **Create the biome table** - Generates `.artifacts/BiomeTable.csv` with distribution percentages (via `.scripts/calculate_biome_percentages.py`). The script also copies or creates `SuggestedImprovements.md` in `.artifacts/`.
  3. **Audit the yml files** - YAML linting and validation (via check-biomes.sh if WSL available)
  4. **Pack configurations and implications of sampler / function / expression definition** -Definitions around key processing information and potential optomizations can be found in 'sampler-optimization-reference.md'
  

The batch file intelligently adapts to available tools:
- **Python** is required for BiomeTable.csv generation
- **WSL** is optional (used for packaging and YAML validation)
- **PowerShell** is used as fallback for packaging if WSL unavailable

See `.scripts/WORKFLOW_DOCUMENTATION.md` for complete details.

- `pack.yml`: The main definition file that tells the Terra plugin how to generate the world. The primary biome configuration is specified in the "biomes:" key.

- `.scripts/calculate_biome_percentages.py`: Python script that generates BiomeTable.csv by analyzing biome distribution pipelines and calculating exact percentages for each preset.

- `.scripts/check-biomes.sh`: Bash script that validates YAML syntax and checks color key consistency across biome files. Generates `SuggestedImprovements.md`.

- `.artifacts/BiomeTable.csv`: A comprehensive table listing all biomes and their distribution across presets. Includes new columns derived from biome files: `Extends`, `VanillaID`, `LAND_CAVES`, `SPECIAL_CAVES`, `CAVERNS_LAND`, and `River`.

**Table Structure**:

The table includes the following columns:

- **BiomeID**: The unique identifier from the biome file's `id:` field
- **Extends**: The parent biome(s) this biome inherits from (from `extends:` key)
- **Color**: The color reference (from `color:` key, typically `$biomes/colors.yml:BIOME_ID`)
- **Preset Columns**: One column per preset (default, origen2, rearth, single, single_debug) showing the **exact percentage** that biome appears in that preset's distribution

**Important**: The table now shows **percentages** (e.g., "4.6875%") instead of Y/N flags, providing accurate distribution data.

**Coverage**: The table includes ALL valid (non-abstract) biomes, even those with 0.0000% across all presets, providing a complete inventory of available biomes.

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