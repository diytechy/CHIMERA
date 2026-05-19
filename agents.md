# Biome Distribution Balancing — Reference

This document captures what was learned while rebalancing biome surface percentages so that no standard land biome occurs more than ~10× more often than another. Read this before making large changes to the climate / biome-distribution pipeline.

## Pipeline (top to bottom)

The end-to-end mapping of (x, z) → final biome happens in stages under `biome-distribution/stages/`. The order matters: each stage rewrites tokens from prior stages.

```
Distribute_Major_Regions.yml     Carves special features from base 'land':
                                 SNOWY_PLAINS (cold plains), GLOOMY_GORGE,
                                 CARVING_CREAKS, vast-forest, mesa, far_river,
                                 _pillow_plains, _secluded_valleys, _desert,
                                 island, archipelago-zone.
                                 ▸ Each carve uses SELF:N + token:1.
                                   Bigger N = rarer feature.
fill_temperature_zones.yml       Sets _foliage_fortress / _patchwork etc.
spread_temperature_zones.yml
climate/temperature.yml          Partitions 'land' into 12 temperature bands
                                 (ice-cap … tropical-rainforest) by weight.
                                 ▸ Weights: 3,2,1,1,1,1,1,3,2,2,2,3 (total 22).
climate/precipitation.yml        Splits each temperature into 6 precip bands
                                 (desert … veryWet) per parent climate.
                                 ▸ Weights: 3,2,1,2,2,4 (total 14).
climate/elevation.yml            Splits each climate into flat/lowlands/highlands
                                 via segment(mountains, flatness, ...) — NOT
                                 by weight. See "Flatness gate" below.
set_biomes_in_climates_origen.yml  Final mapping: each climate sub-region
                                   resolves to actual BIOME ids by weighted list.
add_biome_color_variants.yml     Color expansions (maple-groves →
                                 MAPLE_GROVE/RED_MAPLE_GROVE/YELLOW_MAPLE_GROVE)
                                 and similar.
add_rivers.yml, add_coast.yml ...  Overlay rivers, coasts, islands, spots.
```

## Critical files

- `biome-distribution/stages/set_biomes_in_climates_origen.yml` — the big one. Every climate sub-region's biome menu lives here.
- `biome-distribution/stages/Distribute_Major_Regions.yml` — carving ratios for special placements. `SELF: N` means N out of N+1 stays as the parent.
- `biome-distribution/stages/climate/{temperature,precipitation,elevation}.yml` — climate partition weights.
- `customization.yml` — `flatness-*`, `forced-sealevel-*`, climate temperature/precipitation ranges, ocean thresholds.
- `math/samplers/{temperature,precipitation,elevation}.yml` — the underlying FBM/OpenSimplex noise samplers.
- `benchmark_CHIMERA.csv` — sampled biome surface counts. Run the benchmark, read this to evaluate.

## Flatness gate — the most important thing to understand

`climate/elevation.yml` does NOT partition by weight. The expression is:

```
if elevation > highlands → 1 (HIGHLANDS)
elif flatness < flatnessFactor → 0 (LOWLANDS)
else → -1 (FLAT)
```

`flatness` is the output of two `herp(...)` calls min'd together. Both herps interpolate from `flatness-factor` down to 0. So the `flatness` value is in `[0, flatness-factor]`. The condition `flatness >= flatness-factor` means **flatness must equal its own max**, which only happens when BOTH:

1. `rawFlatness ≤ flatness-percent` (or `forced-sealevel-activation-threshold` after the user renamed it)
2. `|mountainMask| ≤ mountainMaskFlat`

**This means `flatness-factor` does NOT control how much land is FLAT.** It controls how *aggressively* flat terrain is flattened. The actual FLAT share is controlled by `forced-sealevel-activation-threshold` (formerly `flatness-percent`) and the mountain mask threshold.

Raising the activation threshold from 0.26 → 0.31 expanded the FLAT zone from ~13% to ~25% of land and was the single biggest unblocker for the rare-biome floor.

## Sealevel-locked biomes (must remain flat-only)

These biomes use `BiomeShapeSealevelElevation` in their terrain equation, which clamps the surface to sea level. Placing them on slopes breaks the water surface, so they must only be assigned in `*-flat` climate lists. Audit list (verified via grep over `biomes/`):

| Biome | Equation |
|---|---|
| SWAMP, SCULK_SWAMP, MUSKEG | EQ_SWAMP |
| LAVENDER_FIELDS, FROSTCOATED_BOG | EQ_BOG |
| BLACK_DESERT_BOG | EQ_BARRIER_BOG |
| TROPICAL_FLOODPLAIN | EQ_MANGROVE_SWAMP |
| MURKY_MARSHLANDS | EQ_MURKY_MARSHLANDS |
| MARSH, FROZEN_MARSH | EQ_WARPED_WETLANDS (uses sealevel — confirmed by user edit) |
| ALIEN_MARSH | EQ_CELL_MARSH (uses sealevel — confirmed by user edit) |
| BAMBOO_BASIN | EQ_BAMBOO_BASIN |
| CARVING_CREAKS | EQ_CARVING_CREAKS (only placed via Distribute_Major_Regions, not in climate lists) |

To check: `grep -l BiomeShapeSealevelElevation biomes/` finds the relevant equation files.

## Non-sealevel biomes that *can* live in lowlands (don't restrict to flat)

Common ones that earned safe non-flat placements during balancing:
- SAKURA_GROVE (EQ_MULTI_TERRACED_LAND), SAKURA_STREAMS (EQ_SAKURA_STREAMS)
- FOSSILIZED_FENLANDS (uses `BiomeShapeFlattenedElevation`)
- VERDANT_VALLEYS (uses `BiomeShapeFlattenedElevation`)
- SNOWSWEPT_MEADOWS (EQ_PLAINS)
- ICE_SPIKES (EQ_SPIKES) — but thematically kept flat-only
- FROSTBOUND_CHASMS (EQ_CHASMS)
- WATERY_WILDS (EQ_LOWLAND_HILLS)

## Biomes with terrain equations that *demand* highlands

- FRIGID_WASTELANDS uses EQ_ALPHA_MOUNTAINS (scale=140, mountain noise). Belongs in `*-highlands`, not flat. Was originally in `tundra-flat` and dominated wrongly.

## Carved/special-placement biomes (don't add to climate lists)

These are placed directly by `Distribute_Major_Regions.yml` carvings. Adding them again in climate lists double-promotes them:

- GLOOMY_GORGE (1:19 carve where temp ∈ [-0.25, 0.4] & precip > 0)
- SNOWY_PLAINS (1:4 of cold plains)
- CARVING_CREAKS (1:9 where temp > 0.4 & precip < 0.5 & continents < 0.05)
- _pillow_plains, _secluded_valleys, _desert (from far_river_biome)

## The non-uniform noise distribution

`temperature` and `precipitation` come from `FBM(OPEN_SIMPLEX_2, octaves=2)`. The output is **not** uniform — it's quasi-Gaussian centered on 0.

Implications:
- Bands at the **edges** of the weight list (ice-cap, tropical-rainforest) capture **less than nominal** % of land — they sit in rare noise tails.
- Bands at the **center** (boreal-cold, temperate-cold, temperate-warm) capture **more than nominal**.
- The asymmetric existing weights (e.g., 3,2,1,2,2,4 in precipitation) partially compensate for this.

This means **don't blindly flatten climate weights** — it would crush the polar caps and rainforests while inflating the already-busy middle. Trim extreme weights conservatively (e.g., 4→3, not 4→2).

## Key levers in order of blast radius

1. **`forced-sealevel-activation-threshold`** (customization.yml) — controls FLAT zone share. Single biggest lever for lifting marsh/swamp/bog floor.
2. **`climate/temperature.yml` weights** — affects every biome in that temperature band.
3. **`climate/precipitation.yml` weights** — particularly `desertBorder: 2` exclusively feeds `temperate-steppe` and `cold-steppe`. Lowering to 1 cuts XERIC_SHRUBLAND, DRYBRUSH, COLD_STEPPE share.
4. **`Distribute_Major_Regions.yml` carve ratios** — `SELF: N` directly controls special-feature density.
5. **Intra-climate biome weights in `set_biomes_in_climates_origen.yml`** — finest-grained tuning. Single-biome 100% lists or weight-11 monopolies were the worst offenders.

## Patterns that produced runaway biomes (avoid these)

- **Massive weight in one climate.** TAIGA at weight 11 in `boreal-warm` (out of 26) was 42% of that climate alone. Capped at 3.
- **Sole occupancy.** Any climate with a single biome gives that biome 100% of the climate's tile budget. Watch this when removing diversity.
- **High fan-out across climates.** OAK_FOREST appeared in 6 temperate lists → 1.05% even with weight 1 in each. Trim list memberships, not just weights.
- **Wide-list dilution.** `temperate-cold-flat` once had 19 entries; each biome was ~5% per climate. Combined with sealevel-locked entries being unable to leave, this floored the marshes.
- **Adding to vast-forest indiscriminately.** Adding DARK_FOREST, BROADLEAF_FOREST, ENCHANTED_WOODLANDS to `temperate-vast-forest` or `boreal-vast-forest` compounds with their existing climate-list presences. ENCHANTED_WOODLANDS jumped from 0.09 to 1.25 from a single addition.

## "Flat-only sweep" strategy (what actually worked)

For each `*-flat` climate list **containing at least one sealevel-locked biome**:
1. Keep all sealevel biomes.
2. Remove all non-sealevel biomes that already exist in the corresponding non-flat (`*-{lowland}`) list.
3. For non-sealevel biomes not in non-flat, add them to non-flat AND remove from flat.
4. Skip carving-placed biomes (just remove from flat, don't re-add).

This concentrates flat zones on the biomes that *must* be there, dramatically lifting marsh/swamp/bog surface %.

Flat lists without sealevel biomes (like `ice-cap-flat`, `boreal-hot-flat`) serve a different purpose — leave them as variety pools.

## Common over-corrections to watch for

When stripping flat lists, sole-occupant outcomes can explode:
- MUSKEG as sole occupant of `tundra-flat` → 3–4% surface. If too high, add TUNDRA or FROSTBOUND_CHASMS back at weight 1.
- BAMBOO_BASIN as sole occupant of both `tropical-monsoon-flat` AND `tropical-savanna-wet-flat` simultaneously compounds. Consider splitting variety between them.
- TROPICAL_FLOODPLAIN sole in `tropical-rainforest-flat` — usually safe because the tropical-rainforest climate is small.

When moving biomes to non-flat midlands:
- Adding to too many non-flat lists compounds. ENCHANTED_WOODLANDS / BROADLEAF_FOREST / DARK_FOREST in vast-forest is the classic trap.
- Adding to a single non-flat list when the biome already has 4+ existing memberships will push it over 1%.

## Distribution journey (for context)

| State | Top % | Floor % | Ratio |
|---|---|---|---|
| Original | 2.15 (LAND_GLACIER) | 0.009 (VERDANT_VALLEYS) | 231× |
| After intra-climate weight caps | ~1.59 | ~0.03 | 53× |
| After flatness-percent change | ~1.48 | ~0.05 | 30× |
| After flat-list strip + ICE_CAPS migration | ~1.38 (MONSOON_FOREST) | ~0.07 (FROZEN_MARSH) | **~19×** |

## Reaching 5× (the unfinished goal)

To compress further, the remaining levers are:
1. **More flatness expansion** — `forced-sealevel-activation-threshold` 0.31 → ~0.42 lifts floor by ~50%.
2. **Variety injection into tropical-monsoon-flat/highlands** (currently thin 3-entry lists) — drops MONSOON_FOREST.
3. **Precipitation `desertBorder: 2 → 1`** — cuts XERIC_SHRUBLAND, DRYBRUSH, COLD_STEPPE by ~15%.
4. **Variety into `tropical-savanna-dry`** to dilute SAVANNA/GRASS_SAVANNA cluster.
5. **`tropical-rainforest` temperature weight 3 → 2** (only if shrinking the rainforest band visually is acceptable).

The structural ceiling at ~19× is dominated by **wide-coverage tropical and savanna biomes** (MONSOON_FOREST, GRASS_SAVANNA, SAVANNA, MOORLAND, CHAPARRAL, OVERGROWN_CLIFFS, LAND_GLACIER, TAIGA). At some point further compression risks visual homogeneity in those bands.

## How to benchmark

The benchmark CSV at `benchmark_CHIMERA.csv` is generated by running the project's benchmark script (the user invokes this manually — see ViewTable.bat or similar). Columns:
- `Surface Count`, `Surface %` — what the user-visible biome surface looks like.
- `Subsurface Count`, `Subsurface %` — cave/underground layers.
- `Overflow Samples` — usually mirrors Surface Count when overflow mechanism isn't engaged.
- `Avg Sampler µs` — performance signal (high values can indicate slow biome equations).
- `No Noise Props`, `Eval Errors` — should stay 0.

Important: sample counts vary by benchmark scale (smallest ~40M tiles, larger ~1B+). Tiny biomes with <1000 samples have high statistical noise; require larger benchmarks to compare meaningfully.

## When the user references "ai.md"

`CLAUDE.md` says to refer to `ai.md` for repo context. Check that file if present for project-specific conventions (terrain block palettes, biome naming, etc.).
