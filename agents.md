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

---

# Sampler / Noise Reference

This section documents what was learned about Terra VIBE's sampler system through source-code analysis (Terra at `C:\Projects\Terra`, seismic library bytecode). Use this before debugging "why isn't this noise producing the value I expect" questions.

## Default frequency and the FBM trap

**All `NoiseFunction` samplers default to `frequency: 0.02`** (period 50 blocks, patches ~25 blocks). Defined in `NoiseTemplate.java:22`.

**FBM's `frequency:` field is dead code.** `BrownianMotionTemplate.get()` constructs the sampler without ever using the inherited `frequency` field. The effective spatial scale of an FBM is entirely determined by the INNER `sampler:` leaf node's frequency. Writing `frequency: 0.1` on an FBM block is silently ignored — set frequency on the inner OPEN_SIMPLEX_2 (or whatever leaf) instead.

## Output ranges by sampler type

| Type | Output range | Notes |
|---|---|---|
| `OPEN_SIMPLEX_2` | `[-1, 1]` | Symmetric, roughly Gaussian-centered on 0 |
| `OPEN_SIMPLEX_2S` | `[-1, 1]` | Smoother variant |
| `CELLULAR` `return: Distance` (default) | `[-1, (√2-1)/2 ≈ 0.207]` | Distance from cell center, normalized to cell width. `-1` at center, `0.207` at corner edge. |
| `CELLULAR` `return: CellValue` | `[-1, 1]` | Per-cell random constant |
| `CELLULAR` `return: Distance2Div` | `[1, ∞)` | Ratio dist2/dist1, always ≥ 1 |
| `CELLULAR` `return: NoiseLookup` | (range of `lookup:` sampler) | Lookup sampler evaluated at cell-center coords → per-cell constant |
| `FBM` (3 octaves, gain 0.5) | `[-1, 1]` | Normalized via `fractalBounding = 1/Σ amplitudes`. Confirmed from bytecode. |
| `CONSTANT` | the configured `value:` | Spatially uniform |
| `EXPRESSION` | whatever the expression produces | No automatic normalization |
| `LINEAR` (LinearNormalizer) | `[-1, 1]` | Maps inner sampler's `[min, max]` → `[-1, 1]` via `(input − min)·2/(max − min) − 1`. **Inner sampler values outside `[min, max]` are NOT clamped** — they extrapolate. |

## How warps affect (or don't affect) sampler distribution

**DOMAIN_WARP does NOT change the output range or distribution shape of the inner sampler.** It only changes WHERE the inner sampler is evaluated:

```
DOMAIN_WARP.getSample(x, z) = inner_sampler.getSample(x + warp(x,z)*amplitude, z + warp(x,z)*amplitude)
```

So if the inner `sampler:` is FBM (range `[-1, 1]`), the warped output is still in `[-1, 1]` — just sampled at a displaced coordinate. The warp value range (after `LinearNormalizer` if used) times `amplitude` gives the **displacement** in blocks, not the output range.

**Calibrating LinearNormalizer warps to CELLULAR return types** — the common pattern:

```yaml
warp:
  type: LINEAR
  min: -1
  max: 0.2          # matches CELLULAR Distance max of (√2-1)/2 ≈ 0.207
  sampler:
    type: CELLULAR  # default return: Distance, range [-1, 0.207]
    frequency: 0.08
```

This is correctly calibrated. If you change the inner CELLULAR to `return: CellValue` (range `[-1, 1]`) without updating `max`, the LinearNormalizer extrapolates past `+1` for CellValue > 0.2, producing extra-large positive warps. Conversely, `LinearNormalizer(min=-1, max=0.2)` over CELLULAR Distance (default) correctly maps to `[-1, +1]` for symmetric bidirectional warping.

**Heuristic for diagnosing warp issues:** compute `LinearNorm(inner_sampler.min)` and `LinearNorm(inner_sampler.max)` and confirm both endpoints land near `±1`. If both are positive (or both negative), the warp is unidirectional.

**DOMAIN_WARP on a CONSTANT inner sampler is a no-op.** `CONSTANT` returns the same value regardless of input coordinates, so the warp has no effect. This pattern shows up as a debug placeholder — e.g., `eq_stratified_land.yml`'s heightmap has `sampler: {type: CONSTANT, value: 1}` with the real `elevation(x, z)` commented out.

## PALETTE material selection

The top-level `sampler:` in a PALETTE selects materials within each layer's weighted `materials:` list. Behavior (from `ProbabilityCollection.java:54` + `NormalizationFunctions` bytecode):

1. The `materials:` weights expand into an array. `[dirt:3, sand:2]` becomes `[dirt, dirt, dirt, sand, sand]` (length 5).
2. The sampler is called: `value = sampler.getSample(seed, x, y, z)`.
3. Index is computed: `index = clamp(floor((value + 1) / 2 * length), 0, length − 1)`.

**This hard-assumes the sampler output is in `[-1, +1]`.** Values outside this range clamp to the first (`< -1`) or last (`> +1`) material in the expanded array — order in the YAML matters for clamping behavior.

**Per-layer `sampler:`** overrides the top-level default for that specific layer (`PaletteImpl.java:33`).

For `[dirt:3, sand:2]`, the dirt/sand boundary is at sampler value `0.2`:
- `value < 0.2` → dirt (60% of [-1, 1] range)
- `value ≥ 0.2` → sand (40% of [-1, 1] range)

If a palette appears to never produce a particular material despite being listed:
1. Check the sampler's effective output distribution (range × symmetry).
2. Remember that **a 2D sampler returns the same value for all Y at a given (x, z)** — material patches are vertical columns, so a "sand patch" XZ never produces dirt at any depth.
3. Patches are ~25 blocks at default `frequency: 0.02` — small test areas may sit entirely inside one patch.

## Slant calculation (DotProduct vs Derivative)

CHIMERA uses `calculation-method: DotProduct` (set in `pack.yml`). Terra supports two methods (defined in `SlantCalculationMethod.java`):

| | DotProduct | Derivative |
|---|---|---|
| Returns | Y-component of normalized surface normal = `cos(θ)` | Magnitude of density gradient ≈ `2/cos(θ)` for 2D heightmap terrain |
| Range | `[-1, +1]` (flat = +1, vertical = 0, overhang = -1) | `[2, ∞)` (flat = 2, unbounded as θ → 90°) |
| Trigger | `slant < threshold` (steeper = lower) | `slant > threshold` (steeper = higher) |
| Multi-tier selection | `ceilingEntry(slant)` — smallest threshold ≥ slant | `floorEntry(slant)` — largest threshold ≤ slant |
| `floorToThreshold()` | `false` | `true` |

**Consequences for thresholds:**
- DotProduct values are bounded — **any threshold > 1.0 always fires** because `slant ≤ 1.0 < threshold` is unconditionally true.
- For `[stone:1, ice:1]`-style steep palettes, sane DotProduct thresholds are `0.3 – 0.8`.
- `slant-depth: N` is a **palette layer count limit** (how many blocks deep from surface the slant check applies), NOT a value scaler. `slant-depth: 15` doesn't make thresholds 15× larger.

## Converting legacy Derivative thresholds to DotProduct

Two formulas, derived in `tools/slant_convert.py`:

**Theoretical (smooth 2D heightmap terrain):** `DotProduct = 2 / Derivative`

**Empirical curve fit** (matches TerraOverworldConfig's Aug 2022 bulk conversion, anchored at `2→0.6, 4→0.4, 8→0.2, 16→0`):

```
new = 0.8 − 0.2 · log₂(old)
```

| Old (Derivative) | New (DotProduct) |
|---|---|
| 2 | 0.60 |
| 2.5 | 0.54 |
| 2.7 | 0.51 |
| 3 | 0.48 |
| 3.5 | 0.44 |
| 4 | 0.40 |
| 5 | 0.34 |
| 6 | 0.28 |
| 7 | 0.24 |

The empirical curve was the right choice for the Hydraxia biomes — the theoretical `2/x` formula gives more permissive thresholds than what the pack visually calibrated to under FBM terrain with high-frequency surface variation.

## Historical context — why Hydraxia thresholds were broken

Pre-Nov 2022: only Derivative method existed; thresholds were authored in the 2–15 range. Aug 2022: TerraOverworldConfig rebalanced everything to 0.05–0.55 (Terra issue #358). **Hydraxia biomes were missed in that pass.** Nov 2022: Terra added DotProduct enum. Dec 2022: CHIMERA's pack.yml switched to DotProduct. Since DotProduct outputs ≤ 1.0, the un-rebalanced Hydraxia values (3–7 range) became always-fire constants, producing constant ice/stone palette everywhere.

## Terrace functions (math/functions/terrace.yml)

`terraceStrata(i, sc, o, g, d)` and friends are step-function shapers. The general form:

```
terrace*(i, sc, o, g, d) = d · sc · profile(clamp(floorMod(i/sc − o, 1+g))) + i
```

Per-variant profile shapes:

| Function | Profile expression | Profile range | Effect on input `i` |
|---|---|---|---|
| `terrace` | `\|x − 0.5\| − 0.5` | `[-0.5, 0]` | Subtracts up to `0.5 · d · sc` |
| `terraceStrata` | `-if(x>0.95, -(x-1)/0.05, x/0.95)` | `[-1, 0]` | Subtracts up to `d · sc` |
| `terraceParabolic` | `(x−0.5)² − 0.25` | `[-0.25, 0]` | Subtracts up to `0.25 · d · sc` |
| `terraceParalinear` | piecewise | `[-0.5, 0]` | Subtracts up to `0.5 · d · sc` |

**All terrace variants strictly subtract from `i` (or leave it unchanged) — they never add height.** Maximum output equals input; minimum is `input − (profile_min · d · sc)`.

Chained terraces compound subtractions:
```
terraceStrata(terraceStrata(terraceStrata(H, 50, 0, 0, 0.1), 30, 0, 0, 0.15), 15, 0, 0, 0.2)
```
Envelope: `[H − 12.5, H]` (subtractions are 5 + 4.5 + 3).

## Interpolation mechanics (carving and terrain expressions)

**ChunkInterpolator builds a 5×5 sparse grid** (x,z ∈ {0,4,8,12,16}) and evaluates the 3D sampler once per 4 blocks in y. All per-block densities are trilinear interpolations of those sparse corner values.

**Consequence:** if one sparse point returns +2.75 (solid pillar) and the adjacent sparse point 4 blocks away returns −0.002 (barely air), every interpolated block between them has density ≈ +1.37 → solid. For a clean solid-to-air transition the empty-side sparse point must be at least as negative as the solid-side cap, so the midpoint crosses zero within one block.

**Rule of thumb:** `floor ≤ −cap`

For carving expressions (where negative = air, positive = solid):
- If the solid region caps at +2, the air region should floor at ≤ −2 to ensure interpolated midpoints can cross zero cleanly.
- Clamping carving expressions to `[-1.75, 1.75]` (as in `eq_inferno_isle.yml`) provides a safe interpolation envelope for most cavity/platform features.
- Platforms or solid features that exceed +2 require correspondingly deeper negative floors (≤ −2) in adjacent air regions to prevent interpolation artifacts.

**Debugging interpolation bleed:**
1. Check the sparse-grid values at feature boundaries (every 4th block).
2. If solid features appear where they shouldn't, the adjacent "air" sparse point is likely too close to zero (e.g., −0.1 instead of −2).
3. Increase the magnitude of the negative floor in the air region to match the positive cap in the solid region.

**Flat-boundary staircase (high y-exponents)**

High y-exponents (y^4, y^6) in an ellipsoid shape function create a nearly flat top and bottom boundary. On the 4-block sparse grid, a flat horizontal boundary means many adjacent xz cells share the same ceiling y-level → visible staircase of discrete 4-block shelves.

Adding density noise (e.g. `wallOffset * 1.2`) does **not** fix this. Density noise shifts the boundary in value-space: it moves the entire ceiling up or down by a slow-varying amount per region, not per interpolation cell. Only coordinate-space variation breaks the staircase.

**Fix: warp y with a 2D sampler before calling the shape function**

```yaml
# In the expression:
(special_caves(x, y + ceilWarp(x, z) * 6, z) + bias) * scale

# ceilWarp sampler — must be 2D, not 3D:
ceilWarp:
  dimensions: 2          # 2D = consistent vertical offset per xz column
  type: FBM
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.018     # ~56-block period; 3–4 cycles across a 200-block cave
  octaves: 2
  gain: 0.5
```

This displaces where the ellipsoid boundary sits at each xz position, so adjacent grid cells see the ceiling at different heights. Amplitude of 6 blocks gives ~12 blocks of ceiling variation (3× the grid step), which dissolves the staircase into organic curves without distorting the cave shape significantly.

**Why 2D, not 3D:** A 3D warp sampler varies with y, so the offset changes at each block within the same column. This creates mid-column density discontinuities (the same xz position evaluates the shape at different effective y-levels at different block heights). A 2D sampler gives a single constant offset for the whole column — correct for shifting the boundary location.

## Quick diagnostic checklist

When a palette/sampler doesn't behave as expected:

1. **Is the output range what `normalizeIndex` expects?** It hard-assumes `[-1, +1]`. Values outside clamp to first/last material.
2. **Is the FBM `frequency:` set on the leaf, not the FBM?** The FBM-level `frequency:` is silently ignored.
3. **Is the LinearNormalizer's `[min, max]` calibrated to the inner sampler's actual range?** A mismatch produces unidirectional warps or out-of-range extrapolation.
4. **Is the CELLULAR `return:` what you assumed?** Default is `Distance` (`[-1, 0.207]`), not `CellValue` (`[-1, 1]`).
5. **Is the inner sampler a CONSTANT?** DOMAIN_WARP around a CONSTANT is a no-op — usually a debug leftover.
6. **For palettes: is the sampler 2D?** 2D samplers give the same value across all Y at one (x, z), creating vertical-column patches not per-block randomness.
7. **For slant: is the threshold below 1.0?** With DotProduct, anything > 1.0 always fires.
8. **For carving/terrain: are the floor and cap symmetric?** Interpolation requires `floor ≤ −cap` to prevent solid bleed into air regions.
