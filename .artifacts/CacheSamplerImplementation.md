# Terra CACHE Sampler Implementation Guide

This document details the implementation of cache wrappers for ORIGEN2's expensive samplers.

## Overview

Terra provides a `CACHE` sampler type that wraps any sampler and caches its results using the Caffeine library. This eliminates redundant calculations when the same coordinate is queried multiple times.

## Technical Details

### Cache Implementation (from Terra source)

**Location:** `Terra/common/addons/config-noise-function/src/main/java/com/dfsek/terra/addons/noise/config/sampler/CacheSampler.java`

```java
public class CacheSampler implements Sampler {
    // Thread-local cache - each generation thread has its own cache
    private final ThreadLocal<Mutable<DoubleSeededVector2Key, LoadingCache<...>>> cache2D;

    public CacheSampler(Sampler sampler, int dimensions) {
        if(dimensions == 2) {
            this.cache2D = ThreadLocal.withInitial(() -> {
                LoadingCache<DoubleSeededVector2Key, Double> cache = Caffeine
                    .newBuilder()
                    .executor(CACHE_EXECUTOR)
                    .scheduler(Scheduler.systemScheduler())
                    .initialCapacity(256)
                    .maximumSize(256)  // LRU eviction
                    .build(this::sampleNoise);
                return Pair.of(new DoubleSeededVector2Key(0, 0, 0), cache).mutable();
            });
        }
    }
}
```

### Key Characteristics

| Property | Value | Notes |
|----------|-------|-------|
| **Cache Size** | 256 entries | Fixed, not configurable |
| **Eviction Policy** | LRU (Least Recently Used) | Via Caffeine library |
| **Thread Safety** | Thread-local | Each thread has independent cache |
| **Cache Key** | (x, z, seed) | Full coordinate + world seed |
| **Dimensions** | 2D or 3D | 3D cache is larger (981504 entries) |
| **Status** | @Experimental | May change in future Terra versions |

### Cache Key Structure

```java
public class DoubleSeededVector2Key {
    public double x;
    public double z;
    public long seed;

    @Override
    public int hashCode() {
        int code = (int) Double.doubleToLongBits(x);
        code = 31 * code + (int) Double.doubleToLongBits(z);
        return 31 * code + (Long.hashCode(seed));
    }
}
```

**Important:** The cache key uses exact double values. This means:
- Two queries at (100.0, 200.0) will share a cache entry
- Two queries at (100.0, 200.0) and (100.0001, 200.0) will NOT share

## Configuration Syntax

```yaml
samplers:
  # Define the raw (expensive) sampler
  mySampler: &mySampler
    type: EXPRESSION
    expression: expensiveCalculation(x, z)
    # ... configuration ...

  # Wrap it in a cache
  mySamplerCached:
    dimensions: 2
    type: CACHE
    sampler: *mySampler  # Reference the raw sampler
```

## Changes Made to ORIGEN2

### Files Modified

| File | Changes |
|------|---------|
| `math/samplers/continents.yml` | Added `continentsCached` wrapper, updated internal references |
| `math/samplers/elevation.yml` | Added `elevationCached`, `flatnessCached`, `oceanElevationCached` |
| `math/samplers/precipitation.yml` | Added `precipitationCached`, updated continents reference |
| `math/samplers/temperature.yml` | Added `temperatureCached`, updated elevation reference |
| `math/samplers/spawnIsland.yml` | Added `spawnIslandCached` |
| `math/samplers/spots.yml` | Updated elevation references to use cached version |

### Cache Dependency Chain

```
spawnIslandCached
    ↓
continentsCached (uses spawnIslandCached)
    ↓
elevationCached (uses continentsCached, spawnIslandCached)
    ↓
├── temperatureCached (uses elevationCached)
├── precipitationCached (uses continentsCached)
└── oceanElevationCached (uses continentsCached)
```

### Summary of Added Cache Samplers

| Sampler | Purpose | Dependencies |
|---------|---------|--------------|
| `spawnIslandCached` | Spawn point island shape | None |
| `continentsCached` | Ocean/land boundaries | spawnIslandCached, spots |
| `flatnessCached` | Terrain flatness factor | rawFlatness |
| `elevationCached` | Main terrain height | rawElevation, flatnessCached, continentsCached |
| `oceanElevationCached` | Ocean floor depth | rawElevation, continentsCached |
| `temperatureCached` | Temperature zones | rawTemperature, elevationCached |
| `precipitationCached` | Precipitation levels | rawPrecipitation, continentsCached |

## Expected Performance Impact

### Before Caching
At each biome point, the pipeline calculated:
- `continents(x,z)` - **33+ times**
- `elevation(x,z)` - **48+ times**
- Each calculation triggered the full dependency chain

### After Caching
- First query: Full calculation + cache store
- Subsequent queries at same coordinate: Cache hit (O(1) lookup)

**Estimated improvement:** 2-3x faster for the climate distribution phase

### When Cache Helps Most
1. **Sequential stage processing** - Temperature, precipitation, elevation stages all query the same coordinate
2. **Internal sampler dependencies** - elevation uses continents, temperature uses elevation
3. **Kernel/border operations** - continentBorder samples nearby coordinates

### When Cache May Not Help
1. **Sparse sampling** - If >256 unique coordinates are sampled before returning to the same one
2. **Different coordinates** - Cache is coordinate-exact, no interpolation
3. **Across chunks** - Each chunk processes new coordinates

## Usage Guidelines

### Do Cache
- Expensive samplers (multi-octave FBM, Pseudoerosion, CELLULAR, RIDGED)
- Frequently referenced samplers (continents, elevation)
- Samplers with complex dependency chains

### Don't Cache
- Simple samplers (single noise lookup)
- Samplers only used once per coordinate
- Samplers with high coordinate variation (domain-warped with high amplitude)

### Testing Recommendations

1. **Verify identical output** - Compare biome distribution before/after caching
2. **Profile performance** - Use Terra's `/terra profiler` command
3. **Monitor memory** - Each cached sampler adds 256 entries × thread count
4. **Test edge cases** - Spawn island, continent borders, ocean transitions

## Limitations & Caveats

1. **Experimental Feature** - The CACHE sampler is marked `@Experimental` in Terra source
2. **Fixed Cache Size** - Cannot adjust the 256-entry limit without modifying Terra
3. **No Cache Warming** - Cache starts empty each generation thread
4. **Coordinate Precision** - Double comparison may cause rare cache misses on boundary coordinates
5. **Memory Overhead** - 256 entries × ~32 bytes × number of cached samplers × threads

## Future Considerations

1. **Monitor Terra Updates** - Cache implementation may change
2. **Consider Combined Approach** - If caching alone insufficient, combine with simplified topology
3. **Profile Regularly** - As biome distribution evolves, cache effectiveness may change
