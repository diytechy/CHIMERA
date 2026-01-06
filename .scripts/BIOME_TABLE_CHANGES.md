# BiomeTable Generation Changes - Summary

## What Was Fixed

### Issue 1: Missing Preset Columns
**Problem**: The BiomeTable.csv didn't show which biomes were included in which presets (default, rearth, single, single_debug).

**Solution**: Added recursive parsing of preset files that:
- Discovers all .yml files in `biome-distribution/presets/`
- Follows `<< include` references to trace through stages and extrusions
- Extracts all biome references including those in REPLACE operations
- Adds a column for each preset showing Y/N for biome inclusion

### Issue 2: Incorrect Climate Flag Detection
**Problem**: Climate flags (Temperature, Precipitation, Elevation) were using simple string matching and missing biomes referenced through the YAML anchor/alias system.

**Example**: `COLD_DESERT_MESA` showed N for Temperature and Elevation, but it's assigned to `polar-mesa` and `cold-desert-mesa` in `set_biomes_in_climates.yml`, which map back to `ice-cap` and `tundra` temperature zones.

**Solution**: Implemented a comprehensive climate hierarchy parser that:
1. **Parses YAML anchors** (e.g., `&iceCap`) from climate files
2. **Builds intermediate zone mappings** (e.g., `polar-mesa` → `ice-cap`, `tundra`)
3. **Extracts biome-to-zone mappings** from `set_biomes_in_climates.yml`
4. **Traces relationships** through the full hierarchy to determine flags

## Before & After Examples

### COLD_DESERT_MESA
**Before:**
```
COLD_DESERT_MESA,...,N,N,N
```
- Precipitation: N
- Temperature: N ❌ (Should be Y)
- Elevation: N ❌ (Should be Y)

**After:**
```
COLD_DESERT_MESA,...,N,Y,Y,Y,N,N,N
```
- Precipitation: N ✓
- Temperature: Y ✓
- Elevation: Y ✓
- default: Y ✓
- rearth: N ✓
- single: N ✓
- single_debug: N ✓

### DEEP_DARK
**Before:**
```
DEEP_DARK,...,N,N,N
```
- Not detected in any preset ❌

**After:**
```
DEEP_DARK,...,N,N,N,Y,Y,Y,N
```
- Correctly detected in default, rearth, and single presets ✓

### TROPICAL_RAINFOREST
**Before:**
```
TROPICAL_RAINFOREST,...,???,???,???
```

**After:**
```
TROPICAL_RAINFOREST,...,Y,Y,Y,Y,N,N,N
```
- All climate flags correctly set ✓
- Preset detection working ✓

## New CSV Structure

```csv
BiomeID,Extends,Color,Precipitation,Temperature,Elevation,default,rearth,single,single_debug
```

### Column Descriptions

#### Base Columns (unchanged)
- **BiomeID**: The biome identifier (e.g., COLD_DESERT_MESA)
- **Extends**: Parent biomes this biome extends
- **Color**: Color definition reference

#### Climate Flags (improved detection)
- **Precipitation**: Y if biome is assigned through precipitation.yml climate system
- **Temperature**: Y if biome is assigned through temperature.yml climate system
- **Elevation**: Y if biome is assigned through elevation.yml climate system

#### Preset Flags (NEW)
- **default**: Y if biome is generated in the default preset
- **rearth**: Y if biome is generated in the rearth preset
- **single**: Y if biome is generated in the single preset
- **single_debug**: Y if biome is generated in the single_debug preset

## Statistics

### Climate Flag Distribution
- **Biomes with Temperature flag**: 72 biomes
- **Biomes with Precipitation flag**: 66 biomes
- **Biomes with Elevation flag**: 194 biomes

### Preset Distribution
- **default**: 285 biomes
- **rearth**: 110 biomes
- **single**: 96 biomes
- **single_debug**: 15 biomes

### Total Biomes Analyzed
- **389 biomes** across all configurations

## Technical Implementation

### New Functions in generate-biome-table.sh

1. **extract_base_climate_zones()** - Extracts base climate zones from climate files
2. **build_intermediate_zone_map()** - Maps intermediate zones to base zones using YAML anchors/aliases
3. **extract_biome_zone_mappings()** - Parses set_biomes_in_climates.yml
4. **check_climate_with_mapping()** - Traces biome → intermediate zone → base zone → climate file
5. **extract_biomes_from_yaml()** - Enhanced to capture biomes from REPLACE operations
6. **extract_biomes_from_preset()** - Recursively follows includes to find all biomes in a preset

### Processing Flow

```
1. Build climate mapping cache
   ├─ Extract base zones from climate files
   ├─ Build intermediate zone maps
   └─ Extract biome-to-zone mappings

2. Build preset cache
   └─ Recursively parse each preset file

3. Process each biome file
   ├─ Extract biome metadata
   ├─ Check climate flags (using hierarchy)
   ├─ Check preset flags
   └─ Write CSV row

4. Clean up temporary files
```

## Documentation

See **CLIMATE_SYSTEM_DOCUMENTATION.md** for detailed explanation of:
- How the climate hierarchy works
- YAML anchor/alias system
- Stage-by-stage climate refinement
- Example biome mappings
- How presets use the climate system

## Usage

```bash
# Generate BiomeTable.csv with updated detection
bash .scripts/generate-biome-table.sh

# Output location
.scripts/BiomeTable.csv
```

## Notes

- The script now correctly handles YAML anchors (&) and aliases (*)
- Climate detection traces through the full hierarchy instead of simple string matching
- Preset detection follows all `<< include` references recursively
- Special biomes (caves, rivers, fallbacks) correctly show N for climate flags when appropriate
