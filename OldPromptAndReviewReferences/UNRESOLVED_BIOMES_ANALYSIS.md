# Analysis: Unresolved Intermediate Biomes in rearth Preset

## Summary

The `rearth` preset has several unresolved intermediate biomes that remain in the final distribution because the `REPLACE` stages in `border_biomes.yml` are using samplers incorrectly, leaving some intermediate biomes unresolved.

## Root Cause

### How Terra REPLACE Stages Work

When a `REPLACE` stage has a `sampler`:
- **If sampler > 0**: Replace the `from` biome with the `to` biome(s)
- **If sampler <= 0**: Keep the original biome (no replacement)

This is a **spatial/conditional** replacement, not a probabilistic one.

### The Problem in border_biomes.yml

Example from `border_biomes.yml` lines 48-62:

```yaml
- type: REPLACE
  from: _desert
  sampler:
    dimensions: 2
    type: EXPRESSION
    expression: if(cells(x,z) < -0.991, 1, -1)
    samplers:
      cells:
        dimensions: 2
        type: CELLULAR
        jitter: ${customization.yml:biomeSpread.cellJitter}
        frequency: 1 / ${customization.yml:biomeSpread.cellDistance}
  to:
    DESERT: 1
    OASIS: 1
```

**What this does:**
- Where `cells(x,z) < -0.991` (returns 1): Replace `_desert` → DESERT or OASIS
- Where `cells(x,z) >= -0.991` (returns -1): Keep as `_desert`

**The Issue:**
Cellular noise ranges from -1 to 1, so values < -0.991 are **extremely rare** (< 1% of locations). This means:
- ~99% of `_desert` biomes **remain as `_desert`**
- Only ~1% get converted to DESERT/OASIS

Since no stages after `border_biomes.yml` process `_desert`, these intermediate biomes remain in the final world generation, which should not happen.

## Affected Intermediate Biomes

From the rearth preset:

| Intermediate Biome | Percentage | Created In | Should Resolve To |
|-------------------|-----------|-----------|-------------------|
| `_desert` | 0.0582% | fill_temperature_zones.yml | DESERT, OASIS |
| `_pillow_plains` | 0.0369% | fill_temperature_zones.yml | PILLOW_PLAINS_INNER/MIDDLE/OUTER |
| `_foliage_fortress` | 0.0369% | fill_temperature_zones.yml | FOLIAGE_FORTRESS_OUTER, _foliage_fortress_center |
| `_foliage_fortress_center` | 0.0074% | border_biomes.yml | FOLIAGE_FORTRESS_MIDDLE/INNER |
| `_secluded_valleys` | 0.0185% | fill_temperature_zones.yml | SECLUDED_VALLEY, SECLUDED_VALLEY_OUTER |
| `_canyon` | 4.6154% | canyons.yml | ICY_INCISIONS, SANDY_SPLITS |

Additional unresolved (non-underscore intermediates):

| Intermediate Biome | Percentage | Should Resolve To |
|-------------------|-----------|-------------------|
| `land` | 18.0000% | Final biomes via multiple stages |
| `ocean` | 23.4000% | Ocean variants |
| `cold/medium/warm` | 2.4% each | Temperature-specific biomes |
| `coast_*` variants | Various | Coast biomes |
| `ocean_*` variants | 3.12% each | Ocean temperature variants |

## Why This Happens

The `border_biomes.yml` stage uses sampler expressions to create **borders/edges** around biome regions. The pattern used is:

```yaml
expression: if(cells(x,z) < THRESHOLD, 1, -1)
```

This creates replacements only at:
- Cell centers (very low THRESHOLD like -0.991)
- Cell edges (using `Distance2Sub` return type)

**The problem:** There's no "else" case or `default-to` for locations that don't match the sampler condition.

## Comparison with origen2 Preset

The `origen2` preset also has `_canyon` (1.5153%) unresolved for the same reason. However, origen2 has fewer unresolved intermediates because:
1. It uses `border_biomes.yml` in stage 15 (after more processing)
2. Many of the intermediate biomes are resolved by earlier stages

The `default` preset has NO underscore-prefixed intermediates remaining, only `arid-pale-garden` and `maple-groves` (old naming convention).

## Recommendations

### Option 1: Add Default Replacements

Modify `border_biomes.yml` to ensure all intermediate biomes are replaced:

```yaml
- type: REPLACE
  from: _desert
  to: DESERT  # First, replace ALL _desert with DESERT

- type: REPLACE
  from: DESERT
  sampler:
    expression: if(cells(x,z) < -0.991, 1, -1)
  to: OASIS  # Then add OASIS at cell centers
```

### Option 2: Use REPLACE_LIST with default-from/default-to

Convert to `REPLACE_LIST` type which handles defaults:

```yaml
- type: REPLACE_LIST
  default-from: _desert
  default-to:
    - DESERT: 1
  sampler:
    expression: if(cells(x,z) < -0.991, 1, -1)
  to:
    _desert:
      - OASIS: 1
```

### Option 3: Accept as Intentional Design

If these intermediate biomes are intentional (for debugging or special purposes), they should:
1. Have proper biome definition files in the `biomes/` directory
2. Be documented as valid "temporary" or "placeholder" biomes
3. Have palette/feature definitions so they render correctly

## Impact

**Current State:**
- These unresolved biomes appear in the BiomeTable.csv as `UNLINKED_*`
- They may cause runtime errors if Terra encounters them during world generation
- Players might see these biomes with undefined/broken generation

**Recommended Action:**
Review and fix the `border_biomes.yml` configuration to ensure all intermediate biomes are fully resolved before the pipeline completes.

## Related Files

- `.scripts/calculate_biome_percentages.py` - Now correctly identifies and marks unresolved biomes
- `biome-distribution/stages/special/border_biomes.yml` - Source of the issue
- `biome-distribution/stages/fill_temperature_zones.yml` - Creates the intermediate biomes
- `biome-distribution/presets/rearth.yml` - Affected preset

---

**Generated:** 2026-01-07
**Script Version:** calculate_biome_percentages.py with unresolved biome detection
