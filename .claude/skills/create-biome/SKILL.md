---
name: create-biome
description: Author a new biome in the CHIMERA Terra pack (land, ocean, cave, river, or spot biome) — its terrain, palette, colors, climate, tags, features, and distribution placement. Use when the user wants to add a brand-new biome or a variant of an existing one (not a vanilla-mirror port — for that use port-vanilla-biome).
---

# Create a biome in CHIMERA

Goal: a new biome that has the right *shape* (terrain), *surface* (palette/colors), *spawns*
(`vanilla:`), *content* (features), and *where it appears* (distribution). Background:
[`biomes/README.md`](../../../biomes/README.md),
[`biome-distribution/README.md`](../../../biome-distribution/README.md). Terra engine ref:
`C:\Projects\Terra` — consult it when a key's meaning is unclear instead of guessing.
For mirroring a *vanilla* MC biome, use the **port-vanilla-biome** skill instead.

## 0. Start from the closest existing biome
Copy a sibling in the same family (`biomes/**`) and adapt. Most biomes are mostly `extends`.

## 1. The biome file
```yaml
id: MY_BIOME
type: BIOME
extends:
  - EQ_SOMETHING          # an abstract terrain base (biomes/abstract/terrain/**) = the SHAPE
  - ENVIRONMENT_LAND_...  # climate/environment mixin
  - CARVING_OCEAN|NONE    # cave carving
  - BASE                  # shared base (ores/deposits/etc.)
color: $biomes/colors.yml:MY_BIOME
vanilla: minecraft:<biome>   # drives mob spawns, music, fog, particles — pick the closest
colors: { water: 0x..., fog: 0x..., grass: 0x..., foliage: 0x... }   # optional overrides
climate: { precipitation: true, temperature: 0.8, downfall: 0.4 }    # optional
tags: [ USE_RIVER, LAND_CAVES, SPECIAL_CAVES, ... ]
palette:
  - SOME_PALETTE: $meta.yml:top-y
  - << meta.yml:palette-underwater
  - << meta.yml:palette-bottom
slant:                     # optional steeper-slope palettes
  - { threshold: 0.55, palette: [ ... ] }
features:
  trees:   [ ... ]
  flora:   [ ... ]
  postprocessors: [ ... ]
```
- **Terrain shape** comes from the `EQ_*` abstract you extend (it owns the `terrain:` /
  `ocean:` samplers). To reshape, extend a different `EQ_*` or make a new abstract; don't
  inline terrain in the concrete biome.
- **`vanilla:`** is REQUIRED for sane spawns/ambience — choose the nearest vanilla biome.
- **`extends` per-stage feature override:** stages merge per stage, later-parent-wins. If a
  parent already defines `trees:` and you set `trees:` here, you REPLACE it (often what you
  want for a barren/special biome; otherwise leave it and add features in another stage). To
  share dressing across hosts without clobbering, put it in a free stage (e.g. `processors`).

## 2. Palette (the visible surface blocks)
New look → new palette under `palettes/`. A palette is layered `materials:` (weighted block
lists) plus an optional `sampler` that selects across them by noise/position. For color
banding (e.g. terracotta strata, microbial mats) the sampler maps a value to a position in
the material list; `parabolicMap(t, bt,b, at,a)` plateaus output `a` for `t<=at`. See
[`palettes/README.md`](../../../palettes/README.md).

## 3. Colors
Add `MY_BIOME: 0xRRGGBB` to `biomes/colors.yml` (this is the BiomeTool/map color, distinct
from the in-game `colors:` block above). Cave biomes also need a substratum color entry.

## 4. Features
Reuse or author features (see the **create-feature** skill) and list their ids under the
right `features.<stage>`. Order matters when features depend on each other.

## 5. Place it in the distribution (or leave it unplaced)
Biome selection is a multi-stage pipeline in `biome-distribution/` (landmass → temperature →
precipitation → elevation → color → concrete biome in
`stages/set_biomes_in_climates_origen.yml`). To make a biome appear, add it (with a weight)
to the appropriate climate-cell list there / in the relevant extrusion. Mirror how a sibling
in the same climate is wired. Variety within a family = multiple siblings across the
temperature/precipitation/elevation/color axes (that's how deserts get white/red/orange/black
× flat/normal/highlands). It is fine to ship a biome **unplaced** and wire it later.

## 6. Validate
- YAML parses.
- `python .scripts/calculate_biome_percentages.py` resolves with no schema errors and the
  biome shows up (0% if intentionally unplaced is fine).
- Wiring only — the static predictor **over-reports spatially-gated biomes** and says nothing
  about appearance. Confirm look and real frequency in-world (`docs/CAPTURES.md`).
