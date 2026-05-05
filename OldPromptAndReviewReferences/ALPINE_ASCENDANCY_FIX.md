# ALPINE_ASCENDANCY Missing from Origen2 - Root Cause & Fix

## Issue

ALPINE_ASCENDANCY showed 0.0000% in origen2 preset but had a value in default preset, despite both using the same climate processing chain.

## Root Cause

**Bug in calculate_biome_percentages.py script** - Not a configuration issue!

The script incorrectly handled the `SELF` keyword in REPLACE stages. When processing:

```yaml
- type: REPLACE
  from: land
  to:
    SELF: 16      # Keep as "land"
    _canyon: 10   # Convert to canyon
```

The script was creating a literal biome called "SELF" instead of preserving the original biome name ("land").

## Impact Chain

1. **Canyons stage** (origen2 only, runs before temperature):
   - Should: Convert 38.5% of `land` → `_canyon`, keep 61.5% as `land`
   - Actually did: Created biome called `SELF` (36.3%)

2. **Temperature stage**:
   - Looks for `default-from: land` to create climate zones
   - Found NO `land` biome (it was renamed to `SELF`)
   - Result: No ice-cap, tundra, boreal-cold, or boreal-snowy created

3. **Elevation stage**:
   - Converts ice-cap → ice-cap-highlands
   - Converts tundra → tundra-highlands
   - Converts boreal-cold → boreal-cold-highlands
   - Found NONE of these → Created NO highland biomes

4. **Set_biomes_in_climates stage**:
   - Converts tundra-highlands → ALPINE_ASCENDANCY (among others)
   - Found NO highland biomes → ALPINE_ASCENDANCY: 0.0000%

## The Fix

Added SELF handling in process_replace() method (calculate_biome_percentages.py:179-183, 194-198):

```python
for to_biome, weight in to_weights.items():
    prob = from_prob * (weight / total_weight)
    if to_biome == 'SELF':
        # SELF means keep the original biome
        new_dist.add(from_biome, prob)  # Use "land", not "SELF"
    else:
        new_dist.add(to_biome, prob)
```

## Results

### Before Fix:
```
default:  ALPINE_ASCENDANCY: 0.1878%
origen2:  ALPINE_ASCENDANCY: 0.0000%  ← WRONG
```

### After Fix:
```
default:  ALPINE_ASCENDANCY: 0.1918%
origen2:  ALPINE_ASCENDANCY: 0.1212%  ← CORRECT
rearth:   ALPINE_ASCENDANCY: 0.6410%
```

## Why Origen2 < Default

Origen2 has slightly lower ALPINE_ASCENDANCY percentage because:

1. Origen2 starts with 60% land, 40% ocean (vs default: 50/50)
2. Canyons stage converts ~23% of total area to canyon biomes (ICY_INCISIONS, SANDY_SPLITS)
3. This leaves ~37% as "land" to be processed by climate stages
4. Less land → fewer cold climate zones → fewer highlands → less ALPINE_ASCENDANCY

This is **expected behavior** - the canyons feature naturally reduces other biome percentages.

## Verification

The fix was verified by tracing biome flow through the pipeline:

**Origen2 - BEFORE temperature stage (after canyon):**
```
land:        14.12% ← Now correctly preserved (was "SELF")
vast-forest: 15.00%
island:      10.00%
SANDY_SPLITS: 5.04%
ICY_INCISIONS: 3.78%
```

**Origen2 - AFTER temperature stage:**
```
ice-cap:       0.78% ← Now created!
tundra:        0.78% ← Now created!
boreal-cold:   0.78% ← Now created!
boreal-snowy:  0.78% ← Now created!
```

**Origen2 - AFTER elevation stage:**
```
tundra-highlands:        0.26% ← Now created!
boreal-cold-highlands:   0.26% ← Now created!
boreal-snowy-highlands:  0.26% ← Now created!
```

**Origen2 - FINAL:**
```
ALPINE_ASCENDANCY: 0.1212% ← Success!
```

## Lessons Learned

1. **SELF is a Terra keyword**, not a biome name
2. **The script must correctly model Terra's behavior** to produce accurate percentages
3. **Tracing intermediate biomes** is essential for debugging pipeline issues
4. **User questions are valuable** - your observation led to finding this critical bug!

---

**Fixed:** 2026-01-07
**Issue reported by:** User observation about ALPINE_ASCENDANCY distribution
**Root cause:** Script bug in SELF keyword handling
**Configuration status:** No changes needed - configs are correct
