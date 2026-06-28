# Plan: Align CHIMERA Sulfur Caves appearance with Paper 26.2

Companion to `SULFUR_CAVES_STATUS_REPORT.md`. Goal: make the sulfur caves *look* like
vanilla — **stone-walled caves whose sulfur is feature-driven** — instead of the current
solid sulfur/cinnabar walls. Exact vanilla data is in the status report §3.

## The core shift
Vanilla = normal stone cave (all-vanilla ores, NO sulfur/cinnabar ore). Sulfur appears as:
`rooted_sulfur_spring` (sulfur "roots" + spring formations) → `sulfur_pool` (sulfur-lined
water + 1 potent source) → `sulfur_spike`/`_cluster` (speleothems grown ON the sulfur,
including up through pools). **Order matters: sulfur is placed first, spikes grow on it last.**

---

## Change 1 — Palette → stone base (the big visual change)
**Files:** `palettes/cave/sulfur-caves/sulfur_caves.yml`, `sulfur_caves_deepslate.yml`
- Replace the sulfur-dominant materials with **stone (top) / deepslate (deep)**, matching a
  normal cave (model on `palettes/cave/standard_caves` or just `minecraft:stone`/`deepslate`).
- Option: keep a *very* light sulfur fleck (e.g. 1-in-20) for tint, or none for strict vanilla.
- Consequence: the biome no longer reads "sulfur" from walls — all sulfur now comes from
  features below. This is the dependency the reorder addresses.
- Keep `vanilla: minecraft:sulfur_caves` (spawns/music/fog unaffected).

## Change 2 — Exact biome metadata (easy win)
**File:** `biomes/cave/sulfur_caves.yml`
- `climate`: temperature `0.8`, downfall `0.4`, precipitation `true` (vanilla has_precipitation).
- `colors`: fog `0x8cb831`, sky `0x78a7ff`, water-fog `0x17543c`, grass `0xaba64f`, water `0x34bf89`.
- Update `biomes/colors.yml:SULFUR_CAVES` map color to match (~`0xaba64f`/sulfur tone).

## Change 3 — Sulfur "growths" / rooted-spring approximation (NEW; main sulfur placer)
Terra has no `root_system`/`speleothem`-spread, so approximate with a `.tesf`.
**New:** `structures/geological/sulfur/sulfur_growth.tesf` + `features/.../sulfur_growths.yml`
- Placed on cave floors (locator like SULFUR_LAKES: solid@0/air@1), **preprocessors stage**,
  moderate density (a handful per cave region).
- Structure: a sulfur bulb/blob at the floor, **climbing sulfur up nearby walls/ceiling a few
  blocks** (the "roots"), with **cinnabar specks** and a `potent_sulfur` core. This is what
  makes stone caves read as sulfur caves.
**New (occasional, larger):** `sulfur_spring_formation.tesf` — the NBT-template analogue: a
  bigger mound of sulfur + **cinnabar bands** + tuff + `potent_sulfur` (mixed states), rarer.

## Change 4 — Pools: align to vanilla `lake` semantics
**Files:** `sulfur_lake.tesf`, `sulfur_lakes.yml` (already close)
- Keep sulfur barrier + water (matches vanilla `lake`).
- **Potent sulfur:** vanilla = exactly ONE `potent_sulfur[wet]` at the pool floor (the source),
  not a 1/16 scatter. Decide: match vanilla (1 source block at deepest point) vs keep the
  stylistic scatter. (Recommend ~1 source + a couple, closer to vanilla.)
- Density/size already user-tuned; fine.

## Change 5 — Spikes: retarget + REORDER (the ordering ask)
**Files:** spike features + `sulfur_caves.yml` feature stages
- **Match substrate = sulfur AND cinnabar** (vanilla replaceable tag `[sulfur, cinnabar]`), since
  walls are now stone — spikes must key off the feature-placed sulfur, not walls.
- **Stage order (critical):**
  1. `preprocessors`: SULFUR_GROWTHS, SULFUR_SPRING_FORMATION, SULFUR_LAKES  (place all sulfur first)
  2. (`ores`: inherited vanilla ores — keep; runs in its own stage)
  3. `landforms`: SULFUR_CAVES_FLOOR/CEILING_SULFUR_SPIKES  (grow on the sulfur just placed)
  - preprocessors < landforms in pack.yml, so this guarantees sulfur-before-spikes (mirrors
    vanilla step 1 → step 7).
- **Density up** toward vanilla (very dense: 192-256/chunk + clusters) — raise via the spike
  features' distributor (keep the `< threshold` convention; threshold = placement fraction).
- **Spikes through water:** the lake `.tesf` already adds pool stalagmites; optionally also a
  small floor-spike pass that allows water above so spikes rise from pools biome-wide.

## Change 6 — Drop / reconcile divergences
- **SULFUR_DEPOSITS** (rare worldwide sulfur ore-blobs): vanilla has none. Keep only as a
  deliberate CHIMERA embellishment, or remove for strict alignment.
- **Cinnabar in walls:** removed by Change 1; cinnabar now only in growths/springs (vanilla-like).
- **`minecraft:sulfur`/`cinnabar` in ABSTRACT_ORE.replace:** with stone walls this is less
  needed; keep so ores can still appear within sulfur growths (harmless), or revert. Minor.

---

## Suggested execution order
1. Change 2 (metadata) + Change 1 (palette → stone) — immediate visual shift; verify in-world.
2. Change 3 (growths/springs) — restores sulfur presence on the now-stone walls.
3. Change 5 (spike reorder + substrate + density).
4. Change 4 (pool potent to ~1 source).
5. Change 6 (reconcile deposits/ore-replace).
Each is independently testable; in-world capture needed for density (static tools only check wiring).

## Risk / watch-outs
- Stage-override: putting features directly in `sulfur_caves.yml` stages is authoritative for that
  biome (it defines its own preprocessors/landforms) — safe, but it REPLACES any inherited list for
  that stage. SULFUR_CAVES currently only defines preprocessors+landforms, so fine. See memory
  `terra-extends-stage-override`.
- Spikes need real sulfur underneath at placement time → the preprocessors-before-landforms order is
  mandatory, else spikes find no sulfur substrate and don't place.
- All densities are guesses until seen in-world.
