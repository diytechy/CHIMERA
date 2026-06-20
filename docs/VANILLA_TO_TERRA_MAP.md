# Vanilla Minecraft → CHIMERA (Terra) translation map

The reference for porting a vanilla biome into this pack. Pair it with
`.scripts/extract_vanilla_biome.py` (pulls the vanilla JSON) and the `port-vanilla-biome`
skill (the procedure). **Living document** — when you meet a vanilla type that isn't
mapped here, work out the equivalent and add a row.

## Where vanilla defines a biome's appearance (read ALL of these)
The extract script pulls each of these for you. The cardinal sin is stopping early — on
sulfur caves the **wall material lived in `surface_rule`**, not the biome/features, and
missing it produced a wrong "stone caves" port.

| Vanilla source | Defines | CHIMERA target |
|---|---|---|
| `biome/<b>.json` → `effects`, `attributes` visual | water/grass/foliage/fog/sky colors | biome `colors:` |
| `biome/<b>.json` → `temperature`,`downfall`,`has_precipitation` | climate | biome `climate:` |
| `biome/<b>.json` → `spawners`,`spawn_costs` | mob spawns | **inherit** via `vanilla: minecraft:<b>` (don't hand-copy) |
| `biome/<b>.json` → `carvers` | cave carving | inherited via `extends: [CAVE]` / `EQ_CARVING_*` |
| `noise_settings/overworld.json` **surface_rule** (gated on `biome_is`) | **wall/floor block material** | palette `materials:` + sampler |
| `configured_feature/*` + `placed_feature/*` | decorations, pools, ores, spikes | Terra `features:` + `.tesf` |
| multinoise parameter list | **where the biome generates** | `biome-distribution/` (extrusions/stages) |

## Surface rules → palette
A surface rule is `condition(biome_is) → sequence[ condition(noise_threshold) → block ]`.
Each `noise_threshold` band that maps to a block = a slice of the palette. Convert the
noise bands to material weights (estimate fractions; the noise is ~Gaussian around 0).
*Sulfur caves example:* `sulfur_cave_gradient` → cinnabar in two bands + sulfur in one +
stone in the gaps → palette `cinnabar 5 / sulfur 4 / stone 2` with a domain-warped
cellular sampler (blobs). Deep band: swap stone→deepslate.

## Configured features → Terra
| Vanilla configured feature | CHIMERA equivalent |
|---|---|
| `ore` | already inherited (`ORES_*`); only add if the ore is non-vanilla. **No** ore for decorative blocks (sulfur/cinnabar have none). |
| `lake` (barrier + fluid) | `.tesf` basin (carve + fluid + barrier shell) placed by a feature |
| `speleothem` (base + pointed, up/down) | `.tesf` spike + floor/ceiling spike features; `replaceable` tag → locator `MATCH_SET` |
| `root_system` | no Terra equiv — approximate with a `.tesf` "growth" (mound/veins) |
| `simple_block` + placement | a feature placing `BLOCK:<id>` at a located position |
| `sequence` / `*_random_selector` | several features, or one `.tesf` doing the steps |
| `template` (NBT structure) | a `.tesf` approximating the NBT formation |
| `disk`, `spring`, `geode`, `monster_room`, etc. | reuse the existing CHIMERA feature if present, else a `.tesf` |

## Placed-feature placement → Terra distributor + locator
**This is the highest-risk translation** (got it wrong first on sulfur pools).

| Vanilla placement modifier | CHIMERA |
|---|---|
| `count: N` + `in_square` | **per-column** `SAMPLER` distributor, `threshold ≈ N/256` (spreads across the chunk). **NOT** `PADDED_GRID` — that clusters at a few columns. |
| `rarity_filter { chance: C }` | lower the threshold (≈ base/C) |
| `count` (uniform/clamped) inner + `random_offset` (xz_spread) | clustered scatter — `PADDED_GRID` *is* fine here, or RANDOM `amount` |
| `height_range { uniform … }` | locator `range: {min,max}` |
| `block_predicate_filter { matching_blocks X }` | locator `PATTERN` `MATCH`/`MATCH_SET` at offset 0 |
| `environment_scan down/up → solid/air` | locator `PATTERN` (solid@0/air@1 for a floor) or `SURFACE` |
| `biome` | implicit (feature is attached to the biome) |

## Terra gotchas (these bit us)
- **`SAMPLER` distributor places where value `< threshold`**, not `>`. `threshold` = the
  placement fraction. A band-gate `if(inBand, rarity, sentinel)` must use sentinel **`1`**
  (never `< threshold`), not `-1`. See memory `feature-distributor-threshold`.
- **`extends` merges `features` per stage, later parent wins** (override, not concat). To
  add a shared feature to many biomes via a mixin, put it on a stage no host biome uses
  (e.g. `processors`). See memory `terra-extends-stage-override`.
- Distributor samplers need `dimensions: 2`.
- Block ids only resolve on a server of the matching MC version at runtime.
- `calculate_biome_percentages.py` validates **wiring only** (resolution/schema), not
  appearance or density, and **over-reports spatially-gated biomes**. Always confirm
  in-world (`docs/CAPTURES.md`).

## Worked example
`docs/SULFUR_CAVES_STATUS_REPORT.md` + `docs/SULFUR_CAVES_VANILLA_ALIGNMENT_PLAN.md` are a
full end-to-end port using this map.
