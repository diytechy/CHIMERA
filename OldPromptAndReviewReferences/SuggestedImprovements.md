# Suggested Improvements

This document lists configuration issues found during the biome validation audit. These should be reviewed and addressed to ensure consistency across all biome definitions.

## Summary

| Issue Type | Count |
|------------|-------|
| YAML syntax errors | 4 |
| Missing valid color key | 24 |
| Color reference mismatch | 61 |
| **Total** | **89** |

---

## YAML Syntax Errors

These files contain YAML syntax errors that must be fixed:

| File | Error |
|------|-------|
| `./features/rearth/sharp_terraces.yml` | found duplicate anchor 'range'; first occurrence  |
| `./features/rearth/sharp_terraces_edge.yml` | found duplicate anchor 'range'; first occurrence  |
| `./palettes/rearth/ocean_brown_mix` | [Errno 2] No such file or directory: './palettes/rearth/ocean_brown_mix'  |
| `deep.yml` | [Errno 2] No such file or directory: 'deep.yml'  |

---

## Missing Valid Color Key

These biome files do not contain a valid color key (expected format: `color: $biomes/colors.yml:BIOME_ID`):

| File | Action Required |
|------|-----------------|
| `biomes/rearth/base/eq_canyon.yml` | Add color key |
| `biomes/rearth/base/eq_eroded_valley_mountains.yml` | Add color key |
| `biomes/rearth/base/eq_lowland_hillds.yml` | Add color key |
| `biomes/rearth/base/eq_mountain_spots.yml` | Add color key |
| `biomes/rearth/base/eq_pillars.yml` | Add color key |
| `biomes/rearth/base/eq_sinkhole.yml` | Add color key |
| `biomes/rearth/base/eq_terrace_mountain.yml` | Add color key |
| `biomes/rearth/base/eq_tilted_plateau.yml` | Add color key |
| `biomes/rearth/rivers/badlands_balconies_river.yml` | Add color key |
| `biomes/rearth/rivers/frozen_fungi_river.yml` | Add color key |
| `biomes/rearth/rivers/frozen_mountain_river.yml` | Add color key |
| `biomes/rearth/rivers/gloomy_gorge_river.yml` | Add color key |
| `biomes/rearth/rivers/highmountains_river.yml` | Add color key |
| `biomes/rearth/rivers/lush_loops_river.yml` | Add color key |
| `biomes/rearth/rivers/foliage_fortress_river_inner.yml` | Add color key |
| `biomes/rearth/rivers/foliage_fortress_river_middle.yml` | Add color key |
| `biomes/rearth/rivers/scarlet_sactuary_river.yml` | Add color key |
| `biomes/rearth/rivers/verdant_valley_river.yml` | Add color key |
| `biomes/rearth/rivers/vertical_frozen_vistas_river.yml` | Add color key |
| `biomes/rearth/rivers/vertical_jungle_vistas_river.yml` | Add color key |
| `biomes/rearth/rivers/vertical_vistas_river.yml` | Add color key |
| `biomes/rearth/variants/arid_arboretum.yml` | Add color key |
| `biomes/rearth/variants/frozen_arch_ocean.yml` | Add color key |
| `biomes/rearth/variants/rocky_refuge.yml` | Add color key |

---

## Color Reference Mismatches

These biome files have a color reference that does not match the biome ID:

| File | Biome ID | Current Color Reference |
|------|----------|------------------------|
| `biomes/rearth/debug/coast_cold_a.yml` | COAST_COLD_A | FROZEN_BEACH |
| `biomes/rearth/debug/coast_cold_b.yml` | COAST_COLD_B | FROZEN_BEACH |
| `biomes/rearth/debug/coast_medium_a.yml` | COAST_MEDIUM_A | BEACH |
| `biomes/rearth/debug/coast_medium_b.yml` | COAST_MEDIUM_B | BEACH |
| `biomes/rearth/debug/coast_warm_a.yml` | COAST_WARM_A | BEACH |
| `biomes/rearth/debug/coast_warm_b.yml` | COAST_WARM_B | BEACH |
| `biomes/rearth/debug/land_cold_a.yml` | LAND_COLD_A | SNOWY_TAIGA |
| `biomes/rearth/debug/land_cold_b.yml` | LAND_COLD_B | TAIGA |
| `biomes/rearth/debug/land_medium_a.yml` | LAND_MEDIUM_A | OAK_FOREST |
| `biomes/rearth/debug/land_medium_b.yml` | LAND_MEDIUM_B | FOREST_LOWLANDS |
| `biomes/rearth/debug/land_warm_a.yml` | LAND_WARM_A | SAVANNA |
| `biomes/rearth/debug/land_warm_b.yml` | LAND_WARM_B | OAK_SAVANNA |
| `biomes/rearth/debug/variant_c.yml` | VARIANT_C | TEMPERATE_GRASSLAND |
| `biomes/rearth/debug/variant_f.yml` | VARIANT_F | BEACH |
| `biomes/rearth/debug/variant_g.yml` | VARIANT_G | DARK_FOREST |
| `biomes/rearth/debug/variant_h.yml` | VARIANT_H | OAK_FOREST |
| `biomes/rearth/variants/abyssal_ocean.yml` | ABYSSAL_ALLEYS | DEEP_OCEAN |
| `biomes/rearth/variants/arch_oceans.yml` | STONEGATE_SEAS | SANDSTONE_ARCHIPELAGO |
| `biomes/rearth/variants/badlands_balconies.yml` | BADLANDS_BALCONIES | BADLANDS_BUTTES |
| `biomes/rearth/variants/bamboo_basin.yml` | BAMBOO_BASIN | EUCALYPTUS_FOREST |
| `biomes/rearth/variants/barren_tilted.yml` | BARE_BOULDERFIELDS | TEMPERATE_MOUNTAINS |
| `biomes/rearth/variants/black_forest.yml` | BLACK_FOREST | DARK_FOREST |
| `biomes/rearth/variants/canyon_arid.yml` | SANDY_SPLITS | JUNGLE |
| `biomes/rearth/variants/canyon_frozen.yml` | ICY_INCISIONS | FROZEN_ARCHIPELAGO |
| `biomes/rearth/variants/carving_creaks.yml` | CARVING_CREAKS | DESERT_MESA |
| `biomes/rearth/variants/cave_jungle.yml` | VINE_VAULT | DRIPSTONE_CAVES |
| `biomes/rearth/variants/dinosaurs.yml` | FOSSILIZED_FENLANDS | TEMPERATE_GRASSLAND |
| `biomes/rearth/variants/frosty_fingers.yml` | FROSTY_FINGERS | ICE_SPIKES |
| `biomes/rearth/variants/frozen_fungi.yml` | FROZEN_FUNGI | MUSHROOM_FIELDS |
| `biomes/rearth/variants/frozen_vistas.yml` | MOUNTAIN_MIRRORS | SNOWY_MOUNTAINS |
| `biomes/rearth/variants/gloomy_gorge.yml` | GLOOMY_GORGE | DARK_FOREST |
| `biomes/rearth/variants/high_mountains.yml` | ALPINE_ASCENDANCY | MOUNTAINS |
| `biomes/rearth/variants/inferno_isle.yml` | INFERNO_ISLES | DRIPSTONE_CAVES |
| `biomes/rearth/variants/jungle_vistas.yml` | CANOPY_CASCADES | OVERGROWN_CLIFFS |
| `biomes/rearth/variants/lush_loops.yml` | LUSH_LOOPS | OVERGROWN_CLIFFS |
| `biomes/rearth/variants/marine_monoliths.yml` | MARINE_MONOLITHS | BEACH |
| `biomes/rearth/variants/mesa_monuments.yml` | MESA_MONUMENTS | DESERT_MESA |
| `biomes/rearth/variants/murky_marshlands.yml` | MURKY_MARSHLANDS | SWAMP |
| `biomes/rearth/variants/oasis.yml` | OASIS | DESERT |
| `biomes/rearth/variants/pillow_plains_inner.yml` | PILLOW_PLAINS_INNER | SAKURA_GROVE |
| `biomes/rearth/variants/pillow_plains_middle.yml` | PILLOW_PLAINS_MIDDLE | SAKURA_GROVE |
| `biomes/rearth/variants/pillow_plains_outer.yml` | PILLOW_PLAINS_OUTER | SAKURA_GROVE |
| `biomes/rearth/variants/foliage_fortress_inner.yml` | FOLIAGE_FORTRESS_INNER | SAVANNA |
| `biomes/rearth/variants/foliage_fortress_middle.yml` | FOLIAGE_FORTRESS_MIDDLE | SAVANNA |
| `biomes/rearth/variants/foliage_fortress_outer.yml` | FOLIAGE_FORTRESS_OUTER | SAVANNA |
| `biomes/rearth/variants/redwood_forests.yml` | TALL_TIMBERLAND | SEQUOIA_FOREST |
| `biomes/rearth/variants/sakura_streams.yml` | SAKURA_STREAMS | SAKURA_GROVE |
| `biomes/rearth/variants/scarlet_sanctuary.yml` | SCARLET_SANCTUARY | BAMBOO_JUNGLE |
| `biomes/rearth/variants/secluded_valley.yml` | SECLUDED_VALLEY | SUNFLOWER_PRAIRIE |
| `biomes/rearth/variants/secluded_valley_outer.yml` | SECLUDED_VALLEY_OUTER | SUNFLOWER_PRAIRIE |
| `biomes/rearth/variants/sinkhole_forest.yml` | SINKHOLE_FOREST | FOREST_LOWLANDS |
| `biomes/rearth/variants/sinkhole_frozen.yml` | SINKHOLE_FROZEN | SNOWY_PLAINS |
| `biomes/rearth/variants/sinkhole_jungle.yml` | SINKHOLE_JUNGLE | OVERGROWN_CLIFFS |
| `biomes/rearth/variants/sinkhole_outer.yml` | SINKHOLE_OUTER | TEMPERATE_GRASSLAND |
| `biomes/rearth/variants/snowy_spires.yml` | SNOWY_SPIRES | FROZEN_ARCHIPELAGO |
| `biomes/rearth/variants/stone_savanna.yml` | WATERY_WILDS | SAVANNA |
| `biomes/rearth/variants/terracotta_tombs.yml` | TERRACOTTA_TOMBS | DRIPSTONE_CAVES |
| `biomes/rearth/variants/tundra_tracks.yml` | TUNDRA_TRACKS | SAVANNA |
| `biomes/rearth/variants/verdant_valleys.yml` | VERDANT_VALLEYS | TEMPERATE_GRASSLAND |
| `biomes/rearth/variants/vertical_vistas.yml` | VERTICAL_VISTAS | BAMBOO_JUNGLE |
| `biomes/rearth/variants/white_wallows.yml` | WHITE_WALLOWS | MUDDY_COASTS |

---

## Recommendations

### For YAML Syntax Errors
Fix the syntax errors in the listed files. Common issues include:
- Incorrect indentation (YAML uses spaces, not tabs)
- Missing colons after keys
- Unquoted special characters
- Duplicate keys

### For Missing Color Keys
Add a color definition to each biome file in the format:
```yaml
color: $biomes/colors.yml:BIOME_ID
```
And ensure the corresponding color is defined in `biomes/colors.yml`.

### For Color Reference Mismatches
Two options:
1. **Option A**: Update the color reference to match the biome ID and add the new color to `biomes/colors.yml`
2. **Option B**: If intentionally reusing another biome's color, this may be acceptable for map visualization

---

*Generated by check-biomes.sh*
