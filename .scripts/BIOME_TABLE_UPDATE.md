# BiomeTable.csv Generation Update

**Date**: 2026-01-07

## Changes Made

Updated `calculate_biome_percentages.py` to improve biome table generation and intermediate biome detection.

## Key Improvements

### 1. Include All Valid Biomes

**Previous Behavior**:
- Only biomes that appeared in at least one preset distribution were included in BiomeTable.csv
- Valid biomes with 0% across all presets were excluded from the table

**New Behavior**:
- **All valid biomes** (non-abstract biomes with `type: BIOME`) are now included in BiomeTable.csv
- Biomes that don't appear in any preset are listed with 0.0000% for all presets
- This provides a complete inventory of all available biomes in the pack

**Benefits**:
- Complete documentation of all biomes
- Easy to identify unused biomes (those with 0% across all presets)
- Helps detect biomes that might be candidates for inclusion in presets

### 2. Automatic Intermediate Biome Detection

**Previous Behavior**:
- Used a hardcoded list of `known_intermediate_names` to identify intermediate biomes
- Required manual updates when new intermediate biomes were introduced
- Could miss intermediate biomes not in the hardcoded list

**New Behavior**:
- **Automatically derives** intermediate biomes by checking if they have valid biome files
- An intermediate biome is defined as:
  - A biome ID that appears in distribution calculations, BUT
  - Does NOT have a corresponding non-abstract biome file
  - Is NOT the special keyword 'SELF'
- No hardcoded lists needed

**Benefits**:
- Maintenance-free - automatically adapts to new intermediate biomes
- More accurate - catches all unresolved intermediates
- Clearer logic - intermediate status is determined by file existence, not naming conventions

### 3. Enhanced Biome File Cache

**Previous Behavior**:
- Cached biome file paths and IDs
- Did not track which biomes were abstract vs. valid

**New Behavior**:
- Caches biome file paths and IDs
- **Tracks valid (non-abstract) biomes separately**
- Reports counts: "Cached 438 biome files (329 valid, 109 abstract)"

**Benefits**:
- Clear separation between template biomes and usable biomes
- Provides visibility into the biome file structure
- Enables efficient validation

## Results

### Current Statistics

```
Building biome file cache from biomes...
Cached 438 biome files (329 valid, 109 abstract)

Valid biomes found in files: 329
Biomes found in distributions: 205
Total biomes to include in table: 329

CSV written successfully: .scripts\BiomeTable.csv
  Valid biomes: 329
  Unresolved intermediates: 0
```

### Table Contents

The BiomeTable.csv now contains:
- **329 rows** (plus 1 header row = 330 total lines)
- **All valid biomes**, including:
  - 205 biomes that appear in at least one preset distribution
  - 124 biomes with 0.0000% across all presets (not currently used)

### Examples of Newly Included Biomes

Biomes now in the table that were previously excluded (all at 0% in all presets):

```
ALIEN_MARSH
ALPINE_ASCENDANCY_RIVER
ANCIENT_CAVES
ARCHIPELAGO
ARID_PALE_GARDEN_COAST
ARID_PALE_GARDEN_RIVER
BAD_BALCOONIES_RIVER
BLACK_SAND_BEACH
BOREAL_CRATER_LAKE
BOREAL_EXTINCT_VOLCANO
... (114 more)
```

These are all valid, usable biomes that could be added to presets if desired.

## Implementation Details

### Code Changes

1. **BiomeReader Class**:
   - Added `_valid_biomes` class variable to track non-abstract biomes
   - Updated `build_cache()` to check `abstract` flag and separate valid biomes
   - Added `get_all_valid_biomes()` method to retrieve all valid biome IDs

2. **generate_csv_output() Function**:
   - Removed hardcoded `known_intermediate_names` set
   - Added `valid_biomes = BiomeReader.get_all_valid_biomes()` to get all valid biomes
   - Changed `all_biomes` to union of valid biomes and distribution biomes: `valid_biomes | distribution_biomes`
   - Simplified intermediate detection: `biome_id not in valid_biomes and biome_id != 'SELF'`

3. **main() Function Summary Section**:
   - Removed hardcoded intermediate names list
   - Uses `valid_biomes` set for marking unresolved biomes
   - Simplified logic throughout

## Validation

### No Unresolved Intermediates

```
UNRESOLVED INTERMEDIATE BIOMES:
======================================================================
These biomes appear in the distribution but are not final biomes.
They should be fully resolved through REPLACE stages or removed.

  None - all biomes properly resolved!
```

This confirms that all biome distribution pipelines correctly resolve intermediate biomes to final valid biomes.

## Future Improvements

Possible enhancements for future versions:

1. **Usage Analysis**: Add a column indicating which biomes are unused (0% in all presets)
2. **Category Grouping**: Group biomes by climate, terrain type, or other categories
3. **Dependency Tracking**: Show which intermediate biomes lead to each final biome
4. **Coverage Metrics**: Calculate what percentage of valid biomes are actually used

---

**Related Files**:
- `.scripts/calculate_biome_percentages.py` - Updated script
- `.scripts/BiomeTable.csv` - Generated table (329 biomes)
- `.scripts/ABSTRACT_BIOMES.md` - Documentation on abstract biomes
