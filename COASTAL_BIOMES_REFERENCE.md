# Coastal Biomes Reference

This document tracks all coastal and coast-adjacent biome definitions extracted from `set_biomes_in_climates_origen.yml` before removal for consolidated coastal biome management.

## Unique Final Coastal Biomes (30 total - minus a few)

| # | Biome Name | Source Definitions | Count |
|---|---|---|---|
| 1 | FROZEN_BEACH | polar-coast-flat | 1 |
| 2 | FROSTY_FINGERS | polar-coast-flat, polar-coast | 2 |
| 3 | FRIGID_WASTELANDS | polar-coast-flat | 1 |
| 4 | SNOWY_SEA_CAVES | polar-coast, polar-coast-highlands | 2 |
| 5 | POLAR_PALE_GARDEN_COAST | polar-coast, boreal-coast, tropical-vast-forest-coast, polar-vast-forest-coast | 4 |
| 7 | SHALE_BEACH | boreal-coast-flat | 1 |
| 8 | PINE_BARRENS | boreal-coast-flat, temperate-coast-flat | 2 |
| 9 | ROCKY_SEA_CAVES | boreal-coast, boreal-coast-highlands | 2 |
| 10 | BEACH | temperate-coast-flat, arid-coast-flat | 2 |
| 11 | SHRUB_BEACH | temperate-coast-flat | 1 |
| 13 | ARID_PALE_GARDEN_COAST | arid-coast-flat, tropical-vast-forest-coast | 2 |
| 14 | ORANGE_ARID_PALE_GARDEN_COAST | arid-coast-flat, tropical-vast-forest-coast | 2 |
| 15 | RED_ARID_PALE_GARDEN_COAST | arid-coast-flat, tropical-vast-forest-coast | 2 |
| 17 | TERRACOTTA_SEA_CAVES | arid-coast-highlands | 1 |
| 18 | MUDDY_COASTS | tropical-coast-flat | 1 |
| 19 | PALM_BEACH | tropical-coast-flat | 1 |
| 20 | MANGROVE_SWAMP | tropical-coast-flat, tropical-coast | 2 |
| 21 | LUSH_SEA_CAVES | tropical-coast, tropical-coast-highlands | 2 |
| 22 | PALE_GARDEN_COAST | boreal-vast-forest-coast, temperate-vast-forest-coast | 2 |
| 23 | FROZEN_ISLAND_SHALLOWS | polar-sinkhole-border-ocean | 1 |
| 24 | COLD_ISLAND_SHALLOWS | boreal-sinkhole-border-ocean, cold-sinkhole-border-ocean | 2 |
| 25 | ISLAND_SHALLOWS | temperate-sinkhole-border-ocean | 1 |
| 26 | TROPICAL_ISLAND_SHALLOWS | hot-sinkhole-border-ocean, tropical-sinkhole-border-ocean, desert-sinkhole-border-ocean | 3 |
| 27 | MUSHROOM_COAST | mushroom-coast | 1 |
| 28 | POLAR_MUSHROOM_COAST | polar-mushroom-coast | 1 |
| 29 | TROPICAL_MUSHROOM_COAST | tropical-mushroom-coast | 1 |
| 30 | BLACK_SAND_BEACH | volcano-coast | 1 |

## Source Categories

### Landmass Coastal Definitions (15 total)
- **Polar Region:** polar-coast-flat, polar-coast, polar-coast-highlands
- **Boreal Region:** boreal-coast-flat, boreal-coast, boreal-coast-highlands
- **Temperate Region:** temperate-coast-flat, temperate-coast, temperate-coast-highlands
- **Arid Region:** arid-coast-flat, arid-coast, arid-coast-highlands
- **Tropical Region:** tropical-coast-flat, tropical-coast, tropical-coast-highlands

### Largeland Coastal Definitions (4 total)
- polar-vast-forest-coast
- boreal-vast-forest-coast
- temperate-vast-forest-coast
- tropical-vast-forest-coast

### Sinkhole Border Ocean Definitions (7 total)
- polar-sinkhole-border-ocean
- boreal-sinkhole-border-ocean
- temperate-sinkhole-border-ocean
- hot-sinkhole-border-ocean
- tropical-sinkhole-border-ocean
- desert-sinkhole-border-ocean
- cold-sinkhole-border-ocean

### Mushroom Coastal Definitions (3 total)
- mushroom-coast
- polar-mushroom-coast
- tropical-mushroom-coast

### Volcano Coastal Definition (1 total)
- volcano-coast

## Removed Sections
The following 30 definitions have been removed from `set_biomes_in_climates_origen.yml`:

**Removed from Landmass section (lines ~45-60, ~336-345, ~702-715, ~853-865):**
1. polar-coast-flat
2. polar-coast
3. polar-coast-highlands
4. boreal-coast-flat
5. boreal-coast
6. boreal-coast-highlands
7. temperate-coast-flat
8. temperate-coast
9. temperate-coast-highlands
10. arid-coast-flat
11. arid-coast
12. arid-coast-highlands
13. tropical-coast-flat
14. tropical-coast
15. tropical-coast-highlands

**Removed from Largeland section:**
16. polar-vast-forest-coast
17. boreal-vast-forest-coast
18. temperate-vast-forest-coast
19. tropical-vast-forest-coast

**Removed from Spot biomes section (sinkhole-border-ocean variants):**
20. polar-sinkhole-border-ocean
21. boreal-sinkhole-border-ocean
22. temperate-sinkhole-border-ocean
23. hot-sinkhole-border-ocean
24. tropical-sinkhole-border-ocean
25. desert-sinkhole-border-ocean
26. cold-sinkhole-border-ocean
27. volcano-coast

**Removed from Constant mappings section:**
28. mushroom-coast
29. polar-mushroom-coast
30. tropical-mushroom-coast

## Biomes Still Present in set_biomes_in_climates_origen.yml (10 total)

These coastal biomes are still found in the main configuration file in other sections (not removed):

| # | Biome Name | Location in File |
|---|---|---|
| 1 | FRIGID_WASTELANDS | tundra-flat section |
| 3 | FROZEN_ISLAND_SHALLOWS | island-polar-shallow-ocean, polar-sinkhole-border (spot section), polar-sinkhole (landmass section) |
| 4 | COLD_ISLAND_SHALLOWS | island-boreal-shallow-ocean, boreal-sinkhole-border (spot), cold-sinkhole-border (spot) |
| 5 | ISLAND_SHALLOWS | island-temperate-shallow-ocean, temperate-sinkhole-border (spot) |
| 6 | TROPICAL_ISLAND_SHALLOWS | island-hot-shallow-ocean, hot-sinkhole-border (spot), tropical-sinkhole-border (spot), desert-sinkhole-border (spot) |
| 7 | BLACK_SAND_BEACH | volcano-coast (spot biomes section) |
| 8 | PALE_GARDEN | boreal-vast-forest, temperate-vast-forest (largeland section) |
| 9 | POLAR_PALE_GARDEN | polar-vast-forest (largeland section) |
| 10 | ARID_PALE_GARDEN, ORANGE_ARID_PALE_GARDEN, RED_ARID_PALE_GARDEN | constant mappings section |

**Important Note:** These biomes are still in the file because they serve dual purposes:
- **Island shallow biomes** are used in island-specific ocean zones AND sinkhole-border-ocean transitions
- **BLACK_SAND_BEACH** is used for volcano-coast spots
- **PALE_GARDEN variants** are used in largeland (vast forest) biomes
- **FRIGID_WASTELANDS** appears in tundra-flat
- **ROCKY_ARCHIPELAGO** is in archipelago zones

## Next Steps
- Create `fill_coasts.yml` or similar file to consolidate pure coastal biome distribution (the 17 biomes not found in main config)
- Organize by temperature gradient (polar → arid/hot)
- Group by elevation (flat, midlands, highlands)
- Consider island-specific variants for archipelago distribution
- Note: Island shallow biomes and volcano-coast biomes should remain in spot biomes section
