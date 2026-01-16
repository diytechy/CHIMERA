# Combined Climate Sampler System

## Overview

The combined climate sampler system optimizes biome distribution by computing temperature, precipitation, and elevation in a single pass, eliminating redundant calculations of shared dependencies like `continents(x, z)`.

## Problem: Redundant Calculations

The original three-stage climate pipeline (temperature → precipitation → elevation) recalculates expensive samplers multiple times:

| Sampler | Calculations per point |
|---------|----------------------|
| `continents(x, z)` | 33+ times |
| `elevation(x, z)` | 48+ times |
| `spawnIsland(x, z)` | Multiple times |

This happens because each stage independently calls these samplers through their dependency chains.

## Solution: Combined Climate Index

The combined approach encodes all three climate factors into a single value:

```
climateIndex = (tempIndex * 24) + (precipIndex * 4) + elevIndex
```

Where:
- `tempIndex`: 0-11 (12 temperature zones)
- `precipIndex`: 0-5 (6 precipitation levels)
- `elevIndex`: 0-3 (4 elevation variants)

This produces 288 unique combinations (12 × 6 × 4), normalized to [-1, 1] for Terra's weighted list system.

## Generated Files

### 1. `math/samplers/combined_climate.yml`

Contains the combined sampler definition with:

- **`combinedContinent`**: Combines continent noise with spawn island calculation inline
- **`combinedClimate`**: Single expression that computes all climate factors and encodes them

The sampler includes:
- Inline spawn island calculation (no external reference)
- Inline elevation noise (hills + mountains)
- Inline flatness calculation
- Inline temperature and precipitation noise
- Final encoding to climate index

### 2. `biome-distribution/stages/climate/combined_climate.yml`

Contains the combined distribution stage with 288 weighted entries mapping directly from `land` to final biomes (with elevation suffixes).

## Biome Mapping

The 288 combinations map to 72 unique biomes through a three-stage cascade:

### Temperature Stage (12 zones)
```
Index | Zone               | Weight
------|--------------------|---------
0     | ice-cap            | 1
1     | tundra             | 1
2     | boreal-snowy       | 1
3     | boreal-cold        | 1
4     | boreal-warm        | 1
5     | boreal-hot         | 1
6     | temperate-cold     | 1
7     | temperate-warm     | 3
8     | temperate-hot      | 2
9     | tropical-savanna   | 1
10    | tropical-monsoon   | 1
11    | tropical-rainforest| 4
```

### Precipitation Stage (6 levels)
```
Index | Level         | Weight
------|---------------|---------
0     | desert        | 4
1     | desert-border | 1
2     | semi-arid     | 1
3     | mid           | 1
4     | mildly-wet    | 2
5     | very-wet      | 3
```

### Elevation Stage (4 variants)
```
Index | Variant   | Weight
------|-----------|--------
0     | flat      | 1
1     | lowlands  | 1
2     | midlands  | 1
3     | highlands | 1
```

## Usage

Replace the three separate climate stages in your preset:

```yaml
# BEFORE (three stages)
stages:
  - << biome-distribution/stages/climate/temperature.yml:stages
  - << biome-distribution/stages/climate/precipitation.yml:stages
  - << biome-distribution/stages/climate/elevation.yml:stages
```

With:

```yaml
# AFTER (combined stage)
stages:
  - << biome-distribution/stages/climate/combined_climate.yml:stages
```

## Limitations

1. **Land biomes only**: The combined stage only handles the `land` → final biome transformation. Ocean, coast, mesa, volcano, and other special biomes still require separate stages.

2. **Fixed mapping**: The biome mapping is hardcoded in the generator script. Changes to the climate stages require regenerating the combined files.

3. **Weight preservation**: The combined weights are products of individual stage weights (temp × precip × elev), preserving the original distribution proportions.

## Generator Script

The `generate_combined_climate.py` script:

1. Reads configuration from the original stage files
2. Generates the biome mapping for all 288 combinations
3. Outputs both the sampler and stage YAML files

Run with:
```bash
python .scripts/generate_combined_climate.py
```

Options:
- `--dry-run`: Print output without writing files
- `-b, --base-dir`: Specify project base directory (default: current directory)

## Performance Expectations

The combined approach should provide significant performance improvements by:

1. Computing `continents(x, z)` exactly **once** per point (vs. 33+ times)
2. Computing elevation noise exactly **once** per point (vs. 48+ times)
3. Reducing REPLACE_LIST stages from 3 to 1

Note: Actual performance gains depend on Terra's internal caching behavior and the specific world generation patterns.
