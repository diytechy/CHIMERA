# Vanilla Biome Assignments — Unallocated ID Recommendations

Generated: 2026-04-02  
Source: VanillaJavaBiomes.csv × .artifacts/BiomeTable.csv analysis

This document records all applied changes to CHIMERA biome vanilla IDs to cover
previously unallocated non-nether/non-end vanilla biome identifiers.

---

## Applied — Modern MC IDs (valid in 1.18+)

### Priority 1 — New 1.18+ IDs

These 5 IDs exist in current Minecraft and have the most direct gameplay impact.

| Vanilla ID | CHIMERA Biome | Previous ID | File | Reasoning |
|---|---|---|---|---|
| `minecraft:deep_warm_ocean` | TROPICAL_DEEP_OCEAN | `warm_ocean` | `biomes/ocean/warm/deep-ocean/tropical_deep_ocean.yml` | It IS a deep warm ocean — `warm_ocean` was the wrong depth tier |
| `minecraft:windswept_gravelly_hills` | BARE_BOULDERFIELDS | `windswept_hills` | `biomes/rearth/variants/barren_tilted.yml` | Bare, exposed boulder-covered high-elevation terrain — gravelly windswept hills |
| `minecraft:old_growth_birch_forest` | ASPEN_FOREST | `birch_forest` | `biomes/land/continental/monsoon_continental/forest/aspen_forest.yml` | Tall birch/aspen trees; better match than plain `birch_forest` |
| `minecraft:eroded_badlands` | ARID_SPIKES | `badlands` | `biomes/land/dry/desert/red/arid_spikes.yml` | Uses `EQ_SPIKES` terrain — spiky pinnacle terrain IS eroded badlands |
| `minecraft:stony_peaks` | ROCKY_REFUGE | `plains` | `biomes/rearth/land/rocky_refuge.yml` | Rocky elevated terrain (elev=0.875), not freezing — non-snowy rocky summit |

### Priority 1b — 1.18 Renames of removed legacy IDs

These IDs are the direct 1.18 successors of legacy IDs that were removed from natural generation.

| Vanilla ID | Legacy ID replaced | CHIMERA Biome(s) | Previous ID | File(s) | Reasoning |
|---|---|---|---|---|---|
| `minecraft:windswept_forest` | `wooded_mountains` | DENSELY_WOODED_HIGHLANDS | `windswept_hills` | `biomes/land/temperate/oceanic/mountain/densely_wooded_highlands.yml` | Densely wooded high-elevation terrain |
| `minecraft:wooded_badlands` | `wooded_badlands_plateau` + `modified_wooded_badlands_plateau` | MESA_MONUMENTS, BADLANDS_BUTTES | `badlands` | `biomes/rearth/land/mesa_monuments.yml`, `biomes/land/dry/desert/red/badlands_buttes.yml` | Tall mesa/butte formations with trees |
| `minecraft:windswept_savanna` | `shattered_savanna` | SAVANNA_OVERHANGS | `savanna_plateau` | `biomes/land/tropical/savanna/mountain/savanna_overhangs.yml` | Dramatic overhang savanna terrain (EQ_OVERHANGS) |
| `minecraft:sparse_jungle` | `jungle_edge` + `modified_jungle_edge` | TEMPERATE_RAINFOREST, CLOUD_FOREST | `jungle` | `biomes/land/medium/temperate_rainforest.yml`, `biomes/land/tropical/equatorial/mountain/cloud_forest.yml` | Transitional/boundary jungle biomes |
| `minecraft:stony_shore` | `stone_shore` | SHALE_BEACH | `beach` | `biomes/land/maritime/dry/shale_beach.yml` | Rocky/shale shoreline |

---

## Not Applied — Legacy IDs removed in 1.18 with no successor

These IDs cause errors in 1.18+ and have no renamed equivalent. The CHIMERA biomes
below retain their original vanilla IDs.

| Legacy ID | CHIMERA Biome | Current ID | Notes |
|---|---|---|---|
| `snowy_mountains` | SNOWY_MOUNTAINS | `frozen_peaks` | Replaced by `snowy_slopes`/`frozen_peaks` (no 1:1 rename) |
| `mushroom_field_shore` | MUSHROOM_COAST | `mushroom_fields` | Removed; shore now just borders ocean |
| `desert_hills` | DESERT_TERRACES | `desert` | Removed in 1.18 |
| `wooded_hills` | OAK_WOODLANDS | `snowy_taiga` | Removed in 1.18 |
| `taiga_hills` | BOREAL_MESA | `taiga` | Removed in 1.18 |
| `mountain_edge` | WHITE_WALLOWS | `windswept_hills` | Removed in 1.18 |
| `jungle_hills` | OVERGROWN_CLIFFS | `jungle` | Removed in 1.18 |
| `birch_forest_hills` | BIRCH_WOODLANDS | `snowy_taiga` | Removed in 1.18 |
| `snowy_taiga_hills` | ENCHANTED_WOODLANDS | `snowy_taiga` | Removed in 1.18 |
| `snowy_taiga_mountains` | SNOWY_SPIRES | `snowy_taiga` | Removed in 1.18 |
| `giant_tree_taiga_hills` | TALL_TIMBERLAND | `old_growth_pine_taiga` | Removed in 1.18 |
| `badlands_plateau` | BADLANDS_BALCONIES | `badlands` | Removed in 1.18 |
| `desert_lakes` | OASIS | `beach` | Removed in 1.18 |
| `taiga_mountains` | FIR_HIGHLANDS | `snowy_slopes` | Removed in 1.18 |
| `swamp_hills` | FOSSILIZED_FENLANDS | `plains` | Removed in 1.18 |
| `modified_jungle` | TROPICAL_RAINFOREST | `jungle` | Removed in 1.18 |
| `dark_forest_hills` | BLACK_FOREST | `dark_forest` | Removed in 1.18 |
| `giant_spruce_taiga_hills` | SEQUOIA_FOREST | `old_growth_spruce_taiga` | Removed in 1.18 |
| `modified_gravelly_mountains` | VERTICAL_VISTAS | `windswept_hills` | Renamed to `windswept_gravelly_hills` (already used by BARE_BOULDERFIELDS) |
| `modified_badlands_plateau` | CARVING_CREAKS | `badlands` | Removed in 1.18 |
| `bamboo_jungle_hills` | LUSH_LOOPS | `jungle` | Removed in 1.18 |
| `shattered_savanna_plateau` | *(none)* | — | No suitable CHIMERA candidate |

---

## Key Semantic Fixes Applied

1. **TROPICAL_DEEP_OCEAN** — `warm_ocean` → `deep_warm_ocean` (correct depth tier)
2. **SHALE_BEACH** — `beach` → `stony_shore` (rocky/shale shore, not sand beach)
3. **ARID_SPIKES** — `badlands` → `eroded_badlands` (spire terrain matches exactly)
4. **ASPEN_FOREST** — `birch_forest` → `old_growth_birch_forest` (tall trees, better match)
5. **SAVANNA_OVERHANGS** — `savanna_plateau` → `windswept_savanna` (dramatic overhanging terrain)
6. **DENSELY_WOODED_HIGHLANDS** — `windswept_hills` → `windswept_forest` (densely wooded, not bare)
