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

## EXPRESSION sampler scoping rules

What is callable depends on *where* in an EXPRESSION sampler the call appears.

| Caller context | Built-in math (`abs`, `floor`, `if`, …) | Own nested `functions:` | Sibling `functions:` | Pack-level functions | Local `samplers:` | Pack-level samplers |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Top-level `expression:` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Function body (`functions:` entry) | ✓ | ✓ (own nested only) | ✗ | ✗ | ✗ | ✗ |

**Functions are pure math.** A function body can only see built-in operators and whatever is explicitly declared in its own nested `functions:` block. It has no visibility into:
- sibling functions at the same level in the parent `functions:` block
- local samplers declared in the sampler's `samplers:` block
- pack-level samplers (e.g. `special_caves`, `caveWallOffset`)
- pack-level functions (e.g. `smoothstep`, `lerp`)

### Workarounds

**Function needs to call another function** — nest it:
```yaml
functions:
  outer:
    arguments: [x]
    expression: helper(x * 2)
    functions:          # helper declared INSIDE outer, not alongside it
      helper:
        arguments: [v]
        expression: v^2
```
This is why `lerp3` in `math/functions/interpolation.yml` re-declares `lerp` inside its own `functions:` block rather than calling the sibling.

**Function needs a sampler value** — evaluate at the outer expression level and pass as an argument:
```yaml
# platformShape top-level expression — local sampler IS visible here:
expression: |
  platformAt(h, y, platforms(x, z), special_caves(x, y, z))

functions:
  platformAt:
    arguments: [h, py, platVal, caveVal]   # sampler results arrive as plain numbers
    expression: |
      (-platVal - 0.25) * smoothstep(-0.3, -0.6, caveVal)
```
The top-level expression evaluates `platforms(x, z)` and `special_caves(x, y, z)` (both visible there) and forwards the scalar results as arguments. The function body sees only numbers — it never calls samplers directly.

### Pack-level function re-declaration

Adding a function to `pack.yml → functions:` makes it available in any top-level expression across the pack, but **not** automatically inside function bodies. If a function body needs `smoothstep`, declare it as a nested child:
```yaml
myFunc:
  arguments: [...]
  expression: smoothstep(0, 6, ...)
  functions:
    smoothstep:               # must be re-declared here; pack-level is not visible
      arguments: [edge0, edge1, x]
      expression: ...
```

## Interpolation mechanics (carving and terrain expressions)

**ChunkInterpolator builds a 5×5 sparse grid** (x,z ∈ {0,4,8,12,16}) and evaluates the 3D sampler once per 4 blocks in y. All per-block densities are trilinear interpolations of those sparse corner values.

**Consequence:** if one sparse point returns +2.75 (solid pillar) and the adjacent sparse point 4 blocks away returns −0.002 (barely air), every interpolated block between them has density ≈ +1.37 → solid. For a clean solid-to-air transition the empty-side sparse point must be at least as negative as the solid-side cap, so the midpoint crosses zero within one block.

**Rule of thumb:** `floor ≤ −cap`

For carving expressions (where negative = air, positive = solid):
- If the solid region caps at +2, the air region should floor at ≤ −2 to ensure interpolated midpoints can cross zero cleanly.
- Special cave carvers (EQ_INFERNO_ISLE, EQ_VINE_VAULT, EQ_TERRACOTTA_TOMBS) clamp their inner expression to **`[-0.6, +0.5]`** — matched to the standard carver range `[-0.54, +0.46]`. This is critical: if the special cave uses a wider range (e.g. ±2.5), a grid point at the interior void (+2.5) interpolated with an adjacent standard-cave solid (−0.54) yields midpoint **+0.98 → void bleed** into the shell. With `[-0.6, +0.5]`: midpoint(+0.5, −0.54) = −0.02 (barely solid ✓). The `×5.0` scale on `special_caves` and high `pillarScale` values are about the *raw inner expression* before clamping — they are unaffected.
- The rule **`floor ≤ −cap`** ensures clean zero crossings. With special cave cap +0.5, adjacent solid regions need floor ≤ −0.5; standard carver provides −0.54 ✓. Symmetric special cave boundaries (pillar −0.6 / void +0.5) have midpoint −0.05 → slight solid bias, preventing void bleed into narrow pillar/platform edges.

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

## Palette depth counter and carving (`carving.update-palette`)

The palette `paletteLevel` depth counter is built by scanning **top-down** from world max height. It tracks how many consecutive solid blocks have been seen below the last air gap — depth 0 = first solid block, depth 1 = next, etc. The counter is **reset to 0 on any air or water block**.

Carved blocks (terrain density > 0, carver > 0) behave differently depending on `carving.update-palette` (default: `false`):

| `carving.update-palette` | Carved block effect on `paletteLevel` | Cave floor depth |
|---|---|---|
| `false` (default) | **increments** (same as solid) | ≈ number of carved blocks above it |
| `true` | **resets to 0** | 0 (topmost palette layer) |

**Consequence for cave biomes:** With the default, a cave that is N blocks tall leaves `paletteLevel ≈ N` at the floor — well past topsoil and into stone. Features that locate on `plantable-blocks` (grass, dirt, moss) will find nothing and never place.

**Fix:** add `carving.update-palette: true` to any cave biome that needs topsoil at its floor (trees, flowers, dripleaf, etc.).

```yaml
# In the concrete biome YAML (e.g. vine_vault.yml):
carving:
  update-palette: true   # Reset depth counter on carved blocks → floor gets depth-0 palette layer
```

This is a biome-level palette setting (parsed by `BiomePaletteTemplate`), not part of `carving.sampler`. It can be added to a concrete biome even when the abstract parent defines `carving.sampler`.

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

---

# Special Caves / Carving Reference

This section documents what was learned while building and debugging the special cave system (`special_caves`, `eq_inferno_isle`, extrusions, platform carvers, connecting passages). Read this before touching anything in `biomes/rearth/base/eq_inferno_isle.yml`, `math/samplers/spots.yml`, or `biome-distribution/extrusions/add_special_caves.yml`.

## special_caves sampler — semantic and range

`special_caves(x, y, z)` (defined in `math/samplers/spots.yml`) returns:

| Location | Value |
|---|---|
| Cell center (xz), y=0 | −1 |
| xz shell at y=0 | 0 |
| Just outside the shell | small positive |
| Deep outside | large positive |

It is defined as `normalize_shell((R_xz² + R_y^p)^0.5 − 1, ...)` where the `normalize_shell` function scales the raw ellipsoidal distance so that a fixed threshold corresponds to the same **block depth** in every direction (not just at the xz equator).

`special_caveDist(x, y, z)` is the companion approximate **block-distance** to the shell:
- **positive** = inside the ellipsoid (distance to wall from inside)
- **0** = at the shell surface
- **negative** = outside the ellipsoid (distance to wall from outside)

Use `special_caves` to define the hollow boundary (correct ellipsoid shape). Use `special_caveDist` when you need a block-scale proximity measure (e.g., fade widths, connecting passage reach).

## Carving sign convention (CHIMERA pack)

```
carving sampler > 0  →  void (air)
carving sampler ≤ 0  →  solid (rock/terrain)
```

`EQ_CARVING_LAND` starts at `−carvingThreshold = −0.54`. Cave features add positive contributions. `EQ_INFERNO_ISLE`'s main carver is `max(−clamp(inner, −0.6, 0.5), carver_fade)` — the negation of the clamped inner expression means positive carving whenever `inner < 0` (inside the hollow). The clamp range is matched to the standard carver `[-0.54, +0.46]` to prevent interpolation bleed at biome boundaries (see interpolation mechanics section).

**Void threshold math for connection passages:** if the base carver sits at −0.54, a connection contribution of +X creates void where X > 0.54. Over a linear ramp of reach R blocks, the effective passage half-width is `(1 − 0.54) × R ≈ 0.46 × R`.

## Extrusion vs. carving — critical architecture difference

This distinction cost significant debugging time:

- **Terrain blending** (the `blend:` block in a biome) uses the **un-extruded surface biome** for ALL neighbour columns. `ChunkInterpolator.getBiome(cx+dx, cz+dz)` calls `getSurface()`, not `biomeColumn.get(y)`. Setting `blend.distance: 0` disables blending for the centre column but neighbors still use their un-extruded biomes. This means **terrain samplers of extruded biomes are heavily diluted (~2–5% weight) by surrounding surface biomes**, making terrain-based cave hollowing essentially impossible.

- **Carving does NOT blend.** `LazilyEvaluatedInterpolator.cachedSample()` calls `biomeProvider.getBiome(xi, y, zi, seed)` which returns the extruded biome directly. The special cave carver (from `EQ_INFERNO_ISLE`) therefore runs at full strength within the extrusion zone regardless of surrounding surface biomes.

**Rule:** Use carving (not terrain) for underground features in extruded biomes.

## LazilyEvaluatedInterpolator y-shift (Terra engine bug — fixed on branch `CarverFix`)

The original `LazilyEvaluatedInterpolator` had a top-down scan populating sparse-grid cells at the *first* y that visited them (top of cell), but the interpolation formula treated sample values as if they sat at the *bottom* of each cell. This shifted y-dependent carving down by `verticalRes − 1 = 3 blocks`.

**Symptom:** caves/features appear 3 blocks lower than the expression implies. A cave expected at y=[−30, 40] appears at y=[−33, 37].

**Fix (applied to `C:\Projects\Terra`, branch `CarverFix`):** renamed the private helper to `cachedSample` and pinned each cache cell to its canonical bottom-of-cell y:
```java
int y = Math.min(max, yIndex * verticalRes + min);
```
No extra evaluations — just ensures the correct y is passed to `carver.getSample`.

## Extrusion range must be wider than the carver's active zone

`add_special_caves.yml` places the INFERNO_ISLES (and other special cave) biomes via a SET extrusion over the range `[cave_lower, cave_upper]`. If this range is narrower than where the carver's expression goes non-trivial (e.g. `cave_lower − 4`), then at those boundary y levels the biome is the un-extruded surface biome and the **surface biome's carver runs instead** — producing wrong cave geometry or non-cave blocks leaking in.

**Rule:** extrusion range ≥ carver active range. Use `min: ${customization.yml:cave_lower}`, not a hardcoded literal.

## Paralithic smoothstep with inverted edges always returns 0

The expression engine implements:
```
smoothstep(edge0, edge1, x):
  if x <= edge0  →  0
  if x >= edge1  →  1
  else           →  smooth interpolation
```

**If `edge0 > edge1`** (e.g., `smoothstep(6, 3, diff)` to get a decreasing ramp), then for any `x ≤ edge0 = 6` the first branch fires and always returns 0. The interpolation body never executes.

**Fix:** to get a ramp that is 1 at `input=0` and 0 at `input=maxVal`, use:
```
1 - smoothstep(0, maxVal, input)
```
This uses a valid increasing smoothstep and inverts the result.

## Hard if-splits in carving expressions create discontinuities

**Symptom:** flat single-block-thick walls along the y-axis (or x/z axis), sharp horizontal "shelves" that appear and disappear consistently along a constant coordinate, "perfect" 4-block branches whose width and length match the carving grid step.

**Common cause: a hard `if(condition, branchA, branchB)` where branchA ≠ branchB at the boundary.** The two branches evaluate to different values right at the threshold, so density flips instantaneously across one block. The 4-block sparse interpolator then propagates that flip into a visible wall.

**Worked example (caveCarverFade y-split, fixed in `Fixed discontinuities after forever` commit):**

Original `caveCarverFade`:
```
if(y < 0,
  lerp(special_caves, 0, -0.5, act_dist, carver),       // lower hemisphere
  lerp(special_caves, act_thresh-0.1, 0, act_dist, carver))  // upper hemisphere
```

At `special_caves ≈ 0` (cave shell) when the *adjacent* land biome happens to have a standard cave passage there (`carver = +0.46`):
- Upper-hemisphere lerp: ≈ `0.75 × carver = +0.35` → passage bleeds through, void
- Lower-hemisphere lerp: `-0.5` (returns the `a` knot at `t = at`) → sealed, solid
- Jump at y=0: **0.85 in fade value** → outer `max(main, fade)` flips from void to solid → visible flat wall

The fade values dominated the `max()` only at this specific intersection — at most points the main carver expression won and the discontinuity was invisible. That's why it survived as a latent bug until a standard cave passage happened to align with a special cave shell.

**Fix:** replace the hard split with a smooth Hermite interpolation over a buffer band:
```
herp(y, -4, lower_branch, 4, upper_branch)
```
`herp` blends the two branches smoothly over `y ∈ [-4, 4]` (8-block window). Same expressions in both branches; only the *transition* is smoothed.

**Companion fix — align knot values across stages.** The upper-hemisphere lerp was also rewritten as `lerp3` with an extra knot at `act_full=-0.15` returning `-0.5`, so both branches agree at that special_caves value. This keeps the herp blend smooth at the cave interior (both branches see the same `-0.5` at `act_full`), with the transition zone reserved for the meaningful difference at the shell.

**Diagnostic order** when you see flat single-block walls in carving output:
1. **Check for hard if-splits first** — search the carver expression for `if(…)` branches and verify both sides produce *continuous* values across the condition boundary. This is the most common root cause of flat-wall artifacts and the cheapest to fix.
2. Check sparse-grid magnitude asymmetry (see "Interpolation mechanics" — value range mismatches between adjacent grid corners cause similar-looking spikes, but with a 4-block *length* rather than an axis-aligned plane).
3. Check that thresholds across coupled sub-expressions move together (e.g., pillar-existence threshold tied to fade `act_full` parameter rather than a duplicated literal — when one moves, the other stays in lock-step).

**Use shared customization parameters for tied thresholds.** When a pillar existence gate, a carver fade knot, and a biome boundary all need to land at the same `special_caves` value, give that value a name in `customization.yml` and reference it from every site. Drift between duplicated literals reintroduces exactly this class of discontinuity.

## Platform carver — CELLULAR return range matters

The `platforms` sub-sampler uses CELLULAR `Distance` (the default), which returns approximately **[−1, 0]** within a Voronoi cell (−1 at cell center, approaching 0 at edges). The expression `(−platforms − 0.25)` therefore evaluates to:
- **+0.75** at cell centers (negative of −1 minus 0.25)
- **−0.25** at cell edges

This creates solid platforms at cell centers (positive contribution overcomes the carver baseline) and slightly more void at cell edges. The **threshold for platform-creating cells** is where `−platforms − 0.25 > 0`, i.e., where `platforms < −0.25`.

## Domain-warp evaluation-point contamination

When a `DOMAIN_WARP` wraps an EXPRESSION that internally calls sub-samplers, **all sub-sampler calls inside the expression evaluate at the warped coordinates**, not the original (x,z). This is expected for cellular NoiseLookup samplers (which return a constant per-cell value anyway), but breaks for any sampler that evaluates **per-pixel regional functions** (e.g. FBM noise, river distance grids, or continental values).

**Concrete example (`rifts.yml`):**

Stage 2 of `build_rift_regions.yml` applies `DOMAIN_WARP(OS2, freq=0.002, amp=60)` to the pit-classification expression. That expression calls `cold_pit(x,z)` and `warm_pit(x,z)`, which previously checked `riftLandDistributor(x,z)>0` inside them. With a 60-block warp amplitude, the evaluation point can cross a `continentalRiverDistSparseFarGrid` or `continents` boundary — flipping `riftLandDistributor` from true to false (or vice versa) compared to the raw coordinates. This carves ragged notches in the pit boundary that are invisible on the surface (Stage 1 pre-filters with raw `riftLandDistributor`) but directly corrupt the underground cave-suppression boundary.

**The distinction:** all the other conditions in `cold_pit`/`warm_pit` — `riftContinents`, `riftFarRiverDist`, `riftTemperature`, `riftRegions` — are **rift-cell NoiseLookups**. They return the cell-center value for whichever rift cell contains the warped point; that value is constant across the whole cell, so warping only determines WHICH cell is queried, not the within-cell value. These warp cleanly. Per-pixel functions do not.

**Rule:** inside any expression that will be wrapped by DOMAIN_WARP, only use:
- Cellular NoiseLookup / CellValue samplers (constant within each cell)
- Constants / variables
- Expressions that themselves only use the above

Move per-pixel regional guards (river-distance, continents, elevation) **outside** the DOMAIN_WARP, evaluated at raw coordinates as a separate gate.

**Applied fix:** removed `riftLandDistributor(x,z)>0` from `cold_pit`, `warm_pit`, `cold_rift`, `warm_rift` in `rifts.yml`. Re-added it at raw coordinates as the outermost check in `add_special_caves.yml`'s cave-suppression expression. Stage 1 of `build_rift_regions.yml` (which already gates on raw `riftLandDistributor`) ensures the surface biome boundary is unchanged.

## Abstract biome pattern for extending carving

When adding extra carving to a biome variant that inherits CARVING_LAND through a base class:

1. Create a new `abstract: true` biome (e.g. `EQ_SINKHOLE_CAVE_CONNECT`).
2. Define `carving.sampler` that **includes the standard carver as a sub-sampler**:
   ```yaml
   samplers:
     carver: $biomes/equations/caverns/eq_carving_land.yml:carving.sampler
   expression: |
     carver(x, y, z) + extra_contribution(x, y, z)
   ```
3. Add the new abstract biome **last** in the variant's `extends:` list so it takes precedence over CARVING_LAND.

This avoids Terra's inheritance ambiguity when multiple parents define `carving` and ensures both carvers combine correctly.

---

# Feature Stage Blending Reference

This section documents how the `trees` and `flora` stage blend settings interact with biome boundaries, using VINE_VAULT / FUNGAL_UNDERGROWTH as the concrete case study.

## How stage blending works

`pack.yml` gives two stages a global Gaussian blend:

```yaml
- id: trees
  type: FEATURE
  blend:
    amplitude: 30          # features from neighbouring biomes bleed up to 30 blocks in
    sampler:
      type: GAUSSIAN
      salt: 2583

- id: flora
  type: FEATURE
  blend:
    amplitude: 30
    sampler:
      type: GAUSSIAN
      salt: 2934
```

Within a stage, Terra places the **home biome's features first** (in the order they appear in the biome's feature list), then the **blend layer from neighbouring biomes is written on top**. Blended features therefore "win" any block overlap with the home biome's features.

`landforms` and `preprocessors` have **no blend** — only `trees` and `flora` are affected.

## VINE_VAULT ← FUNGAL_UNDERGROWTH bleed (the mushroom case)

`FUNGAL_UNDERGROWTH` (`biomes/cave/substratum/fungal_undergrowth.yml`) is distributed as part of the `STANDARD_CAVES` pool (`add_cave_biomes.yml`) at the same underground depth range as VINE_VAULT's special-cave extrusion. The two biomes can therefore exist horizontally adjacent in the same y band.

`FUNGAL_UNDERGROWTH` puts two features in its **`trees` stage**:

| Feature | Distributor | Structure height |
|---|---|---|
| `GIANT_RED_MUSHROOMS` | `PADDED_GRID width:17 padding:6` | 20–30 blocks |
| `GIANT_BROWN_MUSHROOMS` | `PADDED_GRID width:9 padding:2` | 20–30 blocks |

Both features (`features/substratum/vegetation/mushrooms/giant_red_mushrooms.yml` / `giant_brown_mushrooms.yml`) use locators that require only:
- Air at offsets 0, 3, 5 (headroom)
- Solid at offsets −1, −3 (ground)
- Adjacent solid at −1

**No mycelium check.** VINE_VAULT's cave interior — large air void above a solid `GRASS_DENSE_MOSSY` floor (moss block, grass block, dirt) — satisfies all conditions. Within 30 blocks of the biome border the blend layer can place these 20–30-block mushroom stems inside VINE_VAULT.

Because blended features write after the home biome's features, wherever a blended `GIANT_RED/BROWN_MUSHROOM` overlaps a `VINE_VAULT_JUNGLE_TREES` jungle tree, the mushroom blocks overwrite the jungle-tree blocks.

## Identifying blend-injection candidates for any biome

1. Find all biomes that can appear in the same y range (check `add_cave_biomes.yml` and `add_special_caves.yml` range fields).
2. Check each neighbour's **`trees`** and **`flora`** feature lists.
3. For each neighbour feature, read its locator: if it only guards on air/solid (not a specific block type like mycelium), it can trigger on any sufficiently open surface — including the target biome's cave floor.

## Suppressing unwanted blend-injected features

**Option A — exclude the biome from the trees-stage blend entirely:**
Add a tag (e.g. `NO_BLEND_TREES`) to VINE_VAULT and add it to a `no-blend-tags` list under the `trees` stage in `pack.yml` (Terra supports this via the stage config).

**Option B — guard the source feature's locator:**
Add a `MATCH_SET` check to `GIANT_RED_MUSHROOMS` / `GIANT_BROWN_MUSHROOMS` that requires a FUNGAL_UNDERGROWTH-specific block (e.g. `coarse_dirt`, `rooted_dirt`, or `brown_concrete_powder`) at offset −1. This stops them firing on VINE_VAULT's moss/grass floor even when blended.

**Option C — add a competing trees feature to VINE_VAULT:**
A high-density `PADDED_GRID` feature that places a passable block (air, or a decorative block) can saturate the grid slots and prevent the blended mushroom feature from finding valid distributor positions — though this is fragile and not recommended.

## Repository Overview

This project contains a Terra world configuration, which is packaged into a zip folder to be available to the Terra plugin for minecraft.  This plugin is used for world generation and contains various functions and expressions to create detailed terrain as a function of a world seed and x,y,z coordinates.  These configurations are used to define various parameters that control how this world generation occurs.

This world is templated for the most recent Terra version 7.0 build (https://github.com/PolyhedralDev/Terra).  Older documentation related to configuration development can be referenced from https://terra.polydev.org/config/development/index.html

The core "build" for this repository is intended to be a batch script ".scripts/AuditAndPackage.bat" which is described further below.

## Architecture

### Key Directories

- `../Terra`: If available, this should contain the source code for Terra.
- `biomes/`: Refer to README.md in this directory.
- `biome-distribution/`: Refer to README.md in this directory.
- `features/`: Refer to README.md in this directory.
- `math/`: Refer to README.md in this directory.
- `palettes/`: Refer to README.md in this directory.
- `structures/`: Refer to README.md in this directory.
- `.scripts/`: Includes various files that perform different checks.

### Key Files

- `.scripts/AuditAndPackage.bat`: The main build script for Windows environment. The script performs three key steps:
  1. **Make the package** - Creates `.artifacts/ORIGEN2.zip` (via pack.sh or PowerShell fallback)
  2. **Create the biome table** - Generates `.artifacts/BiomeTable.csv` with distribution percentages (via `.scripts/calculate_biome_percentages.py`). The script also copies or creates `SuggestedImprovements.md` in `.artifacts/`.
  3. **Audit the yml files** - YAML linting and validation (via check-biomes.sh if WSL available)
  4. **Pack configurations and implications of sampler / function / expression definition** -Definitions around key processing information and potential optomizations can be found in 'sampler-optimization-reference.md'
  

The batch file intelligently adapts to available tools:
- **Python** is required for BiomeTable.csv generation
- **WSL** is optional (used for packaging and YAML validation)
- **PowerShell** is used as fallback for packaging if WSL unavailable

See `.scripts/WORKFLOW_DOCUMENTATION.md` for complete details.

- `pack.yml`: The main definition file that tells the Terra plugin how to generate the world. The primary biome configuration is specified in the "biomes:" key.

- `.scripts/calculate_biome_percentages.py`: Python script that generates BiomeTable.csv by analyzing biome distribution pipelines and calculating exact percentages for each preset.

- `.scripts/check-biomes.sh`: Bash script that validates YAML syntax and checks color key consistency across biome files. Generates `SuggestedImprovements.md`.

- `.artifacts/BiomeTable.csv`: A comprehensive table listing all biomes and their distribution across presets. Includes new columns derived from biome files: `Extends`, `VanillaID`, `LAND_CAVES`, `SPECIAL_CAVES`, `CAVERNS_LAND`, and `River`.

**Table Structure**:

The table includes the following columns:

- **BiomeID**: The unique identifier from the biome file's `id:` field
- **Extends**: The parent biome(s) this biome inherits from (from `extends:` key)
- **Color**: The color reference (from `color:` key, typically `$biomes/colors.yml:BIOME_ID`)
- **Preset Columns**: One column per preset (default, origen2, rearth, single, single_debug) showing the **exact percentage** that biome appears in that preset's distribution

**Important**: The table now shows **percentages** (e.g., "4.6875%") instead of Y/N flags, providing accurate distribution data.

**Coverage**: The table includes ALL valid (non-abstract) biomes, even those with 0.0000% across all presets, providing a complete inventory of available biomes.

## Important Notes

- **NEVER** edit any of yaml configuration files directly before building the package file, only edit them after as suggested changes so they can be reviewed and confirmed before being rolled into a package.

### Development Workflow


### Testing


### Code Style

### Implement & Refine
 
   * Write clean, idiomatic TypeScript (or other requested language) with inline comments and clear variable names.
   * Adhere to best practices around modularity, error handling, and security.
 
### Document & Explain
 
   * Provide concise, step‑by‑step instructions for any setup or deployment.
   * Embed helpful comments and docstrings.
   * When introducing new concepts (e.g. a Terraform provider), include a 1–2 sentence definition.

### Style & Format Guidelines
 
* **Clarity First**: Short sentences, minimal jargon, **bold** key commands or config snippets.
* **Step‑by‑Step**: Use numbered lists. Each step must be a standalone action.
* **Code Blocks**: Wrap code in fenced blocks with language tags.
* **Ask Before You Leap**: If any assumption is unclear (e.g. target Node version, cloud region), request clarification.
* **Encouraging Tone**: Be supportive, forward‑thinking, and sprinkle in quick, clever humor (e.g., “Let’s squash this bug like it owes us money!”).
* **Accessibility**: Offer extra background for beginners, but clearly label “Advanced Tips” sections for experts.