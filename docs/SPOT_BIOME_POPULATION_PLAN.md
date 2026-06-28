# Spot-Biome Population Plan — Prismatic Springs, Volcanoes & Crater Lakes

**Status:** Proposal for review. No code changed by this document.
**Goal:** Make the geothermal spot biomes (prismatic springs, erupted/extinct volcanoes, crater lakes) feel inhabited and interesting *around* the central feature, instead of a colorful/lava center surrounded by bare terrain.

---

## 1. Background: how these spots are built

All volcano/spring spots are **"small spots"**: radius **50–150 blocks** (~100–300 diameter), spaced ~1500 blocks apart (`customization.yml: spot-radius-min/max`, `spot-spread`). They are placed by the cellular spot system in `math/samplers/spots.yml`.

Each spot is organised as **concentric radial bands**, addressed by signed distance samplers (negative = inside the pool/crater, `0` = rim, increasing to ~`1` at the outer edge):

| Sampler | Used by | `< 0` | `≈ 0` | `0 → 1` |
|---|---|---|---|---|
| `distanceToPrismaticRim` | prismatic spring | pool interior | waterline rim | apron → exterior |
| `distanceToVolcanicRim` | volcanoes / craters | crater interior | crater rim | cone slope → base |

Key shape facts:
- **Prismatic springs are flat** (`prismaticMinHeight`/`MaxHeight` = 0). A flat colored pool with an apron, *not* a cone.
- **Extinct volcanoes** are a raised cone (height `0.05–0.2 × terrain-height`) with a central crater.
- **Erupted volcanoes** are a tall cone (`0.2–0.4`) with a lava crater.
- **Crater lakes** = an extinct volcano whose crater is water-filled (`VOLCANO_WATER` / `ICE_LAKE`).
- The rim sits at **50–70 %** of the radius (`*EdgeRadius`), so the apron/outer ring is roughly **15–75 blocks wide** — that wide ring is where almost all the current barrenness lives.

### Existing radial-band precedent (reuse this exact pattern)
`PRISMATIC_SPRING_MAGMA` / `PRISMATIC_SPRING_SMOKE` and the new `POTENT_SULFUR_*` vents already gate placement with a distance sampler + a `PADDED_GRID` (or white-noise) distributor. Every new feature below follows the same recipe:

```yaml
distributor:
  type: SAMPLER
  sampler:
    type: EXPRESSION
    dimensions: 2                      # NOTE: samplers in these distributors are 2D
    expression: if(distanceToVolcanicRim(x, z) > LO && distanceToVolcanicRim(x, z) < HI, rarity(x, z), -1)
    samplers:
      distanceToVolcanicRim: $math/samplers/spots.yml:samplers.distanceToVolcanicRim
      rarity:
        dimensions: 2
        type: POSITIVE_WHITE_NOISE
        salt: <unique>
  threshold: <0.9–0.99 for sparsity>
locator: { SURFACE + MATCH_SOLID(-1)/MATCH_AIR(0) }   # standard surface placement
```

Recommended band thresholds (reuse the values the existing sulfur vents already use so everything lines up):

| Band | Prismatic (`distanceToPrismaticRim`) | Volcano (`distanceToVolcanicRim`) |
|---|---|---|
| Pool / crater floor | `< 0` | `< 0` (lake), `< -0.1` (dry) |
| Waterline / crater rim | `-0.05 … 0.10` | `-0.1 … 0.1` |
| Apron / cone slope | `0.10 … 0.55` | `0.1 … 0.6` |
| Outer transition / base | `0.55 … 1.0` | `0.6 … 1.0` |

---

## 2. Reusable assets already in the pack (no need to build)

- **Boulders / talus:** `MOLTEN_ROCKS`, `TUFF_BOULDERS`, `GRANITE_BOULDERS`, `MOSSY_BOULDERS`, `SMALL_BOULDER_PATCHES`, `SMALL_CALCITE_BOULDER_PATCHES`, flat variants.
- **Geothermal:** `HORNITOS` / `SPARSE_HORNITOS`, `VOLCANO_LAVA`, `VOLCANO_SMOKE`, `magma_smoke` particle, `MAGMA_CAVE_LAVA_PILLAR`.
- **Mineral terraces (Yellowstone/Pamukkale):** `EQ_TRAVERTINE_TERRACES`, `TRAVERTINE_WATER`, `TRAVERTINE_WATERFALLS`, calcite palette — currently only on the standalone `TRAVERTINE_TERRACES` biome.
- **Dead / heat-killed vegetation:** `DEAD_TREES_LARGE`, `DEAD_TREES_MODERATE`, `DEAD_BUSHES_BARREN`, `DEAD_BUSHES_ARID`, `CACTI_BARREN`, `BARREN_LEAF_BUSHES`.
- **Mineral/sediment patches:** `CLAY_DEPOSITS`, `GRAVEL_DEPOSITS`, `SUSPICIOUS_GRAVEL`, `SULFUR_DEPOSITS` (new), `CALCITE_CAVERN_SPIKE`.
- **Small pools (model for satellite springs):** `COASTAL_WATER_POOLS`, `LUSH_CAVE_WATER_POOLS`.
- **Sulfur (new this branch):** `POTENT_SULFUR_FUMAROLE`, `POTENT_SULFUR_DORMANT_VENT`, `POTENT_SULFUR_SPRING_VENT`, `SULFUR_SPRING`.

---

## 3. New shared mechanisms to create

These are referenced by multiple biomes; build once.

1. **Feature mixins** (abstract biomes carrying one feature stage, like `SULFUR_SPRING_SURFACE`):
   - `PRISMATIC_APRON_FEATURES` → attached to `EQ_PRISMATIC_SPRING`.
   - `VOLCANO_SLOPE_FEATURES` → attached to `EQ_EXTINCT_VOLCANO` (covers all 5 extinct + all 5 crater lakes in one edit).
   - This keeps shared work DRY; per-biome files only add climate flavor.
2. **New `.tesf` structures** (small, procedural — model on existing boulder/spring `.tesf`):
   - `sinter_step` (banded calcite/terracotta micro-terrace), `fumarole` (steam vent cap), `satellite_pool` (1–5 block hot pool), `obsidian_sheet`, `ash_patch`, `cooled_lava_crack`.
3. **New palettes** (only if a banded look is wanted): `PRISMATIC_SINTER` (white→cream→orange mineral crust for the rim).

---

## 4. Per-biome plan

> Most shared features attach at the **abstract** level. Per-biome entries below list only what is *unique* to that biome (climate flavor) on top of the inherited shared set.

### 4.1 Abstracts (shared — edit these first)

#### `EQ_PRISMATIC_SPRING` (abstract terrain) → gains `PRISMATIC_APRON_FEATURES`
Currently terrain-only. Add the shared spring dressing so `PRISMATIC_SPRING` (and any future spring) inherits it:
- **Waterline rim band:** `PRISMATIC_SINTER_RIM` (new — banded crust at `-0.05…0.10`), `PRISMATIC_BACTERIAL_STREAMERS` (new — radial lime/orange `*_concrete` fingers using `spotAngle`).
- **Apron band (`0.10…0.55`):** `PRISMATIC_FUMAROLE` (new — magma pocket + `magma_smoke`), `PRISMATIC_SATELLITE_POOL` (new — mini secondary springs), `SULFUR_DEPOSITS` + `CLAY_DEPOSITS`/`GRAVEL_DEPOSITS` mineral patches, `DEAD_BUSHES_BARREN` / `DEAD_TREES_MODERATE` (heat-killed).
- **Outer transition (`0.55…1.0`):** `SMALL_BOULDER_PATCHES`, sparse recolonising grass (climate-keyed in the concrete biome).

#### `EQ_EXTINCT_VOLCANO` (abstract terrain) → gains `VOLCANO_SLOPE_FEATURES`
Already carries `POTENT_SULFUR_DORMANT_SURFACE`. Add cone/crater dressing inherited by all 5 extinct volcanoes **and** all 5 crater lakes:
- **Crater floor (`< -0.1`):** `CRATER_SEDIMENT` (new — clay/gravel/mud bed), `OBSIDIAN_SHEET` (new, sparse).
- **Crater rim (`-0.1…0.1`):** existing `POTENT_SULFUR_DORMANT_VENT`, `OBSIDIAN_SHARDS` (new).
- **Cone slope (`0.1…0.6`):** `MOLTEN_ROCKS` + `TUFF_BOULDERS` (reuse — give extinct cones the same boulders the erupted one has), `COOLED_LAVA_CRACKS` (new — basalt/blackstone veins), `ASH_PATCHES` (new — tuff/gravel), `SPARSE_HORNITOS` (reuse, dormant).
- **Base apron (`0.6…1.0`):** `SMALL_BOULDER_PATCHES` talus; recolonising vegetation (climate-keyed).

#### `EQ_VOLCANO` (abstract terrain, erupted) → optional shared slice
The erupted volcano already has lava/boulders/sulfur/smoke; treat as **enhancement only** (see 4.3). No mixin required unless we add future active volcanoes.

---

### 4.2 Prismatic spring

#### `PRISMATIC_SPRING`  *(extends `EQ_PRISMATIC_SPRING`, `ENVIRONMENT_LAND_CONTINENTAL_HUMID`, `CARVING_NONE`, `BASE`)*
- **Current:** `PRISMATIC_MICROBIAL_MAT` palette (good color bands), `PRISMATIC_SPRING_MAGMA`, `PRISMATIC_SPRING_SMOKE`, `POTENT_SULFUR_SPRING_VENT`. Center is fine; rim/apron empty.
- **Inherits (new):** the full `PRISMATIC_APRON_FEATURES` set above.
- **Biome-specific:**
  - Denser core steam (raise `PRISMATIC_SPRING_SMOKE` density or add a second emitter).
  - Recolonisation = temperate-humid: tufts of grass + `OAK_SHRUBS` only in the outer transition, so the inner apron stays bare and mineral-looking.
  - Consider a faint `particles:` entry (white_smoke already present at 0.001 — bump slightly).

---

### 4.3 Erupted volcano

#### `ERUPTED_VOLCANO`  *(extends `EQ_VOLCANO`, `CARVING_NONE`, `BASE`)*
- **Current:** `LAVA_CRACKS` palette, ash particles, `SMOOTH_LAVA`, `VOLCANO_LAVA`, `MOLTEN_ROCKS`, `TUFF_BOULDERS`, `POTENT_SULFUR_FUMAROLE`, `VOLCANO_SMOKE`. Already the richest spot.
- **Add (enhancement):**
  - `OBSIDIAN_SHEET` + `OBSIDIAN_SHARDS` around the crater rim (fresh lava meeting cooler edges).
  - More `HORNITOS` on the upper cone (active spatter cones).
  - `ASH_PATCHES` thickening toward the base.
  - `DEAD_TREES_LARGE` (charred) only on the lowest slope/base — recently-killed forest at the lava's edge.

---

### 4.4 Extinct volcanoes (5 climate variants)

All extend `EQ_EXTINCT_VOLCANO` (so all inherit `VOLCANO_SLOPE_FEATURES`). Per-biome entries add climate flavor only.

#### `BOREAL_EXTINCT_VOLCANO`  *(extends `BOREAL_MESA`; vanilla taiga; `USE_COLD_RIVER`)*
- Spruce **snags** (`DEAD_TREES_MODERATE`) + sparse live spruce shrubs reclaiming the base; podzol/coarse-dirt patches over ash; `MOSSY_BOULDERS` on the oldest talus.

#### `COLD_EXTINCT_VOLCANO`  *(extends `SNOWY_MOUNTAINS`; vanilla frozen_peaks; `ICE_CAVES`; has `ICE_COASTLINE`)*
- Snow/`ICE` crust on the rim; "frozen steam" (very sparse white smoke); packed-ice + obsidian shards in the crater; **no trees**, only the occasional dead bush poking through snow.

#### `DESERT_EXTINCT_VOLCANO`  *(extends `ROCKY_DESERT`; vanilla desert; `USE_DESERT_RIVER`)*
- Heaviest `ASH_PATCHES` + sulfur/calcite **mineral crust**; `DEAD_BUSHES_ARID` + `CACTI_BARREN`; `SMALL_SANDSTONE_BOULDER_PATCHES`; no recolonising grass (stays stark).

#### `TEMPERATE_EXTINCT_VOLCANO`  *(extends `WOODED_BUTTES`; vanilla plains; `USE_RIVER`)*
- Richest recolonisation: grass tufts + `OAK_SHRUBS` up the lower slope, `MOSSY_BOULDERS`, moss creeping over `COOLED_LAVA_CRACKS`; a few live oaks at the base.

#### `TROPICAL_EXTINCT_VOLCANO`  *(extends `JUNGLE`; vanilla jungle; `USE_TROPICAL_RIVER`)*
- Fastest, lushest reclamation: ferns/vines, jungle shrubs, `MOSSY_BOULDERS`, glow-lichen on shaded cracks; ash mostly overgrown except near the rim.

---

### 4.5 Crater lakes (5 climate variants)

Each extends its extinct volcano (so inherits everything above) + `CARVING_NONE`, and fills the crater with water/ice. Add lakeshore life.

#### `BOREAL_CRATER_LAKE` / `TEMPERATE_CRATER_LAKE` / `TROPICAL_CRATER_LAKE` / `DESERT_CRATER_LAKE`  *(have `VOLCANO_WATER`)*
- **Shallows:** mineral-stained bed (`CRATER_SEDIMENT` extended below waterline), sparse `SEAGRASS`/reeds (climate-keyed: lush in tropical, sparse/none in desert).
- **Shoreline ring:** a damp band of recolonising vegetation between waterline and the dry apron; in desert keep it salt-crust + dead bushes instead.
- **Tropical:** add lily-pad/vine shoreline; **Temperate:** reeds + grass; **Boreal:** sparse spruce + coarse dirt shore.

#### `COLD_CRATER_LAKE`  *(has `ICE_LAKE` + `ICE_COASTLINE`)*
- Keep frozen surface; add cracked-ice detail and snow drifts on the shore; frozen steam wisps at the few open leads; no vegetation.

---

## 5. New files this plan would create

**Feature mixins (abstract biomes):**
- `biomes/abstract/features/prismatic_apron_features.yml`
- `biomes/abstract/features/volcano_slope_features.yml`

**Features** (`features/geological/volcano/` or a new `.../geothermal/`):
- Prismatic: `prismatic_sinter_rim.yml`, `prismatic_bacterial_streamers.yml`, `prismatic_fumarole.yml`, `prismatic_satellite_pool.yml`
- Volcano: `crater_sediment.yml`, `obsidian_sheet.yml`, `obsidian_shards.yml`, `cooled_lava_cracks.yml`, `ash_patches.yml`
- Plus climate-flavor feature files where an existing one doesn't fit (most reuse existing).

**Structures (`.tesf`):** `sinter_step`, `fumarole`, `satellite_pool`, `obsidian_sheet`, `ash_patch`, `cooled_lava_crack`.

**Palettes (optional):** `PRISMATIC_SINTER`.

**Edits to existing biomes/abstracts:** `EQ_PRISMATIC_SPRING`, `EQ_EXTINCT_VOLCANO`, `EQ_VOLCANO` (extends lines); `PRISMATIC_SPRING`, `ERUPTED_VOLCANO`, and the 10 extinct/crater biome files (climate-flavor feature lines only).

---

## 6. Suggested implementation order

1. **Vertical slice — prismatic-spring apron** (`PRISMATIC_FUMAROLE`, `PRISMATIC_SATELLITE_POOL`, mineral patches, dead vegetation via `PRISMATIC_APRON_FEATURES`). Biggest visual payoff, mostly reuse. Verify in-world.
2. **Prismatic rim band** (`PRISMATIC_SINTER_RIM`, `PRISMATIC_BACTERIAL_STREAMERS`) once the apron reads well.
3. **Volcano cone slopes** via `VOLCANO_SLOPE_FEATURES` on `EQ_EXTINCT_VOLCANO` (boulders, ash, cooled cracks, obsidian). Covers all 10 extinct/crater biomes at once.
4. **Climate-flavor passes** per biome (vegetation/ash/ice keyed to 4.4 / 4.5).
5. **Erupted-volcano enhancement** (4.3).
6. **Crater-lake shorelines** (4.5).

---

## 7. Validation

- YAML parse + `python .scripts/calculate_biome_percentages.py` (schema/resolution) after each phase — but note these features are **spatial/aesthetic**, so the static tools only confirm wiring, not appearance.
- **In-world capture is required**: generate a spot and screenshot it (see `docs/CAPTURES.md`). Each radial band needs eyeballing for density/threshold tuning, exactly like the existing sulfur vents.
- Watch density: aprons are large rings — start sparse (`threshold ≥ 0.94`) and increase only if too empty.

---

## 8. Open questions for review

1. **Scope** — do all four families (spring, erupted, 5 extinct, 5 crater lakes) get treated now, or just the prismatic spring first?
2. **Travertine terraces on spring rims** — reuse the existing terrace mechanic (heavier, prettier) or just a flat sinter crust (cheaper)?
3. **Satellite pools** — yes/no? They add life but also more water bodies near each spot.
4. **Vegetation intensity** — how strongly should extinct volcanoes recolonise? (Stark geology vs. softened-by-time look — currently proposed: keyed to climate, desert stark → tropical lush.)
5. **New block usage** — fine to lean on `minecraft:obsidian`, `tuff`, `*_concrete` (mineral colors), and the new 26.2 sulfur blocks here too, or keep these spots to pre-26.2 blocks so they work without the server bump?
