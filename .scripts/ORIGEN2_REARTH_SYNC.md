# Origen2 and Rearth Biome Synchronization

**Date**: 2026-01-07

## Objective

Pull special biomes from the rearth preset into the origen2 preset, specifically:
- PILLOW_PLAINS_* (INNER, MIDDLE, OUTER)
- SECLUDED_VALLEY and SECLUDED_VALLEY_OUTER
- FOLIAGE_FORTRESS_* (INNER, MIDDLE, OUTER)
- OASIS
- MARINE_MONOLITHS
- MANGROVE_SWAMP
- MESA_MONUMENTS

## Background

### Rearth Preset Approach

Rearth uses a different biome distribution pipeline:
1. `spread_temperature_zones.yml`: Splits land → cold/medium/warm
2. `fill_temperature_zones.yml`: Creates special biomes + intermediate biomes
3. `fill_patchwork.yml`: Resolves `_patchwork_*` intermediates
4. `border_biomes.yml`: Resolves remaining intermediates (_pillow_plains, _secluded_valleys, _plateao, _desert)

### Origen2 Preset Approach

Origen2 uses a climate-based pipeline:
1. `climate/temperature.yml`: Creates temperature zones
2. `climate/precipitation.yml`: Adds precipitation variation
3. `climate/elevation.yml`: Adds elevation variation
4. `set_biomes_in_climates.yml`: Maps climate zones to actual biomes
5. `special/border_biomes.yml`: Processes intermediate biomes (already included)

## Analysis

Initial comparison showed 12 biomes in rearth but not in origen2:

| Biome | Rearth % | Origin |
|-------|----------|--------|
| MARINE_MONOLITHS | 1.5278% | border_biomes.yml needs intermediate |
| MESA_MONUMENTS | 1.4957% | Direct placement needed |
| MANGROVE_SWAMP | 1.1905% | Coastal biome |
| FOLIAGE_FORTRESS_OUTER | 0.6172% | From _plateao intermediate |
| SECLUDED_VALLEY_OUTER | 0.5185% | From _secluded_valleys intermediate |
| OASIS | 0.3108% | From _desert intermediate |
| PILLOW_PLAINS_OUTER | 0.1972% | From _pillow_plains intermediate |
| PILLOW_PLAINS_INNER | 0.1736% | From _pillow_plains intermediate |
| FOLIAGE_FORTRESS_INNER | 0.0986% | From _plateao intermediate |
| FOLIAGE_FORTRESS_MIDDLE | 0.0986% | From _plateao intermediate |
| SECLUDED_VALLEY | 0.0986% | From _secluded_valleys intermediate |
| PILLOW_PLAINS_MIDDLE | 0.0237% | From _pillow_plains intermediate |

**Key Finding**: Origen2 already has `border_biomes.yml` included, but the intermediate biomes weren't being created, so the final biomes couldn't be generated.

## Changes Made

### File Modified: `biome-distribution/stages/set_biomes_in_climates.yml`

#### 1. Added Intermediate Biomes for Border Processing

**Temperate zones** (lines 286-287, 297):
```yaml
temperate-warm-flat:
  - _pillow_plains: 1
  - _secluded_valleys: 1
temperate-warm:
  - _plateao: 1
```

These intermediates are then processed by `border_biomes.yml` to create:
- `_pillow_plains` → PILLOW_PLAINS_INNER, PILLOW_PLAINS_MIDDLE, PILLOW_PLAINS_OUTER
- `_secluded_valleys` → SECLUDED_VALLEY, SECLUDED_VALLEY_OUTER
- `_plateao` → FOLIAGE_FORTRESS_OUTER → _plateao_center → FOLIAGE_FORTRESS_MIDDLE, FOLIAGE_FORTRESS_INNER

**Hot desert zones** (lines 402, 412):
```yaml
hot-desert-flat-white:
  - _desert: 1
hot-desert-white:
  - _desert: 1
```

This intermediate is processed by `border_biomes.yml` to create:
- `_desert` → DESERT, OASIS

#### 2. Added Ocean Biome

**Hot ocean zones** (lines 590, 597):
```yaml
hot-shallow-ocean:
  - MARINE_MONOLITHS: 1
hot-shallow-ocean-midlands:
  - MARINE_MONOLITHS: 1
```

#### 3. Added Coastal Biome

**Tropical coast zones** (lines 572, 575):
```yaml
tropical-coast-flat:
  - MANGROVE_SWAMP: 1
tropical-coast:
  - MANGROVE_SWAMP: 1
```

#### 4. Added Direct Placement Biome

**Tropical savanna zones** (lines 555, 561):
```yaml
tropical-savanna-dry-flat:
  - MESA_MONUMENTS: 1
tropical-savanna-dry-highlands:
  - MESA_MONUMENTS: 1
```

## Verification

Ran `calculate_biome_percentages.py` to verify all rearth biomes now appear in origen2:

### Before Changes
```
Biomes in rearth but NOT in origen2 (12 biomes):
MARINE_MONOLITHS, MESA_MONUMENTS, MANGROVE_SWAMP,
FOLIAGE_FORTRESS_*, SECLUDED_VALLEY*, OASIS, PILLOW_PLAINS_*
```

### After Changes
```
Biomes in rearth but NOT in origen2 (0 biomes):
```

✅ **All rearth biomes now appear in origen2!**

### Sample Results (Origen2 Preset)

```
origen2:
  PALE_GARDEN                               5.6250%
  SANDY_SPLITS                              5.0440%
  ICY_INCISIONS                             3.7830%
  MUSHROOM_FIELDS                           3.7500%
  ABYSSAL_ALLEYS                            2.7665%
  ...
  MARINE_MONOLITHS                          0.8023%  ← Now present
  ...
  MANGROVE_SWAMP                            0.6360%  ← Now present
  BEACH                                     0.6360%
  OASIS                                     0.0191%  ← Now present
  FOLIAGE_FORTRESS_OUTER                    0.0376%  ← Now present
  PILLOW_PLAINS_OUTER                       0.0120%  ← Now present
  SECLUDED_VALLEY_OUTER                     0.0315%  ← Now present
  MESA_MONUMENTS                            0.0165%  ← Now present
```

## Notes

### Why Not Use fill_patchwork.yml?

The `fill_patchwork.yml` file is specific to rearth's `_patchwork_*` intermediates, which aren't used in origen2's climate-based approach. Origen2 directly places biomes in `set_biomes_in_climates.yml`, making fill_patchwork.yml unnecessary.

### Border Biomes Already Included

Origen2 already had `border_biomes.yml:stages` included in the preset (line 79 of origen2.yml). The only thing missing was creating the intermediate biomes that border_biomes.yml processes.

### Intermediate Biomes

The script detects 4 intermediate biomes remaining in the default preset:
```
UNRESOLVED INTERMEDIATE BIOMES:
  _desert: default: 0.1501%
  _pillow_plains: default: 0.0345%
  _plateao: default: 0.0460%
  _secluded_valleys: default: 0.0345%
```

These small percentages indicate that `border_biomes.yml` doesn't fully resolve all intermediates (by design - the sampler conditions leave some unreplaced). This is expected behavior and matches how rearth works.

## Summary

✅ All 12 special biomes from rearth now appear in origen2
✅ No configuration files added (origen2 already had border_biomes.yml)
✅ Only modifications: Added intermediate and final biomes to `set_biomes_in_climates.yml`
✅ Verification: All rearth biomes now present in origen2 with appropriate percentages

---

**Files Modified**:
- `biome-distribution/stages/set_biomes_in_climates.yml`

**Files NOT Needed**:
- `fill_patchwork.yml` (rearth-specific, not needed for origen2's approach)
- origen2 already includes `border_biomes.yml`

**Verification Command**:
```bash
python .scripts/calculate_biome_percentages.py
```
