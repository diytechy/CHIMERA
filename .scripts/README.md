# Scripts Directory

This directory contains build, validation, and utility scripts for the Terra configuration package.

## Quick Start

**To build the complete package with validation:**

```batch
.scripts\AuditAndPackage.bat
```

This will:
1. Create the package zip → `.artifacts/CHIMERA.zip`
2. Resolve samplers → `.artifacts/resolved_samplers.yml`, then generate the biome distribution table → `.artifacts/BiomeTable.csv`

## Main Scripts

| Script | Status | Purpose |
|--------|--------|---------|
| **AuditAndPackage.bat** | ✅ ACTIVE | Main build orchestrator (Windows) |
| **pack.sh** | ✅ ACTIVE | Create package zip (bash) |
| **resolve_samplers.py** | ✅ ACTIVE | Resolve `math/` samplers into `.artifacts/resolved_samplers.yml` |
| **calculate_biome_percentages.py** | ✅ ACTIVE | Generate BiomeTable.csv with distribution percentages |

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

### For Package Creation via bash (optional)
- WSL or Linux with `zip` — `AuditAndPackage.bat` uses `pack.sh` through WSL when available, otherwise it falls back to PowerShell's `Compress-Archive`

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
├── resolve_samplers.py          # Sampler resolver (Python)
├── calculate_biome_percentages.py  # BiomeTable generator (Python)
├── pack.sh                       # Package creator (bash)
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

A small utility to generate `biomes/colors.generated.yml` from `.artifacts/BiomeTable.csv` using an approximate Munsell-like H/C/V mapping.

Run:

```batch
python .scripts\biome_colorizer.py --input .artifacts/BiomeTable.csv --output biomes/colors.generated.yml --seed 42
```

Notes:
- The conversion uses an HSV-based approximation and deterministic jitter controlled by `--seed`.
- The generated file is `biomes/colors.generated.yml`; you can review and merge or use it to replace `biomes/colors.yml` as desired.

---

For detailed information, see **WORKFLOW_DOCUMENTATION.md**.
