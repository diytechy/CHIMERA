# Vanilla Biome Assignments — Unallocated ID Recommendations

Generated: 2026-04-02  
Source: VanillaJavaBiomes.csv × .artifacts/BiomeTable.csv analysis

This document records the recommended and applied changes to CHIMERA biome vanilla IDs to cover
all previously unallocated non-nether/non-end vanilla biome identifiers.

---

## Priority 1 — Modern MC IDs (valid in 1.18+ natural generation)

These 5 IDs exist in current Minecraft and have the most direct gameplay impact
(mob spawning, music, biome tags, map coloring).

| Vanilla ID | CHIMERA Biome | Previous ID | File | Reasoning |
|---|---|---|---|---|
| `minecraft:deep_warm_ocean` | TROPICAL_DEEP_OCEAN | `warm_ocean` | `biomes/ocean/warm/deep-ocean/tropical_deep_ocean.yml` | It IS a deep warm ocean — `warm_ocean` was simply the wrong depth tier |
| `minecraft:windswept_gravelly_hills` | BARE_BOULDERFIELDS | `windswept_hills` | `biomes/rearth/variants/barren_tilted.yml` | Bare, exposed boulder-covered high-elevation terrain (temp=0.028, elev=0.875) — gravelly windswept hills |
| `minecraft:old_growth_birch_forest` | ASPEN_FOREST | `birch_forest` | `biomes/land/continental/monsoon_continental/forest/aspen_forest.yml` | Tall birch/aspen trees are the defining feature; better semantic match than plain `birch_forest` |
| `minecraft:eroded_badlands` | ARID_SPIKES | `badlands` | `biomes/land/dry/desert/red/arid_spikes.yml` | Uses `EQ_SPIKES` terrain — spiky pinnacle terrain IS eroded badlands |
| `minecraft:stony_peaks` | ROCKY_REFUGE | `plains` | `biomes/rearth/land/rocky_refuge.yml` | Rocky elevated terrain (elev=0.875) that is not freezing — stony_peaks is non-snowy rocky summit |

---

## Priority 2 — Legacy IDs (removed from 1.18 natural gen, still functional in Terra)

| Vanilla ID | CHIMERA Biome | Previous ID | File | Reasoning |
|---|---|---|---|---|
| `minecraft:snowy_mountains` | SNOWY_MOUNTAINS | `frozen_peaks` | `biomes/land/cold/polar/tundra/mountain/snowy_mountains.yml` | Literally named SNOWY_MOUNTAINS; less extreme than jagged/frozen peaks |
| `minecraft:mushroom_field_shore` | MUSHROOM_COAST | `mushroom_fields` | `biomes/land/unique/mushroom/mushroom_coast.yml` | This IS the shore/coast of a mushroom island |
| `minecraft:desert_hills` | DESERT_TERRACES | `desert` | `biomes/land/dry/desert/white/desert_terraces.yml` | Stratified elevated desert (elev=0.5) with layered terrain |
| `minecraft:wooded_hills` | OAK_WOODLANDS | `snowy_taiga` | `biomes/biomes/woodlands/oak_woodlands.yml` | Oak woodland on elevated terrain; `snowy_taiga` was clearly wrong |
| `minecraft:taiga_hills` | BOREAL_MESA | `taiga` | `biomes/spot/mesa/boreal_mesa.yml` | Elevated taiga-climate mesa terrain |
| `minecraft:mountain_edge` | WHITE_WALLOWS | `windswept_hills` | `biomes/rearth/land/white_wallows.yml` | Low-elevation (elev=0.125) windswept eroded valley — foothills/mountain edge |
| `minecraft:jungle_hills` | OVERGROWN_CLIFFS | `jungle` | `biomes/land/warm/overgrown_cliffs.yml` | Uses `EQ_GLOBAL_ERODED_PILLARS` — eroded jungle cliffs = elevated jungle terrain |
| `minecraft:jungle_edge` | TEMPERATE_RAINFOREST | `jungle` | `biomes/land/medium/temperate_rainforest.yml` | Cooler (temp=0.61) transitional rainforest at jungle boundary |
| `minecraft:stone_shore` | SHALE_BEACH | `beach` | `biomes/land/maritime/dry/shale_beach.yml` | Rocky/shale shoreline — precisely what stone_shore describes |
| `minecraft:birch_forest_hills` | BIRCH_WOODLANDS | `snowy_taiga` | `biomes/biomes/woodlands/birch_woodlands.yml` | Birch woodland on elevated (elev=0.5) terrain |
| `minecraft:snowy_taiga_hills` | ENCHANTED_WOODLANDS | `snowy_taiga` | `biomes/biomes/woodlands/enchanted_woodlands.yml` | Snowy elevated woodland (elev=0.5) — hills variant of snowy taiga |
| `minecraft:snowy_taiga_mountains` | SNOWY_SPIRES | `snowy_taiga` | `biomes/rearth/land/snowy_spires.yml` | Very high (elev=0.875, avgY=128) snowy taiga spire columns — extreme mountain variant |
| `minecraft:giant_tree_taiga_hills` | TALL_TIMBERLAND | `old_growth_pine_taiga` | `biomes/rearth/land/redwood_forests.yml` | Old growth pine forest at elevated terrain (elev=0.5) — hills variant |
| `minecraft:wooded_mountains` | DENSELY_WOODED_HIGHLANDS | `windswept_hills` | `biomes/land/temperate/oceanic/mountain/densely_wooded_highlands.yml` | Densely wooded at high elevation (elev=0.875) — textbook wooded_mountains |
| `minecraft:wooded_badlands_plateau` | MESA_MONUMENTS | `badlands` | `biomes/rearth/land/mesa_monuments.yml` | Tall mesa pillars (avgY=128) with plateau-top formations |
| `minecraft:badlands_plateau` | BADLANDS_BALCONIES | `badlands` | `biomes/rearth/land/badlands_balconies.yml` | Elevated badlands with balcony/ledge terrain (avgY=102) |
| `minecraft:desert_lakes` | OASIS | `beach` | `biomes/rearth/land/oasis.yml` | Water-filled desert feature; `beach` was clearly wrong |
| `minecraft:taiga_mountains` | FIR_HIGHLANDS | `snowy_slopes` | `biomes/biomes/fir_highlands.yml` | High-elevation (elev=0.875) fir/taiga forest; better than `snowy_slopes` |
| `minecraft:swamp_hills` | FOSSILIZED_FENLANDS | `plains` | `biomes/rearth/land/dinosaurs.yml` | Wet fen/bog terrain; `plains` was wrong |
| `minecraft:modified_jungle` | TROPICAL_RAINFOREST | `jungle` | `biomes/land/tropical/equatorial/forest/tropical_rainforest.yml` | Extreme high-altitude dense jungle (elev=0.875, avgY=150) |
| `minecraft:modified_jungle_edge` | CLOUD_FOREST | `jungle` | `biomes/land/tropical/equatorial/mountain/cloud_forest.yml` | High-altitude jungle boundary zone with eroded pillar terrain |
| `minecraft:dark_forest_hills` | BLACK_FOREST | `dark_forest` | `biomes/rearth/land/black_forest.yml` | Dark forest on elevated mountain-spot terrain |
| `minecraft:giant_spruce_taiga_hills` | SEQUOIA_FOREST | `old_growth_spruce_taiga` | `biomes/land/continental/humid_continental/forest/sequoia_forest.yml` | Multi-terraced old growth spruce (elev=0.5) — hills variant |
| `minecraft:modified_gravelly_mountains` | VERTICAL_VISTAS | `windswept_hills` | `biomes/rearth/land/vertical_vistas.yml` | Uses `EQ_TERRACE_MOUNTAINS` — extreme vertical terrace mountains |
| `minecraft:shattered_savanna` | SAVANNA_OVERHANGS | `savanna_plateau` | `biomes/land/tropical/savanna/mountain/savanna_overhangs.yml` | Dramatic overhang terrain (EQ_OVERHANGS) at high elevation |
| `minecraft:modified_wooded_badlands_plateau` | BADLANDS_BUTTES | `badlands` | `biomes/land/dry/desert/red/badlands_buttes.yml` | Butte-top badlands formations |
| `minecraft:modified_badlands_plateau` | CARVING_CREAKS | `badlands` | `biomes/rearth/land/carving_creaks.yml` | Carved elevated badlands (base=110, 15 terraces) — highly modified plateau |
| `minecraft:bamboo_jungle_hills` | LUSH_LOOPS | `jungle` | `biomes/rearth/land/lush_loops.yml` | Tall looping elevated jungle terrain (avgY=128, elev=0.5) |

---

## No Assignment Made

| Vanilla ID | Notes |
|---|---|
| `minecraft:shattered_savanna_plateau` | No distinct elevated shattered savanna biome in CHIMERA. SAVANNA_OVERHANGS better fits `shattered_savanna`. |

---

## Key "Wrong" Assignments Fixed

These were the most semantically incorrect before this change:

1. **OAK_WOODLANDS / BIRCH_WOODLANDS / ENCHANTED_WOODLANDS** — used `snowy_taiga` (causes snow fox and stray spawning in temperate woodlands)
2. **OASIS** — used `beach` (desert water feature with beach mob caps)
3. **SHALE_BEACH** — used `beach` instead of rocky `stone_shore`
4. **TROPICAL_DEEP_OCEAN** — used `warm_ocean` instead of correct depth tier
5. **MUSHROOM_COAST** — used `mushroom_fields` instead of shore variant
6. **FIR_HIGHLANDS** — used `snowy_slopes` (bare snowfield) instead of `taiga_mountains` (forested)
