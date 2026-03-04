# River Assignments for Land Biomes

Generated from BiomeTable.csv and set_biomes_in_climates_origen.yml

## Filters Applied
- Origin: Land (+ archipelago Ocean biomes)
- Excluded: River biomes, subsurface/extrusion biomes
- Excluded: Biomes that already have a River column value

## Summary
- Total qualifying biomes: 109
- Direct river match: 23
- Inferred from climate: 64
- Unknown: 22

## Available River Tags (from add_rivers.yml)

- `USE_ARID_PALE_GARDEN_RIVER`
- `USE_COLD_RIVER`
- `USE_DESERT_RIVER`
- `USE_FROZEN_RIVER`
- `USE_FROZEN_RIVER_FROZEN_MARSH`
- `USE_LAND_GLACIER_RIVER`
- `USE_LUKEWARM_RIVER`
- `USE_MUSHROOM_RIVER`
- `USE_ORANGE_ARID_PALE_GARDEN_RIVER`
- `USE_ORANGE_DESERT_RIVER`
- `USE_PALE_GARDEN_RIVER`
- `USE_POLAR_MUSHROOM_RIVER`
- `USE_POLAR_PALE_GARDEN_RIVER`
- `USE_RED_ARID_PALE_GARDEN_RIVER`
- `USE_RED_DESERT_RIVER`
- `USE_RIVER`
- `USE_RIVER_COASTAL_TROPICAL_SWAMP`
- `USE_RIVER_TEMPERATE_MARSH`
- `USE_RIVER_TEMPERATE_SWAMP`
- `USE_TAR_PIT_RIVER`
- `USE_TROPICAL_RIVER`

## Biome-Specific Rivers (Direct Match)

| Biome | River |
|-------|-------|
| ALPINE_ASCENDANCY | ALPINE_ASCENDANCY_RIVER |
| ARID_PALE_GARDEN | ARID_PALE_GARDEN_RIVER |
| BADLANDS | BADLANDS_RIVER |
| DRY_TEMPERATE_MOUNTAINS | DRY_TEMPERATE_MOUNTAINS_RIVER |
| DRY_TEMPERATE_WHITE_MOUNTAINS | DRY_TEMPERATE_WHITE_MOUNTAINS_RIVER |
| FROZEN_FUNGI | FROZEN_FUNGI_RIVER |
| GLOOMY_GORGE | GLOOMY_GORGE_RIVER |
| HIGHLANDS | HIGHLANDS_RIVER |
| LAND_GLACIER | LAND_GLACIER_RIVER |
| MOUNTAINS | MOUNTAINS_RIVER |
| MOUNTAIN_MIRRORS | MOUNTAIN_MIRRORS_RIVER |
| ORANGE_ARID_PALE_GARDEN | ORANGE_ARID_PALE_GARDEN_RIVER |
| ORANGE_XERIC_MOUNTAINS | ORANGE_XERIC_MOUNTAINS_RIVER |
| PALE_GARDEN | PALE_GARDEN_RIVER |
| POLAR_PALE_GARDEN | POLAR_PALE_GARDEN_RIVER |
| RED_ARID_PALE_GARDEN | RED_ARID_PALE_GARDEN_RIVER |
| RED_XERIC_MOUNTAINS | RED_XERIC_MOUNTAINS_RIVER |
| SCARLET_SANCTUARY | SCARLET_SANCTUARY_RIVER |
| SNOWY_BLACKSTONE_MOUNTAINS | SNOWY_BLACKSTONE_MOUNTAINS_RIVER |
| SNOWY_MOUNTAINS | SNOWY_MOUNTAINS_RIVER |
| SNOWY_TUFF_MOUNTAINS | SNOWY_TUFF_MOUNTAINS_RIVER |
| SWAMP | SWAMP_RIVER |
| XERIC_MOUNTAINS | XERIC_MOUNTAINS_RIVER |

## Inferred River Assignments

### USE_COLD_RIVER (8 biomes)

| Biome | Reasoning |
|-------|-----------|
| AUTUMNAL_WOODLANDS | from boreal-cold |
| ENCHANTED_WOODLANDS | from boreal-cold |
| PRAIRIE | averaged: USE_COLD_RIVER (62%), USE_RIVER (38%) |
| SAKURA_WOODLANDS | from boreal-cold |
| STEPPE | averaged: USE_COLD_RIVER (67%), USE_RIVER (33%) |
| SUNFLOWER_PRAIRIE | averaged: USE_COLD_RIVER (67%), USE_RIVER (33%) |
| VERTICAL_VISTAS | averaged: USE_COLD_RIVER (50%), USE_FROZEN_RIVER (50%) |
| VERTICAL_VISTAS_WARM | from boreal-warm-highlands |

### USE_DESERT_RIVER (4 biomes)

| Biome | Reasoning |
|-------|-----------|
| ARID_SPIKES | from hot-desert-flat-red |
| BADLANDS_BUTTES | from hot-desert-flat-red |
| CARVING_CREAKS | from hot-desert-white |
| SNOWY_BADLANDS | from cold-desert |

### USE_FROZEN_RIVER (17 biomes)

| Biome | Reasoning |
|-------|-----------|
| COLD_EXTINCT_VOLCANO | averaged: USE_FROZEN_RIVER (67%), USE_DESERT_RIVER (33%) |
| FROSTBOUND_CHASMS | from ice-cap-highlands |
| FROSTCOATED_BOG | from boreal-snowy-flat |
| FROZEN_ARCHIPELAGO | from frozen-archipelago-zone |
| FROZEN_MARSH | from boreal-snowy-flat |
| FROZEN_SPIRES | from ice-cap-highlands |
| ICE_CAPS | from ice-cap-highlands |
| ICE_SPIKES | from ice-cap-flat |
| MONTANE_FOREST | averaged: USE_FROZEN_RIVER (67%), USE_COLD_RIVER (33%) |
| POLAR_MUSHROOM_FIELDS | from polar-island |
| SEARING_TORS | from boreal-snowy-highlands |
| SNOWY_BIRCH_FOREST | from boreal-snowy |
| SNOWY_PLAINS | from boreal-snowy-flat |
| SNOWY_SPIRES | from ice-cap-highlands |
| SNOWY_TAIGA | from boreal-snowy |
| TUNDRA | from tundra-flat |
| VERTICAL_VISTAS_FROZEN | from tundra-highlands |

### USE_LUKEWARM_RIVER (8 biomes)

| Biome | Reasoning |
|-------|-----------|
| BADLANDS_BALCONIES | from hot-steppe-flat-red |
| DIKSAM_PLATEAU | from hot-steppe-highlands-white |
| GRASS_SAVANNA | from tropical-savanna-dry-flat |
| SAVANNA | from tropical-savanna-dry-flat |
| SAVANNA_OVERHANGS | from tropical-savanna-dry-highlands |
| TAR_PITS | from hot-steppe-flat-white |
| TROPICAL_EXTINCT_VOLCANO | averaged: USE_LUKEWARM_RIVER (50%), USE_TROPICAL_RIVER (50%) |
| WET_SAVANNA | from tropical-savanna-wet-flat |

### USE_RIVER (13 biomes)

| Biome | Reasoning |
|-------|-----------|
| ALIEN_MARSH | from temperate-warm-flat |
| DARK_FOREST | from temperate-warm-flat |
| MARSH | from temperate-warm-flat |
| MUSHROOM_FIELDS | from island |
| OAK_SAVANNA | from temperate-hot-flat |
| PALM_FOREST | from temperate-hot-dry |
| ROCKY_GRASSLAND | from temperate-hot-flat |
| SAKURA_STREAMS | from temperate-hot |
| TEMPERATE_ALPHA_MOUNTAINS | from temperate-hot-highlands |
| TEMPERATE_GRASSLAND | from temperate-warm-dry-flat |
| TEMPERATE_OVERPASS | from temperate-hot |
| VERDANT_VALLEYS | from temperate-hot |
| WOODED_BUTTES | from temperate-hot |

### USE_TROPICAL_RIVER (14 biomes)

| Biome | Reasoning |
|-------|-----------|
| BAMBOO_BASIN | from tropical-monsoon-flat |
| BAMBOO_JUNGLE | from tropical-rainforest-flat |
| CANOPY_CASCADES | from tropical-rainforest |
| CLOUD_FOREST | from tropical-rainforest |
| DRY_WOODLANDS | from tropical-monsoon-flat |
| JUNGLE | from tropical-rainforest-flat |
| LUSH_LOOPS | from tropical-rainforest |
| MONSOON_FOREST | from tropical-monsoon-flat |
| OVERGROWN_CLIFFS | averaged: USE_TROPICAL_RIVER (67%), USE_LUKEWARM_RIVER (33%) |
| ROCKY_JUNGLE | from tropical-rainforest-flat |
| TROPICAL_FLOODPLAIN | from tropical-rainforest-flat |
| TROPICAL_MESA | from tropical-mesa |
| TROPICAL_MUSHROOM_FIELDS | from tropical-island |
| TROPICAL_RAINFOREST | from tropical-rainforest-flat |

## Unknown (No Climate Region Found)

| Biome | Notes |
|-------|-------|
| ARID_PALE_GARDEN_COAST | No climate region found |
| BEACH | No climate region found |
| FROZEN_BEACH | No climate region found |
| ICY_INCISIONS | No climate region found |
| MANGROVE_SWAMP | No climate region found |
| MUDDY_COASTS | No climate region found |
| MUSHROOM_COAST | No climate region found |
| ORANGE_ARID_PALE_GARDEN_COAST | No climate region found |
| PALE_GARDEN_COAST | No climate region found |
| PALM_BEACH | No climate region found |
| PINE_BARRENS | No climate region found |
| POLAR_MUSHROOM_COAST | No climate region found |
| POLAR_PALE_GARDEN_COAST | No climate region found |
| RED_ARID_PALE_GARDEN_COAST | No climate region found |
| SANDY_SPLITS | No climate region found |
| SECLUDED_VALLEY | No climate region found |
| SHALE_BEACH | No climate region found |
| SHRUB_BEACH | No climate region found |
| SINKHOLE_FROZEN | No climate region found |
| SINKHOLE_JUNGLE | No climate region found |
| SNOWY_SEA_CAVES | No climate region found |
| TROPICAL_MUSHROOM_COAST | No climate region found |
