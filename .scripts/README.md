# Scripts Directory

This directory contains build, validation, and utility scripts for the Terra configuration package.

## Quick Start

**To build the complete package with validation:**

```batch
.scripts\AuditAndPackage.bat
```

This will:
1. Create the package zip → `.artifacts/ORIGEN.zip`
2. Generate biome distribution table → `.scripts/BiomeTable.csv`
3. Audit configurations → `SuggestedImprovements.md`

## Main Scripts

| Script | Status | Purpose |
|--------|--------|---------|
| **AuditAndPackage.bat** | ✅ ACTIVE | Main build orchestrator (Windows) |
| **calculate_biome_percentages.py** | ✅ ACTIVE | Generate BiomeTable.csv with distribution percentages |
| **pack.sh** | ✅ ACTIVE | Create package zip (bash) |
| **check-biomes.sh** | ✅ ACTIVE | YAML validation and linting (bash) |

## Obsolete Scripts

| Script | Status | Replacement |
|--------|--------|-------------|
| generate-biome-table.sh | ⚠️ OBSOLETE | calculate_biome_percentages.py |
| calculate-biome-percentages.sh | ⚠️ OBSOLETE | calculate_biome_percentages.py |

**Safe to delete**: Yes, these bash scripts have been replaced by the more accurate Python implementation.

## Requirements

### For Package Creation
- Windows (for batch file) OR
- WSL/Linux (for bash scripts)

### For BiomeTable.csv
- **Python 3.x** (required)
- PyYAML library: `pip install pyyaml`

### For YAML Validation (optional)
- WSL with Python and PyYAML

## Documentation

- **WORKFLOW_DOCUMENTATION.md** - Complete workflow guide
- **BIOME_TABLE_UPDATE.md** - BiomeTable.csv improvements
- **ABSTRACT_BIOMES.md** - Abstract biome system
- **ORIGEN2_REARTH_SYNC.md** - Biome preset synchronization

## Support Files

- `lib.sh` - Shared bash functions
- `vars.sh` - Environment variables
- `ViewTable.bat` - Quick CSV viewer
- `ensure_module.py` - Python dependency helper
- `debug_alpine_ascendancy.py` - Debug script for specific biome
- Various analysis markdown files

## Directory Structure

```
.scripts/
├── AuditAndPackage.bat          # Main entry point (Windows)
├── calculate_biome_percentages.py  # BiomeTable generator (Python)
├── pack.sh                       # Package creator (bash)
├── check-biomes.sh              # YAML validator (bash)
│
├── generate-biome-table.sh      # OBSOLETE - Use Python version
├── calculate-biome-percentages.sh  # OBSOLETE - Use Python version
│
├── README.md                    # This file
├── WORKFLOW_DOCUMENTATION.md    # Complete workflow guide
│
└── changelog/                   # Version history
```

---

## Biome colorizer

A small utility to generate `biomes/colors.generated.yml` from `.scripts/BiomeTable.csv` using an approximate Munsell-like H/C/V mapping.

Run:

```batch
python .scripts\biome_colorizer.py --input .scripts/BiomeTable.csv --output biomes/colors.generated.yml --seed 42
```

Notes:
- The conversion uses an HSV-based approximation and deterministic jitter controlled by `--seed`.
- The generated file is `biomes/colors.generated.yml`; you can review and merge or use it to replace `biomes/colors.yml` as desired.

---

For detailed information, see **WORKFLOW_DOCUMENTATION.md**.
