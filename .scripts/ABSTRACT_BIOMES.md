# Abstract Biomes in Terra

## Overview

The `abstract: true` flag in Terra biome configuration files marks a biome as a **template biome** designed for inheritance, not direct world generation.

## Purpose

Abstract biomes serve as reusable templates that define common properties for multiple concrete biomes, following an inheritance pattern similar to abstract classes in object-oriented programming.

## How It Works

### Abstract Biomes (Templates)

- **Location**: `biomes/abstract/` directory (organized by category)
- **Flag**: `abstract: true` in the YAML configuration
- **Purpose**: Define reusable properties like:
  - Colors (sky, fog, grass, foliage, water)
  - Climate settings (temperature, precipitation, downfall)
  - Terrain equations
  - Feature sets
  - Palettes
  - Mob spawns
- **World Generation**: **NOT** placed in the world directly

### Concrete Biomes (Actual Biomes)

- **Location**: Other biome directories (`biomes/land/`, `biomes/ocean/`, `biomes/cave/`, etc.)
- **Flag**: No `abstract` flag (or `abstract: false`)
- **Inheritance**: Use the `extends:` key to inherit from one or more abstract biomes
- **World Generation**: These are the actual biomes placed in the world

## Example

### Abstract Biome Template

File: `biomes/abstract/environment/land/dry/environment_land_dry_desert.yml`

```yaml
id: ENVIRONMENT_LAND_DRY_DESERT
type: BIOME
abstract: true  # This is a template only

colors:
  fog: 0xc0d8ff
  water: 0x32A598
  water-fog: 0x32A598
  sky: 0x6eb1ff
  grass: 0xBFB755
  foliage: 0xAEA42A

climate:
  precipitation: false
  temperature: 2.0
  downfall: 0.0
```

### Concrete Biome Using Templates

File: `biomes/land/dry/desert/white/desert.yml`

```yaml
id: DESERT
type: BIOME
# NO abstract flag - this is a real biome

extends:
  - COLOR_XERIC              # Inherits xeric color palette
  - ENVIRONMENT_LAND_DRY_WHITE_DESERT  # Inherits desert climate
  - EQ_GLOBAL_DUNES          # Inherits dune terrain equation
  - CARVING_LAND             # Inherits land carving settings
  - BASE                     # Inherits base features

color: $biomes/colors.yml:DESERT

vanilla: minecraft:desert

palette:
  - SAND: $meta.yml:top-y
  - << meta.yml:palette-bottom

features:
  flora:
    - CACTUS_SPARSE
    - DEAD_BUSHES
```

## Abstract Biome Categories

The `biomes/abstract/` directory is organized by purpose:

### `/abstract/base.yml`
- Root template with universal settings (deposits, ores, cave features)
- Extended by almost all biomes

### `/abstract/carving/`
- Carving settings (caves, ravines)
- Examples: `carving_land.yml`, `carving_ocean.yml`, `carving_none.yml`

### `/abstract/color/`
- Color palettes for similar biome types
- Examples: `color_frozen.yml`, `color_tundra.yml`, `color_xeric.yml`

### `/abstract/environment/`
- Climate and atmospheric settings
- Organized by biome type (land/marine) and climate zone
- Examples: Desert, tundra, tropical, oceanic environments

### `/abstract/features/`
- Feature collections (ores, deposits, rivers)
- Examples: `ores_default.yml`, `ores_emerald.yml`, `deposits_infested.yml`

### `/abstract/palettes/`
- Block palette definitions
- Examples: `palette_ocean.yml`, `palette_sand_ocean.yml`

### `/abstract/terrain/`
- Terrain equation templates
- Examples: `eq_global_ocean.yml`, `eq_mountains.yml`, `eq_spikes.yml`

## Enforcement

**Question**: Does Terra actually prevent abstract biomes from being used in world generation, or is it just a design convention?

**Answer**: Based on investigation of the Terra source code:

### Evidence of Enforcement

1. **AbstractConfigLoader**: Terra uses a specialized `AbstractConfigLoader` from the Tectonic config library to load biome configurations
2. **Naming Convention**: The loader is specifically named "AbstractConfigLoader," suggesting it handles abstract configs specially
3. **Observed Behavior**:
   - Abstract biomes **never** appear in BiomeTable.csv as generated biomes
   - Abstract biomes **only** appear in the "Extends" column of concrete biomes
   - No biome distribution files reference abstract biome IDs

4. **Code Evidence**: In `ConfigPackImpl.java:200`, Terra logs "Loading abstract config" when processing configs through the AbstractConfigLoader, but these configs are loaded into the inheritance system, not the biome registry for world generation

### Conclusion

While the exact implementation details are in the Tectonic library (not accessible), the behavior strongly suggests:

- ✅ **Abstract biomes ARE filtered out** from being registered as usable biomes in world generation
- ✅ **Abstract biomes ARE available** for inheritance via the `extends:` mechanism
- ✅ **This is enforced by the config system**, not just a convention

### What Happens If You Use an Abstract Biome ID in Distribution?

If you were to reference an abstract biome ID (like `ENVIRONMENT_LAND_DRY_DESERT` or `BASE`) in:
- Biome distribution pipelines (`biome-distribution/stages/*.yml`)
- Preset source definitions (`biome-distribution/presets/*.yml`)

The likely behavior would be:
- **Registration Error**: Terra would fail to find the biome in the usable biome registry
- **Load Failure**: The config pack might fail to load, or
- **Silent Skip**: The reference might be ignored/skipped with a warning

**Best Practice**: Never reference abstract biome IDs in biome distribution configurations. They are for inheritance only.

## Benefits of Abstract Biomes

### 1. Code Reuse
Define common properties once, use in many biomes:
```yaml
# Instead of repeating climate settings in 10 desert biomes:
extends:
  - ENVIRONMENT_LAND_DRY_DESERT  # Inherits all desert climate settings
```

### 2. Consistency
All biomes of a type share consistent properties:
- All temperate biomes can inherit from the same temperature settings
- All ocean biomes can inherit from the same water properties

### 3. Maintainability
Change multiple biomes by editing one template:
- Update `color_xeric.yml` → affects all xeric biomes
- Update `ores_default.yml` → affects all biomes using default ore distribution

### 4. Organization
Separate concerns:
- Terrain equations in `/terrain/`
- Climate in `/environment/`
- Colors in `/color/`
- Features in `/features/`

### 5. Composition
Mix and match components:
```yaml
extends:
  - COLOR_XERIC           # Dry colors
  - ENVIRONMENT_LAND_DRY_DESERT  # Desert climate
  - EQ_SPIKES             # Spiky terrain
  - CARVING_LAND          # Land caves
  - ORES_GOLD             # Gold-rich ore distribution
  - BASE                  # Universal features
```

## Multiple Inheritance

Biomes can extend multiple abstract biomes:

```yaml
extends:
  - ENVIRONMENT_LAND_DRY_DESERT
  - COLOR_XERIC
  - EQ_GLOBAL_DUNES
  - CARVING_LAND
  - ORES_GOLD
  - BASE
```

Properties are merged in order (later entries can override earlier ones).

## Verification

To verify abstract biomes are never used in world generation:

1. **Check BiomeTable.csv**: Abstract biome IDs should never appear as BiomeID (first column)
2. **Check Distribution Files**: Abstract biome IDs should never appear in:
   - `biome-distribution/stages/*.yml`
   - `biome-distribution/presets/*.yml`
3. **Check Extends Column**: Abstract biome IDs should only appear in the Extends column

---

**Last Updated**: 2026-01-07
**Terra Version**: 7.0
**Related Files**:
- `biomes/abstract/` - All abstract biome templates
- `.scripts/calculate_biome_percentages.py` - Biome distribution calculator (ignores abstract biomes)
- `.artifacts/BiomeTable.csv` - Generated biome distribution table
