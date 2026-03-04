# River Assignments for Land Biomes

Generated from BiomeTable.csv and set_biomes_in_climates_origen.yml

## Filters Applied
- Origin: Land (+ archipelago Ocean biomes)
- Excluded: River biomes, subsurface/extrusion biomes
- Excluded: Biomes with existing river assignment (CSV River column OR YAML river tags)

## Summary
- Total qualifying biomes: 37
- Direct river match: 9
- Inferred from climate: 19
- Unknown: 9

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
| DRY_TEMPERATE_MOUNTAINS | DRY_TEMPERATE_MOUNTAINS_RIVER |
| DRY_TEMPERATE_WHITE_MOUNTAINS | DRY_TEMPERATE_WHITE_MOUNTAINS_RIVER |
| HIGHLANDS | HIGHLANDS_RIVER |
| MOUNTAINS | MOUNTAINS_RIVER |
| ORANGE_XERIC_MOUNTAINS | ORANGE_XERIC_MOUNTAINS_RIVER |
| RED_XERIC_MOUNTAINS | RED_XERIC_MOUNTAINS_RIVER |
| SNOWY_BLACKSTONE_MOUNTAINS | SNOWY_BLACKSTONE_MOUNTAINS_RIVER |
| SNOWY_TUFF_MOUNTAINS | SNOWY_TUFF_MOUNTAINS_RIVER |
| XERIC_MOUNTAINS | XERIC_MOUNTAINS_RIVER |

## Inferred River Assignments

### USE_COLD_RIVER (6 biomes)

| Biome | Reasoning |
|-------|-----------|
| AUTUMNAL_WOODLANDS | from boreal-cold |
| ENCHANTED_WOODLANDS | from boreal-cold |
| SAKURA_WOODLANDS | from boreal-cold |
| SUNFLOWER_PRAIRIE | averaged: USE_COLD_RIVER (67%), USE_RIVER (33%) |
| VERTICAL_VISTAS | averaged: USE_COLD_RIVER (50%), USE_FROZEN_RIVER (50%) |
| VERTICAL_VISTAS_WARM | from boreal-warm-highlands |

### USE_DESERT_RIVER (1 biomes)

| Biome | Reasoning |
|-------|-----------|
| CARVING_CREAKS | from hot-desert-white |

### USE_FROZEN_RIVER (6 biomes)

| Biome | Reasoning |
|-------|-----------|
| FROSTBOUND_CHASMS | from ice-cap-highlands |
| FROSTCOATED_BOG | from boreal-snowy-flat |
| FROZEN_SPIRES | from ice-cap-highlands |
| ICE_CAPS | from ice-cap-highlands |
| SEARING_TORS | from boreal-snowy-highlands |
| VERTICAL_VISTAS_FROZEN | from tundra-highlands |

### USE_LUKEWARM_RIVER (3 biomes)

| Biome | Reasoning |
|-------|-----------|
| DIKSAM_PLATEAU | from hot-steppe-highlands-white |
| GRASS_SAVANNA | from tropical-savanna-dry-flat |
| WET_SAVANNA | from tropical-savanna-wet-flat |

### USE_RIVER (2 biomes)

| Biome | Reasoning |
|-------|-----------|
| SAKURA_STREAMS | from temperate-hot |
| TEMPERATE_ALPHA_MOUNTAINS | from temperate-hot-highlands |

### USE_TROPICAL_RIVER (1 biomes)

| Biome | Reasoning |
|-------|-----------|
| BAMBOO_BASIN | from tropical-monsoon-flat |

## Unknown (No Climate Region Found)

| Biome | Notes |
|-------|-------|
| ICY_INCISIONS | No climate region found |
| MUSHROOM_COAST | No climate region found |
| PALE_GARDEN_COAST | No climate region found |
| POLAR_MUSHROOM_COAST | No climate region found |
| SANDY_SPLITS | No climate region found |
| SECLUDED_VALLEY | No climate region found |
| SINKHOLE_FROZEN | No climate region found |
| SINKHOLE_JUNGLE | No climate region found |
| TROPICAL_MUSHROOM_COAST | No climate region found |

## Already Assigned (Excluded from Above)

These biomes already have river tags via CSV River column or YAML tags.

| Biome | Source |
|-------|--------|
| ALIEN_MARSH | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| ALPINE_ASCENDANCY | YAML tags: USE_HIGHMOUNTAINS_RIVER |
| ARCHIPELAGO | CSV River column: General |
| ARCTIC_MESA | CSV River column: General |
| ARID_ARBORETUM | CSV River column: General |
| ARID_PALE_GARDEN | YAML tags: USE_ARID_PALE_GARDEN_RIVER |
| ARID_PALE_GARDEN_COAST | YAML tags: USE_ARID_PALE_GARDEN_RIVER |
| ARID_SPIKES | YAML tags: USE_RED_DESERT_RIVER |
| ASPEN_FOREST | CSV River column: General |
| AZALEA_FOREST | CSV River column: General |
| BADLANDS | YAML tags: USE_RED_DESERT_RIVER |
| BADLANDS_BALCONIES | YAML tags: USE_BAD_BALCOONIES_RIVER |
| BADLANDS_BUTTES | YAML tags: USE_RED_DESERT_RIVER |
| BAMBOO_JUNGLE | YAML tags: USE_TROPICAL_RIVER |
| BARE_BOULDERFIELDS | CSV River column: General |
| BEACH | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| BIRCH_FOREST | CSV River column: General |
| BIRCH_WOODLANDS | CSV River column: General |
| BITTER_HEIGHTS | CSV River column: General |
| BLACK_FOREST | CSV River column: General |
| BOREAL_EXTINCT_VOLCANO | CSV River column: Cold |
| BOREAL_MESA | CSV River column: Cold |
| BOREAL_SHRUBLAND | CSV River column: Cold |
| BROADLEAF_FOREST | CSV River column: General |
| CANOPY_CASCADES | YAML tags: USE_JUNGLE_VISTA_RIVER |
| CHAPARRAL | CSV River column: General |
| CLOUD_FOREST | YAML tags: USE_TROPICAL_RIVER |
| COLD_DESERT_MESA | CSV River column: Desert |
| COLD_EXTINCT_VOLCANO | YAML tags: USE_FROZEN_RIVER |
| COLD_STEPPE | CSV River column: General |
| DARK_FOREST | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| DARK_OAK_WOODLANDS | CSV River column: General |
| DENSELY_WOODED_HIGHLANDS | CSV River column: General |
| DESERT | CSV River column: Desert |
| DESERT_EXTINCT_VOLCANO | CSV River column: Desert |
| DESERT_MESA | CSV River column: Desert |
| DESERT_PILLARS | CSV River column: Desert |
| DESERT_SPIKES | CSV River column: Desert |
| DESERT_SPIKES_GOLD | CSV River column: Desert |
| DESERT_TERRACES | CSV River column: Desert |
| DRYBRUSH | CSV River column: Desert |
| DRY_FIR_FIELDS | CSV River column: General |
| DRY_PALM_FOREST | CSV River column: Desert |
| DRY_WOODLANDS | YAML tags: USE_LUKEWARM_RIVER |
| FIRMIHIN_FOREST | CSV River column: Desert |
| FIR_FIELDS | CSV River column: Cold |
| FIR_HIGHLANDS | CSV River column: General |
| FLOWERING_FOREST | CSV River column: General |
| FOSSILIZED_FENLANDS | CSV River column: General |
| FRIGID_WASTELANDS | CSV River column: General |
| FROSTY_FINGERS | CSV River column: General |
| FROZEN_ARCHIPELAGO | YAML tags: USE_FROZEN_RIVER |
| FROZEN_BEACH | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| FROZEN_FUNGI | YAML tags: USE_COLD_FUNGI_RIVER |
| FROZEN_MARSH | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| GLOOMY_GORGE | YAML tags: USE_GLOOMY_GORGE_RIVER |
| ICEBOUND_JUNGLE | CSV River column: General |
| ICE_SPIKES | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| JUNGLE | YAML tags: USE_TROPICAL_RIVER |
| LAND_GLACIER | YAML tags: USE_LAND_GLACIER_RIVER |
| LAVENDER_FIELDS | CSV River column: General |
| LUSH_LOOPS | YAML tags: USE_LOOPS_RIVER |
| LUSH_SEA_CAVES | CSV River column: General |
| MANGROVE_SWAMP | YAML tags: USE_RIVER_COASTAL_TROPICAL_SWAMP |
| MAPLE_GROVE | CSV River column: Cold |
| MAPLE_WOODLANDS | CSV River column: General |
| MARSH | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| MESA_MONUMENTS | CSV River column: General |
| MONSOON_FOREST | YAML tags: USE_LUKEWARM_RIVER |
| MONTANE_FOREST | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| MOORLAND | CSV River column: General |
| MOUNTAIN_MIRRORS | YAML tags: USE_FROZEN_VISTA_RIVER |
| MUDDY_COASTS | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| MURKY_MARSHLANDS | CSV River column: General |
| MUSHROOM_FIELDS | YAML tags: USE_MUSHROOM_RIVER |
| MUSKEG | CSV River column: General |
| OAK_FOREST | CSV River column: General |
| OAK_SAVANNA | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| OAK_WOODLANDS | CSV River column: General |
| OASIS | CSV River column: General |
| OLD_GROWTH_SEQUOIA_FOREST | CSV River column: Cold |
| ORANGE_ARID_PALE_GARDEN | YAML tags: USE_ORANGE_ARID_PALE_GARDEN_RIVER |
| ORANGE_ARID_PALE_GARDEN_COAST | YAML tags: USE_ARID_PALE_GARDEN_RIVER |
| ORANGE_DESERT | CSV River column: Desert |
| ORANGE_DRY_PALM_FOREST | CSV River column: Desert |
| ORANGE_XERIC_SHRUBLAND | CSV River column: Desert |
| OVERGROWN_CLIFFS | YAML tags: USE_TROPICAL_RIVER |
| PALE_GARDEN | YAML tags: USE_PALE_GARDEN_RIVER |
| PALM_BEACH | YAML tags: USE_RIVER_COASTAL_TROPICAL_SWAMP |
| PALM_FOREST | YAML tags: USE_RIVER_TEMPERATE_SWAMP |
| PEARLESCENT_DESERT | CSV River column: Desert |
| PERMAFROST_CLIFFS | CSV River column: General |
| PINE_BARRENS | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| PINE_CANOPY | CSV River column: Cold |
| POLAR_MUSHROOM_FIELDS | YAML tags: USE_POLAR_MUSHROOM_RIVER |
| POLAR_PALE_GARDEN | YAML tags: USE_POLAR_PALE_GARDEN_RIVER |
| POLAR_PALE_GARDEN_COAST | YAML tags: USE_PALE_GARDEN_RIVER |
| PRAIRIE | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| REDWOOD_WOODLANDS | CSV River column: General |
| RED_ARID_PALE_GARDEN | YAML tags: USE_RED_ARID_PALE_GARDEN_RIVER |
| RED_ARID_PALE_GARDEN_COAST | YAML tags: USE_ARID_PALE_GARDEN_RIVER |
| RED_DESERT | CSV River column: Desert |
| RED_DRY_PALM_FOREST | CSV River column: Desert |
| RED_MAPLE_GROVE | CSV River column: Cold |
| RED_XERIC_SHRUBLAND | CSV River column: Desert |
| ROCKY_ARCHIPELAGO | CSV River column: General |
| ROCKY_DESERT | CSV River column: Desert |
| ROCKY_GRASSLAND | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| ROCKY_JUNGLE | YAML tags: USE_TROPICAL_RIVER |
| ROCKY_REFUGE | CSV River column: General |
| ROCKY_SEA_CAVES | CSV River column: General |
| SAKURA_GROVE | CSV River column: General |
| SALT_FLATS | CSV River column: Desert |
| SANDSTONE_ARCHIPELAGO | CSV River column: General |
| SAVANNA | YAML tags: USE_LUKEWARM_RIVER |
| SAVANNA_OVERHANGS | YAML tags: USE_LUKEWARM_RIVER |
| SCARLET_SANCTUARY | YAML tags: USE_SCARLET_RIVER |
| SEQUOIA_FOREST | CSV River column: Cold |
| SHALE_BEACH | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| SHRUB_BEACH | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| SNOWSWEPT_MEADOWS | CSV River column: General |
| SNOWY_BADLANDS | YAML tags: USE_RED_DESERT_RIVER |
| SNOWY_BIRCH_FOREST | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| SNOWY_DUNES | CSV River column: Desert |
| SNOWY_MEADOW | CSV River column: General |
| SNOWY_MOUNTAINS | YAML tags: USE_FROZEN_RIVER |
| SNOWY_PLAINS | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| SNOWY_SEA_CAVES | YAML tags: USE_FROZEN_RIVER |
| SNOWY_SPIRES | YAML tags: USE_FROZEN_RIVER |
| SNOWY_TAIGA | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| SPRUCE_WOODLANDS | CSV River column: General |
| STEPPE | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| SUGAR_PINE_WOODLANDS | CSV River column: General |
| SWAMP | YAML tags: USE_SWAMP_RIVER |
| TAIGA | CSV River column: Cold |
| TAIGA_CLEARING | CSV River column: Cold |
| TALL_TIMBERLAND | CSV River column: General |
| TAR_PITS | YAML tags: USE_TAR_PIT_RIVER |
| TEMPERATE_EXTINCT_VOLCANO | CSV River column: General |
| TEMPERATE_GRASSLAND | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| TEMPERATE_MESA | CSV River column: General |
| TEMPERATE_MONTANE_RAINFOREST | CSV River column: General |
| TEMPERATE_MOUNTAINS | CSV River column: General |
| TEMPERATE_OVERPASS | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| TEMPERATE_RAINFOREST | CSV River column: General |
| TRAVERTINE_TERRACES | CSV River column: General |
| TROPICAL_EXTINCT_VOLCANO | YAML tags: USE_TROPICAL_RIVER |
| TROPICAL_FLOODPLAIN | YAML tags: USE_RIVER_TEMPERATE_SWAMP |
| TROPICAL_MESA | YAML tags: USE_TROPICAL_RIVER |
| TROPICAL_MUSHROOM_FIELDS | YAML tags: USE_MUSHROOM_RIVER |
| TROPICAL_RAINFOREST | YAML tags: USE_TROPICAL_RIVER |
| TUNDRA | YAML tags: USE_FROZEN_RIVER_FROZEN_MARSH |
| TUNDRA_TRACKS | CSV River column: General |
| VERDANT_VALLEYS | YAML tags: USE_VERDANT_RIVER |
| WATERY_WILDS | CSV River column: General |
| WHITE_WALLOWS | CSV River column: General |
| WOODED_BUTTES | YAML tags: USE_RIVER_TEMPERATE_MARSH |
| XERIC_SHRUBLAND | CSV River column: Desert |
| YELLOW_MAPLE_GROVE | CSV River column: Cold |
