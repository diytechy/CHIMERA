# CHIMERA Pack - 0% Unplaced Biomes Analysis & Integration Guide

## Overview
This document analyzes all **138 biomes** currently at 0% distribution in the CHIMERA pack and provides specific recommendations for how to integrate each into the pack.

**Total Biomes to Process: 138**

---

## Category 1: DO NOT PLACE - Generic Placeholder Biomes (29 biomes)

These are generic/placeholder biomes that serve as templates or fallbacks and should **NOT** be placed in the final configuration.

### Biomes:
- COAST_COLD_A, COAST_COLD_B, COAST_MEDIUM_A, COAST_MEDIUM_B, COAST_WARM_A, COAST_WARM_B
- LAND_COLD_A, LAND_COLD_B, LAND_MEDIUM_A, LAND_MEDIUM_B, LAND_WARM_A, LAND_WARM_B
- UNLINKED_archipelago-zone, UNLINKED_coast_small_warm, UNLINKED_frozen-archipelago-zone
- UNLINKED_hot-coast, UNLINKED_land-sea-border, UNLINKED_ocean_coast_wide
- UNLINKED_ocean_warm, UNLINKED_warm
- VARIANT_C, VARIANT_F, VARIANT_G, VARIANT_H
- COLD_ISLAND_SHALLOWS, FROZEN_ISLAND_SHALLOWS, ISLAND_SHALLOWS
- SUBTROPICAL_ISLAND_SHALLOWS, TROPICAL_ISLAND_SHALLOWS

**Action:** Skip these entirely - they are scaffolding/helper biomes used during development.

---

## Category 2: SPECIAL FEATURES - Incomplete/Special Terrain (7 biomes)

These biomes are part of special terrain generation features (crater lakes, sinkholes, volcanoes) that have not yet been fully implemented in CHIMERA:

### Biomes:
- BOREAL_CRATER_LAKE
- COLD_CRATER_LAKE
- COLD_DESERT_SINKHOLE, COLD_DESERT_SINKHOLE_BORDER
- DESERT_CRATER_LAKE
- TEMPERATE_CRATER_LAKE
- TROPICAL_CRATER_LAKE

**Action:** These should be addressed as part of completing special terrain features. They have dependencies in `set_biomes_in_climates_origen.yml` under spot biome categories. Once the parent feature is enabled, these will automatically be placed.

---

## Category 3: COASTAL BIOMES (19 biomes)

These should be integrated into coastal distribution, primarily through `fill_coasts.yml`:

### Temperature-Specific Beaches:
- **Cold:** SHALE_BEACH, FROZEN_BEACH, SNOWY_SEA_CAVES
- **Warm/Tropical:** PALM_BEACH, MUDDY_COASTS, TROPICAL_MUSHROOM_COAST, LUSH_SEA_CAVES
- **Rocky/Mixed:** ROCKY_SEA_CAVES, TERRACOTTA_SEA_CAVES

### Pale Garden Variants (coast):
- ARID_PALE_GARDEN_COAST
- ORANGE_ARID_PALE_GARDEN_COAST
- PALE_GARDEN_COAST
- POLAR_PALE_GARDEN_COAST
- RED_ARID_PALE_GARDEN_COAST
- POLAR_MUSHROOM_COAST

### Other:
- BEACH, SHRUB_BEACH, SNOWDRIFT_COASTS, MUSHROOM_COAST

**Action:** These require additions to `fill_coasts.yml` to be placed in appropriate temperature zones. Structure them similarly to existing entries:
```yaml
- type: REPLACE
  from: coast_small_cold
  to:
    SHALE_BEACH: X
    FROZEN_BEACH: Y
```

---

## Category 4: OCEANIC BIOMES (21 biomes)

These are deep ocean variants (trenches, vents, submarine features) that are **addressed later** in ocean biome distribution:

### Trenches:
- COLD_DEEP_DEPTHS_TRENCH, COLD_OCEAN_TRENCH
- CORAL_OCEAN_TRENCH, DEEP_DEPTHS_TRENCH, FROZEN_DEEP_DEPTHS_TRENCH, FROZEN_OCEAN_TRENCH
- OCEAN_TRENCH
- SUBTROPICAL_DEEP_DEPTHS_TRENCH, TROPICAL_DEEP_DEPTHS_TRENCH, TROPICAL_OCEAN_TRENCH

### Vents:
- COLD_DEEP_OCEAN_VENTS, DEEP_OCEAN_VENTS, FROZEN_DEEP_OCEAN_VENTS
- SUBTROPICAL_DEEP_OCEAN_VENTS, TROPICAL_DEEP_OCEAN_VENTS

### Subtropical Ocean:
- SUBTROPICAL_DEEP_DEPTHS, SUBTROPICAL_DEEP_OCEAN
- SUBTROPICAL_OCEAN, SUBTROPICAL_OCEAN_OVERHANGS, SUBTROPICAL_OCEAN_SLOPES

**Action:** These require updates to ocean biome distribution in `set_biomes_in_climates_origen.yml` under the "Ocean biomes (cellular)" section. Add entries to appropriate ocean depth/temperature categories.

---

## Category 5: RIVER-BORDERING BIOMES (34 biomes)

These biomes have river variants or depend on river placement. Many are **Hydraxia-based** (cold climate):

### Pale Garden River Variants:
- ARID_PALE_GARDEN_RIVER
- ORANGE_ARID_PALE_GARDEN_RIVER
- PALE_GARDEN_RIVER
- POLAR_PALE_GARDEN_RIVER
- RED_ARID_PALE_GARDEN_RIVER

### Hydraxia Woodlands/Mountain Biomes (all COLD):
- AUTUMNAL_WOODLANDS
- BIRCH_WOODLANDS
- DARK_OAK_WOODLANDS
- ENCHANTED_WOODLANDS
- ICEBOUND_JUNGLE
- MAPLE_WOODLANDS
- OAK_WOODLANDS
- REDWOOD_WOODLANDS
- SAKURA_WOODLANDS
- SPRUCE_WOODLANDS
- SUGAR_PINE_WOODLANDS

### Hydraxia Highland Biomes (all COLD):
- BITTER_HEIGHTS
- FIR_HIGHLANDS
- FRIGID_WASTELANDS
- LAVENDER_FIELDS
- PERMAFROST_CLIFFS
- SEARING_TORS

### River Features:
- BAD_BALCOONIES_RIVER
- CHILLY_CREEKS (cold river variant in mountain terrain)
- DRAFTY_STREAMS
- FROSTBITE_RIVERS
- MOUNTAIN_RIVER_FROZEN
- MUSKEG (swamp-like river biome)
- PLATEAO_RIVER_INNER, PLATEAO_RIVER_MIDDLE
- TRAVERTINE_TERRACES, TRAVERTINE_TERRACES_RIVER
- VERTICAL_JUNGLE_RIVER
- WINTRY_SEAS, WINTRY_WATERS (frozen river/coast features)
- FROSTY_FINGERS (special river-adjacent)

**Action for Hydraxia Biomes:** All Hydraxia-based woodlands and mountains should be placed in **COLD climates** in `set_biomes_in_climates_origen.yml`. Examples:
- boreal-snowy-flat/highlands
- boreal-cold-flat/highlands
- boreal-hot-dry-flat/highlands (for more temperate variants)

**Action for River Variants:** Create river variant entries in `set_biomes_in_climates_origen.yml` similar to existing patterns, or integrate as border biomes for existing river systems.

---

## Category 6: SUBSURFACE/CAVERN BIOMES (12 biomes)

These are extrusion/cavern biomes and are **NOT** for surface placement:

### Hydraxia Caverns (all COLD):
- ACACIA_CAVERNS
- AUTUMNAL_CAVERNS
- BIRCH_CAVERNS
- DARK_OAK_CAVERNS
- ENCHANTED_CAVERNS
- JUNGLE_CAVERNS
- MAPLE_CAVERNS
- OAK_CAVERNS
- SAKURA_CAVERNS

### Surface Caverns:
- MUSHROOM_CAVES
- RESIN_ROOTS
- FROSTBOUND_CHASMS

**Action:** These require separate subsurface/cavern distribution (likely already handled in a different configuration section). No action needed for surface biome placement.

---

## Category 7: SPECIALIZED BIOMES REQUIRING CLIMATE PLACEMENT (28 biomes)

These biomes need to be placed in specific climates in `set_biomes_in_climates_origen.yml`:

### COLD CLIMATE - Polar/Glacier Variants:
- POLAR_PALE_GARDEN (use in vast-forest categories)
- SINKHOLE_FOREST (temperate/forested sinkhole area)

### HOT/WARM CLIMATE - Pale Garden Variants (Arid):
- ARID_PALE_GARDEN
- ORANGE_ARID_PALE_GARDEN
- RED_ARID_PALE_GARDEN

*These pale garden biomes should likely be placed in special vast-forest categories similar to PALE_GARDEN placement, but in appropriate temperature zones.*

### Mushroom Biomes:
- MUSHROOM_FIELDS
- POLAR_MUSHROOM_COAST (Special feature for polar regions)
- PINE_BARRENS (coastal pine forest)

### Unknown/Special:
- YELLOWSTONE (likely a special feature biome)

**Action:** 
1. Pale Garden variants should be added to the vast-forest categories in `set_biomes_in_climates_origen.yml`:
   - tropical-vast-forest for ARID variants
   - polar-vast-forest for POLAR variants
   
2. Mushroom biomes may need special placement or involvement with large-feature systems

3. Review and place YELLOWSTONE as appropriate (appears to be a special environmental feature)

---

## Integration Priority & Strategy

### Phase 1: Immediate - Delete Generic Biomes (0 effort)
Skip all 29 biomes in Category 1 - they're not real biomes.

### Phase 2: Quick Wins - Address Coastal Biomes (1-2 hours)
1. Update `fill_coasts.yml` with new coastal biome weights
2. Organize by temperature: cold, medium, warm
3. Test coastal distribution

### Phase 3: Medium Priority - Integrate Hydraxia Biomes (2-4 hours)
1. Categorize Hydraxia woodlands/mountains by elevation (flat vs highland)
2. Add to `set_biomes_in_climates_origen.yml` in appropriate cold climate zones
3. Test distribution balance

### Phase 4: River Features - Add River Variants (1-2 hours)
1. Create river variant entries for palette variants
2. Integrate river-edge biomes into river systems
3. Test river placement

### Phase 5: Later - Ocean & Special Features
1. Ocean biomes: Add to ocean temperature/depth categories in `set_biomes_in_climates_origen.yml`
2. Special features: Revisit once crater lake/sinkhole systems are fully implemented
3. Pale Garden variants: Integrate into vast-forest placement

---

## Key Placement Rules

1. **Hydraxia Biomes are always COLD** - Verify BASE_HYDRAXIA in Extends field
2. **Elevation mapping:**
   - Elevation < 0.7 = FLAT region (e.g., -flat suffix)
   - Elevation >= 0.7 = HIGHLAND region (e.g., -highlands suffix)
3. **River biomes need special handling** - Check existing river biome patterns in CHIMERA
4. **Coastal biomes follow temperature stratification** - Use fill_coasts.yml for distribution
5. **Ocean trenches/vents are deep-ocean features** - Place in ocean depth categories, not surface

---

## Files to Modify

1. **`biome-distribution/stages/set_biomes_in_climates_origen.yml`**
   - Add Hydraxia biomes to appropriate cold climate sections
   - Add mushroom field biomes to vast-forest sections
   - Add ocean biome variants to ocean sections

2. **`biome-distribution/stages/fill_coasts.yml`**
   - Add new coastal biome variants with appropriate temperature weights

3. **`biome-distribution/stages/` (rivers)**
   - May need to create or update river-specific placement files for new river variants

---

## Summary Table

| Category | Count | Action | Priority |
|----------|-------|--------|----------|
| Generic Placeholders | 29 | Skip entirely | - |
| Special Features | 7 | Wait for feature impl. | Low |
| Coastal | 19 | Add to fill_coasts.yml | High |
| Oceanic | 21 | Add to ocean sections | Medium |
| River-Bordering | 34 | Integrate Hydraxia + variants | High |
| Subsurface | 12 | Already handled separately | - |
| Other/Specialized | 28 | Add to climate categories | Medium |
| **TOTAL** | **138** | | |
