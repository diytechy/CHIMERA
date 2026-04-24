# Biome Resolution Investigation - Final Findings

## Summary

**The rearth preset does NOT have unresolved intermediate biomes.**

The original issue reported (`_desert` showing as 0.0582% in rearth) was caused by **incorrect modeling in the calculate_biome_percentages.py script**, not an actual configuration bug.

## What Was Wrong With The Script

### Original (Incorrect) Assumption

The script assumed that REPLACE stages with samplers only partially replaced biomes:

```python
# INCORRECT CODE (lines 163-166)
elif sampler_type in ['EXPRESSION', 'OPEN_SIMPLEX_2', 'WHITE_NOISE', 'CELLULAR']:
    transform_fraction = 0.4  # Only 40% replaced
```

This caused the script to calculate that:
- 60% of `_desert` remained as `_desert` (unresolved)
- 40% was split between DESERT and OASIS

### Actual Terra Behavior (From Source Code)

After examining the Terra source code at `C:\Projects\Terra`, we found:

**REPLACE stages replace ALL matching biomes (100%), not just a fraction.**

From `ReplaceStage.java`:
```java
if(viewPoint.getBiome().getTags().contains(replaceableTag)) {
    PipelineBiome biome = replace.get(sampler, worldX, worldZ, worldSeed);
    return biome.isSelf() ? viewPoint.getBiome() : biome;
}
```

#### How Samplers Actually Work

1. **The `from` field** - Matches biomes by tag/ID
2. **ALL matching biomes are replaced** - No partial replacement
3. **The `sampler` determines WHICH `to` biome is selected** at each location (spatial pattern)
4. **The `to` weights** determine proportional distribution (modified by sampler spatial pattern)

#### Example

```yaml
- type: REPLACE
  from: _desert
  sampler: { type: CELLULAR }
  to:
    DESERT: 1
    OASIS: 1
```

**What this does:**
- Finds ALL locations with `_desert` biome
- At each location, uses the cellular sampler to pick either DESERT or OASIS
- The 1:1 weight means approximately 50% DESERT, 50% OASIS (with spatial coherence from sampler)
- **Result: 0% `_desert` remaining**

## Corrected Script Results

After fixing the script to model Terra's actual 100% replacement behavior:

### Before Fix:
```
UNRESOLVED INTERMEDIATE BIOMES:
  _canyon: origen2: 1.5153%, rearth: 4.6154%
  _desert: rearth: 0.0582%
  _pillow_plains: rearth: 0.0369%
  _foliage_fortress: rearth: 0.0369%
  _foliage_fortress_center: rearth: 0.0074%
  _secluded_valleys: rearth: 0.0185%
  [+ many more intermediate biomes]
```

### After Fix:
```
UNRESOLVED INTERMEDIATE BIOMES:
  None - all biomes properly resolved!
```

## What Samplers Control

Based on Terra source code analysis:

| Component | Controls |
|-----------|----------|
| `from` field | Which biomes to replace (tag/ID matching) |
| Sampler | **WHICH** replacement biome is selected at each (x, z) coordinate |
| `to` weights | Proportional distribution across the world |
| Sampler pattern | Spatial coherence (clumping/scattering) of replacement biomes |

**Key Insight:** Samplers create **deterministic, spatially-coherent patterns** for biome selection, not probability-based random selection. This ensures biomes appear in natural-looking clusters rather than random noise.

## Implications

1. **Configuration is correct** - The border_biomes.yml file works as intended
2. **No unresolved biomes exist** - All intermediate biomes (`_desert`, `_canyon`, etc.) are fully resolved
3. **Weights control distribution** - The 1:1 ratio in `to:` determines average ~50/50 split
4. **Samplers control pattern** - Cellular noise creates organic-looking biome boundaries

## Technical Details

### Sample Distribution (from corrected script)

**rearth preset final distribution (top biomes):**
```
SANDY_SPLITS:             10.99%  (from _canyon)
ICY_INCISIONS:             8.24%  (from _canyon)
BEACH:                     7.27%
PALM_BEACH:                4.35%
SHALE_BEACH:               2.75%
TEMPERATE_SEA_ARCHES:      1.67%
```

Notice: No `_desert` or other intermediate biomes in the output.

### Where DESERT/OASIS Went

The `_desert` biome:
- Was only created in presets that use `fill_temperature_zones.yml`
- The **rearth preset doesn't use that stage**, so `_desert` is never created
- The rearth preset uses a simpler pipeline: coasts → oceans → temperature zones → patchwork → borders

The **default preset** does create and resolve `_desert`:
- Creates `_desert` via temperature/climate stages
- Resolves to DESERT (0.4581%) and potentially other desert variants

## Conclusion

**You were absolutely right to question the script!**

The original assumption that samplers control "how much" gets replaced was incorrect. They actually control "which replacement" is selected at each location. This is a critical distinction that affects biome distribution calculations significantly.

The configuration files are working correctly, and Terra's REPLACE stages behave exactly as the configuration intends.

---

**Script Fixed:** calculate_biome_percentages.py now correctly models Terra's 100% replacement behavior
**Generated:** 2026-01-07
**Based on:** Terra source code analysis (ReplaceStage.java, ProbabilityCollection.java)
