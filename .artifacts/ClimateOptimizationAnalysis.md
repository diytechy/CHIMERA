# Climate Distribution Optimization Analysis

## Current System Overview

### Pipeline Flow
```
Source: continents(x,z) → ocean/land split
   ↓
Stage: add_spots.yml → volcanic features
   ↓
Stage: add_coast.yml → coastline detection
   ↓
Stage: temperature.yml → 12 temperature zones (samples temperature(x,z))
   ↓
Stage: precipitation.yml → 6 precipitation levels (samples precipitation(x,z))
   ↓
Stage: elevation.yml → 4 elevation variants (samples elevation(x,z) + flatness(x,z))
```

### Dependency Chain (The Problem)
```
continents(x,z)
├── RIDGED noise (3 octaves, freq 1/5000) - EXPENSIVE
├── spawnIsland(x,z) - DISTANCE sampler
└── spotDistance/spotRadius - CELLULAR noise

elevation(x,z)
├── rawElevation(x,z)
│   ├── hills: FBM (6 octaves, freq 1/2000) - EXPENSIVE
│   └── mountains: Pseudoerosion + FBM (3 octaves, freq 1/900) - VERY EXPENSIVE
├── flatness(x,z) - FBM + PROBABILITY
├── continents(x,z) ← RECALCULATED
├── spawnIsland(x,z) ← RECALCULATED
└── riverTerrainErosion(x,z)

temperature(x,z)
├── rawTemperature: FBM (2 octaves, freq 1/5000)
└── elevation(x,z) ← RECALCULATES ENTIRE CHAIN ABOVE

precipitation(x,z)
├── rawPrecipitation: FBM (2 octaves, freq 1/7500)
└── continents(x,z) ← RECALCULATED AGAIN
```

### Measured Redundancy
| Sampler | Times Recalculated Per Point |
|---------|------------------------------|
| `continents(x,z)` | 33+ times |
| `elevation(x,z)` | 48+ times |
| `rawElevation(x,z)` | Multiple (through elevation) |

---

## Option 1: Combined Climate Stage

### Concept
Replace the three separate stages (temperature → precipitation → elevation) with a single stage that samples a combined `climate(x, z)` value.

### Implementation Approach

**Step A: Create a Combined Climate Sampler**

```yaml
# math/samplers/climate.yml
samplers:
  climate:
    dimensions: 2
    type: EXPRESSION
    expression: |
      # Pre-compute shared values ONCE
      c = continentsValue;
      e = rawElevationValue * (1-flatnessValue)
          * herp(c, continentZero, 0, continentFull, 1);

      # Compute climate factors
      t = rawTemperatureValue - lerp(e, lapseStart, 0, 1, lapseRate);
      p = lerp(c, oceanThreshold, 1, landThreshold, rawPrecipitationValue);

      # Encode into single value: T*100 + P*10 + E
      # Temperature: 12 zones (0-11)
      # Precipitation: 6 levels (0-5)
      # Elevation: 4 variants (0-3)
      tIndex = floor((t + 1) / 2 * 12);
      pIndex = floor((p + 1) / 2 * 6);
      eIndex = floor((e + 1) / 2 * 4);

      (tIndex * 24 + pIndex * 4 + eIndex) / 288  # Normalize to [0, 1]
```

**Step B: Create Combined Stage**

A single REPLACE_LIST stage with 288 entries (12 temp × 6 precip × 4 elevation).

### Pros
- **Single calculation of shared dependencies** - continents, elevation computed once
- **Eliminates redundant recalculations** - massive performance gain
- **Deterministic output** - same biome selection as current system

### Cons
- **Large weighted list** - 288 entries per biome type (e.g., land, coast, ocean, mesa)
- **Complex maintenance** - harder to understand and modify
- **Loss of modularity** - can't easily adjust just temperature or precipitation
- **Requires flattening the existing multi-dimensional logic**

### Estimated Performance Improvement
**~3-5x faster** for the climate distribution phase

---

## Option 2: Simplified Map Topology

### Concept
Redesign the underlying noise functions to be computationally cheaper while maintaining visual quality.

### Current Expensive Operations

| Operation | Cost | Notes |
|-----------|------|-------|
| `rawElevation.mountains` | VERY HIGH | Pseudoerosion + 3-octave FBM |
| `rawElevation.hills` | HIGH | 6-octave FBM |
| `continents` | MEDIUM | 3-octave RIDGED |
| `flatness` | MEDIUM | PROBABILITY + FBM |

### Proposed Simplifications

**A. Simplified Elevation**
```yaml
# Replace complex hills + mountains with single expression
rawElevation:
  type: EXPRESSION
  expression: |
    # Single 4-octave FBM with posterization for mountain ridges
    base = fbm4(x, z);
    ridged = 1 - abs(base * 2);  # Creates ridge effect without Pseudoerosion
    lerp(base, 0.5, base, 1, ridged)  # Blend ridges at high elevations
```

**B. Decoupled Temperature/Precipitation**
```yaml
# Remove elevation dependency from temperature
# Instead, apply altitude effect directly in the stage expression
temperature_stage_sampler:
  type: EXPRESSION
  expression: |
    # Base temperature (no altitude lapse)
    rawTemperature(x, z)
    # Altitude lapse applied inline, not in sampler definition
    - if(applyAltitudeLapse,
        lerp(elevation(x, z), lapseStart, 0, 1, lapseRate),
        0)
```

**C. Simplified Continents**
```yaml
# Use cheaper noise for continental boundaries
continents:
  type: EXPRESSION
  expression: |
    # Replace 3-octave RIDGED with 2-octave + thresholding
    noise = fbm2(x / scale, z / scale);
    # Create continental shapes via threshold
    smoothstep(noise, -0.1, 0.1) * 2 - 1
```

### Pros
- **Maintains existing architecture** - minimal structural changes
- **Easier to tune** - each component can be adjusted independently
- **Preserves modularity** - temperature/precipitation/elevation remain separate
- **Gradual optimization** - can be applied incrementally

### Cons
- **May reduce visual quality** - simpler noise = less natural terrain
- **Still has some redundancy** - multiple stages still sample overlapping functions
- **Requires careful tuning** - must balance speed vs. aesthetics

### Estimated Performance Improvement
**~1.5-2x faster** depending on which simplifications are applied

---

## Option 3: Cache Layer (Recommended Starting Point)

### Concept
Use Terra's built-in CACHE sampler to eliminate redundant calculations without changing the algorithm.

### Implementation

**Step 1: Wrap expensive samplers with CACHE**

```yaml
# math/samplers/continents.yml
samplers:
  continents_cached:
    dimensions: 2
    type: CACHE
    sampler:
      # ... existing continents definition ...
```

**Step 2: Reference cached version everywhere**

```yaml
# math/samplers/elevation.yml
samplers:
  elevation:
    # ...
    samplers:
      continents: $math/samplers/continents.yml:samplers.continents_cached  # Use cached
```

### Key Samplers to Cache
1. **`continents`** - Referenced 33+ times, RIDGED noise is expensive
2. **`rawElevation`** - Complex multi-layer computation
3. **`flatness`** - Used in elevation calculation
4. **`spawnIsland`** - DISTANCE sampler referenced multiple times

### Pros
- **Minimal code changes** - just wrap existing samplers
- **No algorithm changes** - identical output guaranteed
- **Easy to test** - can enable/disable per sampler
- **Stacks with other optimizations** - can combine with Options 1 or 2

### Cons
- **Memory overhead** - 256-entry cache per thread (configurable)
- **Experimental feature** - marked `@Experimental` in Terra
- **May not help in all cases** - depends on access patterns
- **Cache invalidation** - must ensure cache is cleared between chunks

### Estimated Performance Improvement
**~2-3x faster** for redundant calculations

---

## Recommended Approach

### Phase 1: Quick Wins (Option 3) - **IMPLEMENTED**

**Status:** Complete - See `CacheSamplerImplementation.md` for details

Changes made:
1. Added `continentsCached` wrapper to `math/samplers/continents.yml`
2. Added `elevationCached`, `flatnessCached`, `oceanElevationCached` to `math/samplers/elevation.yml`
3. Added `spawnIslandCached` to `math/samplers/spawnIsland.yml`
4. Added `temperatureCached` to `math/samplers/temperature.yml`
5. Added `precipitationCached` to `math/samplers/precipitation.yml`
6. Updated all cross-file references to use cached versions

**Next steps:**
1. Test the pack to verify identical biome distribution
2. Measure performance improvement with Terra profiler
3. Verify visual output is unchanged

### Phase 2: Targeted Simplification (Option 2)
1. Simplify `mountains` calculation (replace Pseudoerosion with cheaper alternative)
2. Reduce FBM octaves in `hills` (6 → 4)
3. Test visual quality vs. performance tradeoff

### Phase 3: Structural Optimization (Option 1) - If Needed
1. Only if Phase 1+2 don't achieve target performance
2. Design combined climate encoding scheme
3. Generate the 288-entry weighted lists programmatically
4. Extensive testing to ensure biome distribution matches original

---

## Cache Sampler Technical Details

From `CacheSampler.java`:

```java
// 2D cache configuration
LoadingCache<DoubleSeededVector2Key, Double> cache = Caffeine
    .newBuilder()
    .initialCapacity(256)
    .maximumSize(256)  // LRU eviction after 256 entries
    .build(this::sampleNoise);
```

**Important Considerations:**
- Cache is **per-thread** (ThreadLocal)
- Size is **fixed at 256** entries for 2D samplers
- Uses **Caffeine** library (high-performance caching)
- Marked **@Experimental** - may change in future Terra versions

**Configuration Example:**
```yaml
samplers:
  continents_cached:
    dimensions: 2
    type: CACHE
    sampler: *continents  # Reference to actual sampler
```

---

## Biome Count Analysis

Understanding the combinatorial explosion:

| Factor | Values | Current Biomes |
|--------|--------|----------------|
| Temperature | 12 zones | ice-cap, tundra, boreal-snowy, boreal-cold, boreal-warm, boreal-hot, temperate-cold, temperate-warm, temperate-hot, tropical-savanna-wet, tropical-monsoon, tropical-rainforest |
| Precipitation | 6 levels | desert, desert-border, semi-arid, mid, mildly-wet, very-wet |
| Elevation | 4 variants | flat, lowlands, midlands, highlands |

**Theoretical Maximum:** 12 × 6 × 4 = **288 combinations**

**Actual Usage:** Many combinations share biome IDs (e.g., `boreal-hot` covers multiple precipitation levels)

This is why a combined approach (Option 1) is complex but could be very efficient.

---

## Appendix: Full Dependency Graph

```
temperature.yml stage
└── temperature(x, z)
    ├── rawTemperature(x, z)
    │   └── FBM (2 octaves)
    └── elevation(x, z)
        ├── rawElevation(x, z)
        │   ├── hills: FBM (6 octaves)
        │   ├── mountains: Pseudoerosion + FBM (3 octaves)
        │   └── mountainMask: PROBABILITY + OPEN_SIMPLEX_2
        ├── flatness(x, z)
        │   └── rawFlatness: PROBABILITY + FBM
        ├── continents(x, z)
        │   ├── RIDGED (3 octaves)
        │   ├── spawnIsland(x, z)
        │   └── spots
        ├── spawnIsland(x, z)
        └── riverTerrainErosion(x, z)

precipitation.yml stage
└── precipitation(x, z)
    ├── rawPrecipitation(x, z)
    │   └── FBM (2 octaves)
    └── continents(x, z)  ← REDUNDANT
        └── [same as above]

elevation.yml stage
├── oceanElevation(x, z)
│   ├── rawElevation(x, z)  ← REDUNDANT
│   └── continents(x, z)    ← REDUNDANT
├── elevation(x, z)          ← REDUNDANT
└── flatness(x, z)           ← REDUNDANT
```

Each stage independently recalculates the entire dependency tree.
