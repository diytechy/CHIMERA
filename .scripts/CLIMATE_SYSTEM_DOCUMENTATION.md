# Terra Origen Climate System Documentation

This document explains how the climate system works in Terra Origen and how biomes are assigned to different climate zones through a hierarchical mapping system.

## Overview

The climate system uses a multi-stage pipeline to assign biomes based on three primary climate factors:
1. **Temperature** - Determines temperature zones (ice-cap, tundra, boreal, temperate, tropical)
2. **Precipitation** - Determines moisture levels (desert, steppe, savanna, monsoon, rainforest)
3. **Elevation** - Determines elevation zones (flat, lowlands, midlands, highlands)

## File Structure

The climate system is defined across several key files:

### Core Climate Files
- **`biome-distribution/stages/climate/temperature.yml`** - Defines temperature-based climate zones
- **`biome-distribution/stages/climate/precipitation.yml`** - Defines precipitation-based climate zones
- **`biome-distribution/stages/climate/elevation.yml`** - Defines elevation-based subdivisions
- **`biome-distribution/stages/set_biomes_in_climates.yml`** - Maps actual biomes to climate zones

### Preset Files
- **`biome-distribution/presets/default.yml`** - Default world generation preset
- **`biome-distribution/presets/rearth.yml`** - Alternate world generation preset
- **`biome-distribution/presets/single.yml`** - Single biome preset
- **`biome-distribution/presets/single_debug.yml`** - Debug preset

## How the Climate Hierarchy Works

### Stage 1: YAML Anchors and Aliases

The climate files use YAML anchors (&) and aliases (*) to create reusable climate zone weights.

**Example from temperature.yml:**
```yaml
default-from: land
default-to:
  - ice-cap: &iceCap         1
  - tundra: &tundra          1
  - boreal-snowy: &borealSnowy    1
  - boreal-cold: &borealCold     1
  - boreal-warm: &borealWarm     1
  - boreal-hot: &borealHot      1
  - temperate-cold: &temperateCold  1
  - temperate-warm: &temperateWarm  3
  - temperate-hot: &temperateHot   2
```

This defines **base temperature zones** with anchor names (e.g., `&iceCap`).

### Stage 2: Intermediate Climate Zones

These base zones are then applied to different terrain types using aliases:

**Example from temperature.yml:**
```yaml
to:
  mesa:
    - arctic-mesa: *iceCap
    - polar-mesa: *tundra
    - boreal-mesa: *borealSnowy
    - boreal-mesa: *borealCold
    - boreal-mesa: *borealWarm
    - boreal-mesa: *borealHot
    - temperate-mesa: *temperateCold
    - temperate-mesa: *temperateWarm
    - temperate-mesa: *temperateHot
```

This creates **intermediate climate zones** (e.g., `polar-mesa`) that combine terrain type with temperature.

The weights (`*iceCap`, `*tundra`) reference the anchor definitions from Stage 1, inheriting their relative probabilities.

### Stage 3: Precipitation Refinement

Precipitation.yml further subdivides temperature zones:

**Example:**
```yaml
default-from: tropical-rainforest
default-to:
  - hot-desert: &desert       4
  - hot-desert: &desertBorder 1
  - hot-steppe: &semiArid     1
  - tropical-savanna-dry: &mid          1
  - tropical-monsoon: &mildlyWet    2
  - tropical-rainforest: &veryWet      3
to:
  temperate-warm:
    - hot-desert: *desert
    - temperate-steppe: *desertBorder
    - temperate-warm-dry: *semiArid
    - temperate-warm: *mildlyWet
    - temperate-warm: *veryWet
```

This takes temperature zones (e.g., `temperate-warm`) and creates precipitation-refined zones (e.g., `temperate-warm-dry`).

### Stage 4: Elevation Subdivision

Elevation.yml further subdivides by elevation:

**Example:**
```yaml
default-from: ice-cap
default-to:
  - ice-cap-flat: 1
  - ice-cap: 1
  - ice-cap: 1
  - ice-cap-highlands: 1
to:
  tundra:
    - tundra-flat: 1
    - tundra: 1
    - tundra: 1
    - tundra-highlands: 1
  boreal-hot:
    - boreal-hot-flat: 1
    - boreal-hot: 1
    - boreal-hot: 1
    - boreal-hot-highlands: 1
```

The weighted lists are interpreted as:
- **Index 0**: Flat areas (low elevation, high flatness)
- **Index 1**: Lowlands
- **Index 2**: Midlands (normal elevation)
- **Index 3**: Highlands (high elevation)

### Stage 5: Biome Assignment

Finally, `set_biomes_in_climates.yml` maps these combined climate zones to actual biomes:

**Example:**
```yaml
polar-mesa:
  - COLD_DESERT_MESA: 1

ice-cap-flat:
  - ICE_SPIKES: 1
  - LAND_GLACIER: 1

ice-cap:
  - LAND_GLACIER: 2
  - SNOWY_TUFF_MOUNTAINS: 1

tropical-rainforest:
  - TROPICAL_RAINFOREST: 4
  - DENSE_JUNGLE: 2
  - BAMBOO_JUNGLE: 1
```

## Example: COLD_DESERT_MESA

Let's trace how `COLD_DESERT_MESA` gets its climate flags:

### Mapping Chain:
1. **set_biomes_in_climates.yml** assigns `COLD_DESERT_MESA` to intermediate zones:
   - `polar-mesa`
   - `cold-desert-mesa`

2. **temperature.yml** defines `polar-mesa`:
   ```yaml
   mesa:
     - polar-mesa: *iceCap
     - polar-mesa: *tundra
   ```
   This means `polar-mesa` includes both `ice-cap` and `tundra` temperature zones.

3. **elevation.yml** defines both `ice-cap` and `tundra` with elevation subdivisions:
   ```yaml
   ice-cap:
     - ice-cap-flat: 1
     - ice-cap: 1
     - ice-cap: 1
     - ice-cap-highlands: 1
   tundra:
     - tundra-flat: 1
     - tundra: 1
     - tundra: 1
     - tundra-highlands: 1
   ```

### Result:
- **Temperature: Y** - Because `polar-mesa` → `ice-cap` and `tundra` are base zones in temperature.yml
- **Elevation: Y** - Because `ice-cap` and `tundra` have elevation subdivisions in elevation.yml
- **Precipitation: N** - Because `polar-mesa` and `cold-desert-mesa` are not referenced in precipitation.yml

## Example: TROPICAL_RAINFOREST

### Mapping Chain:
1. **set_biomes_in_climates.yml** assigns it to `tropical-rainforest` zone

2. **temperature.yml** defines `tropical-rainforest` as a base zone:
   ```yaml
   - tropical-rainforest: &tropicalHot    4
   ```

3. **precipitation.yml** uses it as the default and refines it:
   ```yaml
   default-from: tropical-rainforest
   default-to:
     - hot-desert: &desert       4
     - hot-desert: &desertBorder 1
     - hot-steppe: &semiArid     1
     - tropical-savanna-dry: &mid          1
     - tropical-monsoon: &mildlyWet    2
     - tropical-rainforest: &veryWet      3
   ```

4. **elevation.yml** subdivides it further

### Result:
- **Temperature: Y** - It's a base temperature zone
- **Precipitation: Y** - It's a base precipitation zone
- **Elevation: Y** - It has elevation subdivisions

## How Presets Use These Stages

Presets like `default.yml` and `rearth.yml` reference these climate stages:

```yaml
biomes:
  type: EXTRUSION
  extrusions:
    - << biome-distribution/extrusions/add_cave_biomes.yml:extrusions
    - << biome-distribution/extrusions/add_deep_dark.yml:extrusions
  provider:
    type: PIPELINE
    pipeline:
      source:
        type: SAMPLER
        biomes:
          ocean: 1
          land: 1
      stages:
        - << biome-distribution/stages/climate/temperature.yml:stages
        - << biome-distribution/stages/climate/precipitation.yml:stages
        - << biome-distribution/stages/climate/elevation.yml:stages
        - << biome-distribution/stages/set_biomes_in_climates.yml:stages
        - << biome-distribution/stages/add_rivers.yml:stages
```

The stages are applied **in order**:
1. Temperature zones are assigned
2. Precipitation refines those zones
3. Elevation further subdivides
4. Actual biomes are placed in the resulting zones
5. Rivers and other features are added

## BiomeTable.csv Climate Flags

The `generate-biome-table.sh` script uses this hierarchy to determine climate flags:

### Algorithm:
1. **Build intermediate zone mappings** from climate files (parsing YAML anchors/aliases)
2. **Extract biome-to-zone mappings** from set_biomes_in_climates.yml
3. **Trace relationships**: For each biome, check if its assigned intermediate zones map back to base zones in each climate file
4. **Set flag**: If a relationship exists, the climate flag is "Y", otherwise "N"

### Climate Column Meanings:

- **Precipitation=Y**: The biome is assigned through the precipitation.yml climate system
- **Temperature=Y**: The biome is assigned through the temperature.yml climate system
- **Elevation=Y**: The biome is assigned through the elevation.yml climate system
- **Preset Columns (default, rearth, single, single_debug)**: Whether the biome is generated in that preset

### Special Cases:

- **All flags = N**: The biome is used as a special replacement or fallback (e.g., TEMPERATE_GRASSLAND as a "todo" replacement)
- **Cave biomes**: Typically have N for all climate flags since they use extrusions instead
- **River biomes**: May have N flags if they're added through river stages rather than climate zones
- **Ocean biomes**: May have limited climate flags depending on how they're generated

## Summary

The Terra Origen climate system is a **four-stage hierarchical mapping**:

1. **Base Climate Zones** (anchors: `&iceCap`, `&veryWet`, etc.)
2. **Intermediate Zones** (aliases: `polar-mesa`, `temperate-warm-dry`, etc.)
3. **Elevation Subdivisions** (`ice-cap-flat`, `ice-cap-highlands`, etc.)
4. **Biome Assignment** (actual biome IDs: `COLD_DESERT_MESA`, `TROPICAL_RAINFOREST`, etc.)

This system allows Terra to create realistic world generation with appropriate climate-based biome distribution while maintaining flexibility and modularity in the configuration.
