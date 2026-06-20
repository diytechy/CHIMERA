# Sulfur Caves + Spot Biomes — Status Report

**Branch:** `Sulfer-caves+sulfer-Deposits`
**Last updated:** 2026-06-18
**Purpose:** Handoff snapshot of the Paper 26.2 "Sulfur Caves" port into the CHIMERA Terra pack, the geothermal spot-biome population work, and the SULFUR_TERRACES biome — plus the exact vanilla worldgen values extracted from the 26.2 server jar.

> Requires a **Minecraft 26.2 server at runtime** — block ids (`minecraft:sulfur`, `cinnabar`, `potent_sulfur`, `sulfur_spike`) only resolve there. The pack is version-agnostic YAML; pre-26.2 servers fail to parse these.

---

## 1. Git state

Uncommitted at snapshot: `structures/geological/sulfur/sulfur_lake.tesf` (latest pool tweaks — potent 1/16, void-seal pass, spikes — see §4). Everything else is committed.

Key commits (this branch):
- `9377a035` Add Sulfur Caves biome, springs, potent-sulfur volcanic features
- `1223dcab` Rework sulfur-cave distribution: sulfur+cinnabar palette + lakes
- `16952fd1` Spot-biome population PLAN (docs/SPOT_BIOME_POPULATION_PLAN.md)
- `5a11d8a9` Populate prismatic springs, volcanoes & crater lakes (spot plan)
- `7d489df6` **Fix inverted spot-feature distribution**; denser sulfur pools; smaller prismatic springs
- `0e3619bf` Add SULFUR_TERRACES biome (unplaced)
- `16e0d521` Make sulfur pools common: rework SULFUR_LAKES placement + structure
- `58715f00` better... (pool size/depth tuning)
- (interleaved user commits: `9749e430`, `3beaabcd`, `95986789`, `19f87419`)

---

## 2. What's been built

### Sulfur Caves biome
- `biomes/cave/sulfur_caves.yml` — `vanilla: minecraft:sulfur_caves` (inherits real sulfur-cube spawns + music/fog). Palette `SULFUR_CAVES`/`SULFUR_CAVES_DEEPSLATE` is **sulfur-dominant (~70%) + cinnabar veining (~20%)** — a deliberate vivid divergence from vanilla (see §3 decision). Features: `SULFUR_LAKES` (preprocessor), floor/ceiling sulfur spikes (landforms).
- Palettes: `palettes/cave/sulfur-caves/sulfur_caves*.yml`.
- `SULFUR_LAKES` + `sulfur_lake.tesf` — underground sulfur water pools (see §4 for current tuning).
- Floor/ceiling sulfur-spike speleothems: `structures/geological/sulfur/small_{floor,ceiling}_sulfur_spike.tesf` + features.
- `minecraft:sulfur` and `minecraft:cinnabar` added to `ABSTRACT_ORE.replace` so ores carve the sulfur/cinnabar strata.

### Distribution + vanilla remap
- `SULFUR_CAVES` placed via `biome-distribution/extrusions/add_cave_biomes.yml`: a localized region sampler (`math/samplers/sulfur.yml`) clusters them, plus a small `WARM_CAVES` background weight ("slightly elevated").
- **Strong remap:** `MOLTEN_PASSAGES`, `MAGMA_CAVERNS`, `BASALT_CAVERNS` now `vanilla: minecraft:sulfur_caves` (for sulfur-cube spawns).
- Surface sulfur springs (`SULFUR_SPRING`) injected into all surface biomes via a `BASE_HYDRAXIA` mixin, gated to sulfur-region cores.
- Rare worldwide `SULFUR_DEPOSITS` (0.5/chunk) in `DEPOSITS_GENERIC`/`DEPOSITS_DEFAULT`.

### Potent-sulfur volcanic variants
- `potent_sulfur_{erupting,dormant,wet}.tesf` + features wired to erupted volcano (fumaroles), extinct volcanoes (dormant vents, via `VOLCANO_SLOPE_FEATURES`), prismatic spring (wet vents).

### Spot-biome population (docs/SPOT_BIOME_POPULATION_PLAN.md)
- **Prismatic springs**: sinter rim, mineral crust, satellite pools, steam vents, dead bushes (radial bands on `distanceToPrismaticRim`).
- **Extinct volcanoes + crater lakes** (one `VOLCANO_SLOPE_FEATURES` mixin on `EQ_EXTINCT_VOLCANO`, **`processors` stage** to avoid host-biome clobber): crater sediment, rim obsidian, ash, cooled-lava cracks, tuff boulders, dormant sulfur vents.
- **Erupted volcano**: + rim obsidian, ash.
- Generic spot dressing uses **pre-26.2 blocks** (terracotta/concrete/obsidian/tuff/basalt) so it works without the server bump; only sulfur vents use new blocks.
- **Prismatic springs shrunk to ~half** via `customization.yml:prismatic-radius-scale` (0.5) + a `prismaticRadius` sampler substituted for `spotRadius` in the rim sampler, terrain eq, and microbial-mat palette.

### SULFUR_TERRACES (unplaced)
- `biomes/land/unique/sulfur_terraces.yml` — sulfur analogue of TRAVERTINE_TERRACES (calcite→sulfur), + `SULFUR_TERRACE_WATER`/`_WATERFALLS` features + color. **Not in any distribution** (registers at 0%); place later at low weight.

### Critical bug fixed (commit 7d489df6)
The spot/sulfur radial features were **inverted**: Terra's `SAMPLER` distributor places where **value < threshold**, but the features used a `-1` out-of-band sentinel (always < threshold → placed everywhere) and high thresholds (dense). Fixed 14 features: sentinel `-1→1`, threshold → density fraction. See memory `feature-distributor-threshold`.

---

## 3. Paper 26.2 actual worldgen values (extracted from jar)

**Extraction method (repeatable):** `Z:\MC_SERV_BACKUP_20260516\MINECRAFT_SERVER_TMP_4BACKUP\cache\mojang_26.2.jar` is a bundler → nested `META-INF/versions/26.2/server-26.2.jar` → `data/minecraft/worldgen/`. (The Paper *source* at C:\Projects\Paper has no worldgen JSON, only noise_settings patches.)

**KEY FINDING — vanilla sulfur caves are STONE caves; sulfur is feature-driven, not a wall palette.** `biome/sulfur_caves.json` has all-vanilla ores (no sulfur/cinnabar ore). Sulfur comes from:

| Feature | Count/chunk | Detail |
|---|---|---|
| `rooted_sulfur_spring` | 1–2 | `root_system` (azalea-style): spreads `minecraft:sulfur` roots (radius 3, height ≤184) + triggers `sulfur_spring` (NBT templates + tuff; cinnabar lives in these). Main sulfur placer. |
| `sulfur_pool` | 256 attempts | vanilla `lake` feature: `sulfur` barrier + `water` fill, then **exactly ONE** `potent_sulfur[state=wet]` at the pool floor (geyser source). NOT a scatter. |
| `sulfur_spike` | 192–256, ×(1–5) | `speleothem`, floor AND ceiling variants; down-scan **allows water** so spikes grow up out of pools. Replaceable tag = `[sulfur, cinnabar]`. |
| `sulfur_spike_cluster` | 48–96 | denser spike clumps. |

**Biome metadata (exact):** temperature `0.8`, downfall `0.4`, has_precipitation `true`; fog `#8cb831`, sky `#78a7ff`, water-fog `#17543c`, grass `#aba64f`, water `#34bf89`; carvers cave/cave_extra_underground/canyon; music `music.overworld.sulfur_caves`.

**Spawners (monster):** sulfur_cube **w100** count 2–4 (dominant); creeper/skeleton/zombie w50; slime w25; cave_spider w20; enderman w10; zombie_villager w5; witch w1. Ambient: bat w10 count 8.

**No `cinnabar_ore`/`sulfur_ore`/`raw_*`** — both are decorative block families only (raw block + bricks/polished/chiseled/slab/stairs/wall). Cinnabar generates only via the spring NBT templates + as spike substrate.

---

## 4. Current sulfur_lake.tesf tuning (uncommitted)

Placement (`features/geological/sulfur/sulfur_lakes.yml`, user-tuned): PADDED_GRID width 7 / padding 5, RANDOM amount 40, locator targets cave floors (solid@0 / air@1 / solid@-4).

Structure (`sulfur_lake.tesf`): radius 2.5–8.5 (mean ~5.5), squish 2.2–3.4 (shallow, ~half old depth), wall = `radius−1.3`. Basin shell = sulfur, ~1/5 cinnabar, **1/16 potent_sulfur[wet]**. Added: **void-seal pass** (backfills air below/beside water with sulfur; leaves surface open) and **occasional sulfur-spike stalagmites** (radius>4, ~1/4 chance, rise out of water, waterlogged below surface).

vs vanilla: vanilla puts ~1 potent block per pool (not 1/16 scatter); spikes-through-water is vanilla-accurate.

---

## 5. Open decisions / TODO

1. **Palette style decision (biggest open item):** keep vivid sulfur/cinnabar walls (current) vs match vanilla stone walls + feature-driven sulfur vs hybrid. See §3.
2. **Apply exact vanilla biome values** to `sulfur_caves.yml` colors/temperature (easy win; values in §3). Currently uses approximations.
3. **Commit** the pending `sulfur_lake.tesf` changes.
4. **In-world tuning still needed** (static tools only validate wiring, not appearance/density) for: sulfur pool density, spike density, prismatic apron/volcano feature densities, prismatic 0.5 scale, SULFUR_CAVES rarity + total sulfur-cube exposure across the 4 remapped biomes.
5. **`potent_sulfur_fumarole.yml` locator** was changed externally to `solid@0/air@1` (vs other features' `solid@-1/air@0`) — may misalign with `potent_sulfur_erupting.tesf` (could place 1 low). Verify/realign.
6. **Crater-lake sediment** won't place under water (SURFACE locator needs air); only dry craters get it.
7. **Optional:** save extracted Paper sulfur worldgen JSON into repo as reference (Mojang-data licensing caveat for committing).
8. **SULFUR_TERRACES** still unplaced — add at low weight when desired.

---

## 6. Validation status

All committed work: YAML parses, `python .scripts/calculate_biome_percentages.py` resolves with no schema errors, structure refs resolve. `.tesf` runtime behavior and all densities are UNVERIFIED in-world. Note: BiomeTable predictor over-reports SULFUR_CAVES (~6.9%) because it can't see the spatial sulfur gate; real value est ~2%.

## 7. Related memory files
`sulfur-caves-plan`, `spot-biome-population`, `terra-extends-stage-override`, `feature-distributor-threshold`, `biome-distribution-tuning`.
