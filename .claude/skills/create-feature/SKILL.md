---
name: create-feature
description: Author a new Terra FEATURE (and its structure/distributor/locator) in the CHIMERA pack — i.e. decide WHERE and HOW something generates (boulders, vents, flora patches, lakes, decorations). Use when the user wants to add or change a feature, scatter/place blocks or structures, or tune how often/where something spawns.
---

# Create a feature in CHIMERA

A **feature** answers *where* and *how often* a thing generates and *what* gets placed.
It is three parts: a **distributor** (selects XZ columns / rarity), a **locator** (selects
the Y and the block context within a chosen column), and **structures** (what to place).
Background: [`features/README.md`](../../../features/README.md),
[`structures/README.md`](../../../structures/README.md). Terra reference:
`C:\Projects\Terra` (engine) — consult it when a config key's behavior is unclear rather
than guessing.

## 0. Before writing: copy a working sibling
Find an existing feature that does something similar (`features/**`) and start from it.
The gotchas below are the ones that have repeatedly cost iteration here.

## 1. Distributor — selects which XZ columns (and how dense)
- **SAMPLER** — places where the sampler value is **< threshold** (NOT `>`). So a *smaller*
  threshold = *sparser*. This is the single most common mistake.
  - To gate to a region with an EXPRESSION sampler, return the rarity noise **in-band** and
    a constant **`1` out-of-band** (1 is never `< threshold`, so out-of-band never places).
    Using `-1` as the out-of-band sentinel places EVERYWHERE outside the band (the classic
    "inverted distribution" bug). `threshold` is then the in-band density fraction.
  - For an even per-column spread matching a vanilla `count:N + in_square`, use a
    `POSITIVE_WHITE_NOISE` SAMPLER with `threshold ≈ N/256`.
- **PADDED_GRID** (`width`, `padding`, `salt`) — ~one candidate per `width+padding` cell:
  **clusters/spaces things out**. Good for boulders, geysers, structures; bad for an even
  field (it leaves grid gaps). Use it for "sparse, spaced".
- **AND` / `OR`** of distributors — e.g. `PADDED_GRID` AND a `POSITIVE_WHITE_NOISE` SAMPLER
  gives spaced-out *and* irregularly thinned placement ("sparse periodic").
- **RANDOM** (`amount` = tries per chunk), **PROBABILITY**, **YES** (every column; rely on
  the locator to restrict).

## 2. Locator — selects the Y and the block context
Set `range: { min, max }` (use `${meta.yml:ocean-level}`, `$meta.yml:top-y`, etc.). Then:
- **SURFACE** / **TOP** — the surface/top solid column position.
- **PATTERN** — `MATCH` (exact block), `MATCH_SET` (any of a block list), `MATCH_AIR`,
  `MATCH_SOLID`, `NOT`, `AND`, `OR`, each with an `offset` (blocks relative to the located
  Y). e.g. floor = `MATCH_SOLID offset:0` AND `MATCH_AIR offset:1`; submerged floor =
  solid@0 AND water@1 (and water@2 if you need it to stay underwater).
- **ADJACENT_PATTERN**, **SLANT** (`condition: a < value && value < b`), **SAMPLER_3D**.
- Combine with `type: AND` / `OR` of locators.

## 3. Structures — what gets placed
```yaml
structures:
  distribution: { type: CONSTANT }      # or a weighted list to pick among variants
  structures: my_structure              # a .tesf/.schem name, OR
  # structures: BLOCK:minecraft:dead_bush
  # structures: BLOCK:minecraft:potent_sulfur[potent_sulfur_state=wet]
```
For anything procedural (lakes, vents, boulders, speleothems, geysers) write a `.tesf`
under `structures/` (see the create-feature companion patterns in `structures/README.md`):
`block(x,y,z,id[,overwrite[,physics]])`, `getBlock`, `check()=="LAND"`, `fail`,
`randomInt(n)`, `sampler("simplex3",...)`, `originX/Y/Z()`, `round/sqrt/pow/sin/cos`,
string `+`. Bail early with `fail` when the context is wrong (e.g. campfires emit no smoke
next to water — guard and `fail`, or place the source on dry ground).

## 4. Wire it into a biome and the stage that fits
Add the feature `id` to the biome's `features.<stage>` list. Stage order (from `pack.yml`):
`global-preprocessors → preprocessors → structures → landforms → slabs → ores → deposits →
river-decoration → trees → processors → underwater-flora → sculk → flora → postprocessors →
snow → entities`. Ordering matters when features depend on each other (place the ground/
material before the thing that locates on it — e.g. fill water before placing vents in it).

**`extends` per-stage override:** when a biome `extends` several parents, feature stages
merge **per stage, later-parent-wins** — a later parent that defines `trees:` replaces an
earlier one's `trees:`. To attach shared dressing without clobbering a host biome, put it
in a stage the hosts don't use (e.g. `processors`). See [`agents.md`](../../../agents.md).

## 5. Validate
- YAML parses.
- `python .scripts/calculate_biome_percentages.py` resolves with no schema errors.
- These check **wiring only**. Density/appearance and `.tesf` correctness MUST be confirmed
  in-world (`docs/CAPTURES.md`); the static predictor over-reports spatially-gated features.
