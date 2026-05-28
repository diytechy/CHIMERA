# Terrain Sampler Sharing Recommendations

These biomes have similar enough terrain definitions that they could share a common eq_* base file.

## 1. eq_fossilized_fenlands ≈ eq_foliage_fortress_outer
**Biomes:** `dinosaurs.yml` (FOSSILIZED_FENLANDS), `foliage_fortress_outer.yml` (FOLIAGE_FORTRESS_OUTER)

Identical terrain expression and samplers (`plateous`, `surfaceOffset`). Differ only in `base` variable (71 vs 69).

**Action:** Merge into one eq file with a shared default `base`, or accept the 2-block height difference and merge anyway.

---

## 2. eq_arch_ocean ≈ eq_frozen_arch_ocean
**Biomes:** `arch_oceans.yml` (STONEGATE_SEAS), `frozen_arch_ocean.yml` (ARCTIC_ARCHES)

Same arch structure and main expression. Differences:
- `archHeight`: 3 vs 4
- `arch_oceans` includes `+ widthRandom(x,y,z) * 0.8` in the arch expression

**Action:** Merge into one eq file with `archHeight` as a variable and `widthRandom` included in both (the effect underwater is minor).

---

## 3. eq_lush_loops / eq_arch_ocean / eq_frozen_arch_ocean — shared arch primitive
**Biomes:** `lush_loops.yml`, `arch_oceans.yml`, `frozen_arch_ocean.yml`

All three use the same arch generation pattern: a wave function transformed by an arch mask sampler (`archMask`, `pillarRand`, `wave`). The arch sub-sampler logic is structurally identical across all three.

**Action:** Extract a shared `eq_arch_base.yml` abstract defining the arch sub-sampler, extended by each biome's eq file with their specific parameters.

---

## 4. eq_inferno_isle ≈ eq_cave_jungle ≈ eq_terracotta_tombs — shared cave chambers base
**Biomes:** `inferno_isle.yml`, `cave_jungle.yml`, `terracotta_tombs.yml`

All three use identical `caves` and `wallOffset` sampler definitions:
```yaml
caves:
  dimensions: 3
  type: CELLULAR
  frequency: 0.005
  jitter: 0.05
  salt: 24
wallOffset:
  dimensions: 3
  type: FBM
  sampler:
    type: OPEN_SIMPLEX_2S
    frequency: 0.025
  octaves: 2
  lacunarity: 2.8
  gain: 0.5
```
Their main expressions use these samplers differently but the underlying cave shape is shared.

**Action:** Extract a shared `eq_cave_chambers_base.yml` defining the `caves` + `wallOffset` samplers, then have each specific eq file extend it and override only the expression.

---

## 5. eq_bamboo_basin ≈ eq_sakura_streams — shared river mask
**Biomes:** `bamboo_basin.yml` (already cross-references sakura_streams), `sakura_streams.yml`

Both use the same cellular river mask pattern (`riverBaseAngle`, `riverAngleVariation`, `rivers` angle sampler, `cellMountains`). `bamboo_basin` already cross-references the riverMask sampler from `eq_sakura_streams.yml`.

**Action:** The cross-reference is already in place. Consider making this explicit by extracting a shared `eq_river_mask_base.yml` that both extend.
