# Coastal Biomes Reference

This document tracks all coastal and coast-adjacent biome definitions extracted from `set_biomes_in_climates_origen.yml` before removal for consolidated coastal biome management.

## Unique Final Coastal Biomes (26 total)

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
| 23 | MUSHROOM_COAST | mushroom-coast | 1 |
| 24 | POLAR_MUSHROOM_COAST | polar-mushroom-coast | 1 |
| 25 | TROPICAL_MUSHROOM_COAST | tropical-mushroom-coast | 1 |
| 26 | BLACK_SAND_BEACH | volcano-coast | 1 |

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

### Mushroom Coastal Definitions (3 total)
- mushroom-coast
- polar-mushroom-coast
- tropical-mushroom-coast

### Volcano Coastal Definition (1 total)
- volcano-coast

## Removed Sections
The following definitions have been extracted from `set_biomes_in_climates_origen.yml` (26 coastal + 7 oceanic):

**Removed from Landmass section (15 coast definitions):**
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

**Removed from Largeland section (4 coast-forest definitions):**
16. polar-vast-forest-coast
17. boreal-vast-forest-coast
18. temperate-vast-forest-coast
19. tropical-vast-forest-coast

**Removed from Spot biomes section (7 sinkhole-border-ocean → oceanic island shallows):**
20. polar-sinkhole-border-ocean
21. boreal-sinkhole-border-ocean
22. temperate-sinkhole-border-ocean
23. hot-sinkhole-border-ocean
24. tropical-sinkhole-border-ocean
25. desert-sinkhole-border-ocean
26. cold-sinkhole-border-ocean

**Removed from Spot biomes section (1 volcano-coast definition):**
27. volcano-coast

**Removed from Constant mappings section (3 mushroom-coast definitions):**
28. mushroom-coast
29. polar-mushroom-coast
30. tropical-mushroom-coast

## Oceanic "Shallows" Biomes - To Be Injected Elsewhere (4 total)

These biomes contain "SHALLOWS" in their name and are oceanic rather than coastal. They should be managed in ocean/island configuration files, not coastal distributions:

| # | Biome Name | Current Locations | Purpose |
|---|---|---|---|
| 1 | FROZEN_ISLAND_SHALLOWS | island-polar-shallow-ocean, polar-sinkhole-border-ocean (spot section) | Cold island ocean transitions |
| 2 | COLD_ISLAND_SHALLOWS | island-boreal-shallow-ocean, boreal-sinkhole-border-ocean (spot section) | Boreal island ocean transitions |
| 3 | ISLAND_SHALLOWS | island-temperate-shallow-ocean, temperate-sinkhole-border-ocean (spot section) | Temperate island ocean transitions |
| 4 | TROPICAL_ISLAND_SHALLOWS | island-hot-shallow-ocean, hot/tropical/desert-sinkhole-border-ocean (spot section) | Tropical island ocean transitions |

**Note:** These biomes serve dual purposes:
- Primary: Island-specific shallow ocean zones (island-X-shallow-ocean)
- Secondary: Sinkhole-border-ocean transitions in spot biomes section

They should remain in the ocean biome configuration and spot biemes sections, NOT in coastal distributions.

## Biomes Still Present in set_biomes_in_climates_origen.yml (6 true coastal biomes)

These coastal biomes are still found in the main configuration file in other sections (not removed):

| # | Biome Name | Location in File |
|---|---|---|
| 1 | FRIGID_WASTELANDS | tundra-flat section |
| 2 | ROCKY_ARCHIPELAGO | archipelago-zone section |
| 3 | BLACK_SAND_BEACH | volcano-coast (spot biomes section) |
| 4 | PALE_GARDEN | boreal-vast-forest, temperate-vast-forest (largeland section) |
| 5 | POLAR_PALE_GARDEN | polar-vast-forest (largeland section) |
| 6 | ARID_PALE_GARDEN, ORANGE_ARID_PALE_GARDEN, RED_ARID_PALE_GARDEN | constant mappings section |

**Important Note:** These biomes are still in the file because they serve dual purposes:
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
