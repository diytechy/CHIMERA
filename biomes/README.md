# Biomes (Definition Reference)

This directory defines every biome in the pack — its terrain equation, palette, slant palettes,
features, river/ocean variants, and carving. **Where** biomes are placed is configured in
[`biome-distribution/`](../biome-distribution/); this directory defines **what each biome is**.

```
biomes/
  abstract/        Shared parameter bundles biomes `extends:` (terrain, environment, features, color)
  land/            Land biomes, grouped by climate/environment
  ocean/ river/    Aquatic biomes
  cave/substratum/ Substratum cave biomes
  rearth/          Origen ("rearth") dramatic-terrain biomes & equations
  spot/            Point-feature biomes (volcanoes, sinkholes, …)
  colors.yml       One color per biome (used by distribution & dev-tool visualisation)
  equations/       Reusable terrain `EQ_*` equations
```

Contents:

1. [Branch vs base legend](#branch-vs-base-legend)
2. [Anatomy of a biome config](#anatomy-of-a-biome-config)
3. [Abstract inheritance](#abstract-inheritance)
4. [Terrain equations & elevation constraints](#terrain-equations--elevation-constraints)
5. [Carving & cave biomes](#carving--cave-biomes)
6. [Screenshot placeholders](#screenshot-placeholders)

Legend (see [math/README.md](../math/README.md#branch-vs-base-legend)): 🟢 base / 🔶 fork.

---

## Branch vs base legend

The biome config schema (`extends`, `palette`, `slant`, `features`, `ocean`, `carving`) is
🟢 base Terra. CHIMERA / fork specifics:

- 🔶 `slant.calculation-method: DotProduct` is set pack-wide in `pack.yml` (base default is
  Derivative). This changes the meaning and sane range of slant thresholds — see below.
- 🔶 The special-cave equations (`rearth/base/eq_inferno_isle.yml`, etc.) and their carving
  rely on fork samplers (`special_caves`) and the `CarverFix` engine fix.
- 🔶 `carving.update-palette` behaviour for cave-floor topsoil (documented in agents.md).

---

## Anatomy of a biome config

```yaml
id: MONTANE_FOREST
type: BIOME
extends:                       # inherit shared parameter bundles (order matters — last wins)
  - COLOR_FROZEN
  - ENVIRONMENT_LAND_CONTINENTAL_SUBARCTIC
  - EQ_LAND                    # terrain equation
  - CARVING_LAND               # standard cave carver
  - BASE
color: $biomes/colors.yml:MONTANE_FOREST
tags:                          # used by distribution stages, river/coast assignment, caves
  - LAND_CAVES
  - SPECIAL_CAVES
  - USE_CHILLY_CREEK_RIVER
  - BOREAL_COAST_HIGHLANDS
vanilla: minecraft:grove       # vanilla biome for client-side effects
ocean:
  palette: FROZEN_OCEAN        # palette used where this biome meets ocean
palette:                       # surface column, top-down
  - GRASS_SNOW_MIX: $meta.yml:top-y
  - << meta.yml:palette-underwater
  - << meta.yml:palette-bottom
slant:                         # steep-slope palette overrides
  - threshold: 0.4             # DotProduct: fires where slant < 0.4 (steeper)
    palette:
      - BLOCK:minecraft:stone: $meta.yml:top-y
      - << meta.yml:palette-bottom
features:                      # features keyed by generation stage (see features/README.md)
  flora: [FERNS, GRASS]
  trees: [DENSE_FIR_TREE_PATCHES, SPARSE_SPRUCE_TREES]
  # ...
```

`colors.yml` is also the single best **inventory of every biome** in the pack.

---

## Abstract inheritance

Biomes `extends:` abstract configs in `biomes/abstract/` that bundle shared parameters
(terrain equation, environment/climate metadata, default feature sets, colors). Later entries
in the `extends:` list take precedence. To add behaviour (e.g. extra carving) to a variant
without disturbing a shared base, create a new `abstract: true` biome and place it **last** in
the `extends:` list — see
[agents.md → Abstract biome pattern for extending carving](../agents.md#abstract-biome-pattern-for-extending-carving). 🟢

A deeper explanation of the abstract layout is in `.scripts/ABSTRACT_BIOMES.md`.

---

## Terrain equations & elevation constraints

Terrain `EQ_*` equations (in `biomes/equations/` and `biomes/rearth/`) drive surface height as a
function of the pack samplers. Two placement constraints recur (full lists in agents.md):

- **Sealevel-locked biomes** use `BiomeShapeSealevelElevation` (swamps, bogs, marshes, …) and
  clamp their surface to sea level — they **must** only be assigned in `*-flat` climate lists,
  or the water surface breaks. 🟢/🔶
- **Highlands-demanding biomes** (e.g. `FRIGID_WASTELANDS` via `EQ_ALPHA_MOUNTAINS`) belong in
  `*-highlands`, never flat. 🟢

The sealevel-locked audit list and the non-sealevel biomes safe for lowlands are in
[agents.md → Sealevel-locked biomes](../agents.md#sealevel-locked-biomes-must-remain-flat-only).

**Slant thresholds (🔶 DotProduct):** since CHIMERA uses `DotProduct`, slant values are bounded
to `[-1, 1]` (flat = +1, vertical = 0) and the check is `slant < threshold` (steeper = lower).
Any threshold > 1.0 fires unconditionally. Sane steep-palette thresholds are `0.3–0.8`. Legacy
Derivative thresholds (2–15 range) must be converted — see
[agents.md → Slant calculation](../agents.md#slant-calculation-dotproduct-vs-derivative) and
`tools/slant_convert.py`.

---

## Carving & cave biomes

Cave biomes carve hollows via a `carving.sampler` (negative = solid, positive = void in this
pack). Key rules, all expanded in
[agents.md → Special Caves / Carving Reference](../agents.md#special-caves--carving-reference):

- 🔶 Use **carving, not terrain**, for hollows in extruded cave biomes (terrain blends across
  surface neighbours and gets diluted; carving does not blend).
- 🔶 Add `carving.update-palette: true` to a cave biome that needs topsoil at its floor (trees,
  flowers), otherwise the palette depth counter is well into stone.
- 🟢 Keep solid/air interpolation symmetric (`floor ≤ −cap`) to avoid solid bleed into air.

---

## Screenshot placeholders

Biome *terrain* shape is best illustrated by rendering its terrain equation (or the elevation
field) with the NoiseTool CLI. Placeholders until captured — see
[docs/CAPTURES.md](../docs/CAPTURES.md).

| What | Image |
|---|---|
| Elevation field driving land terrain | ![elevation](../docs/img/biomes/elevation.png) |
