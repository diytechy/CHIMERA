# Terra Weighted List Distribution: How Thresholds Are Computed

This document explains how Terra's biome pipeline computes thresholds for weighted lists in `REPLACE_LIST` stages.

---

## Quick Reference: Key Code Locations

| Component | File | Key Lines |
|-----------|------|-----------|
| **Weight → Array expansion** | `ProbabilityCollection.java:34-43` | `add(E item, int probability)` method |
| **Noise → Index conversion** | `ProbabilityCollection.java:74-77` | `get(Sampler n, double x, double z, long seed)` method |
| **normalizeIndex formula** | Seismic `NormalizationFunctions.java` | `((val + 1) / 2) * size`, clamped to [0, size-1] |
| **REPLACE_LIST stage** | `ReplaceListStage.java:38-48` | `apply(ViewPoint)` method |
| **YAML list parsing** | `ProbabilityCollectionLoader.java:54-73` | Parses `[{item: weight}, ...]` format |
| **LINEAR normalizer** | `LinearNormalizerTemplate.java:18-28` | **min/max are REQUIRED** (no defaults) |
| **LINEAR_MAP normalizer** | `LinearMapNormalizerTemplate.java:12-30` | **from defaults to [-1, 1]** |

---

## Overview

When you configure a weighted list like this in a Terra config:

```yaml
- type: REPLACE_LIST
  sampler:
    type: EXPRESSION
    expression: temperature(x, z)
  default-from: land
  default-to:
    - ice-cap: 1
    - tundra: 1
    - boreal-snowy: 1
    - boreal-cold: 1
    - boreal-warm: 1
    - boreal-hot: 1
    - temperate-cold: 1
    - temperate-warm: 3
    - temperate-hot: 2
    - tropical-savanna-wet: 1
    - tropical-monsoon: 1
    - tropical-rainforest: 4
```

Terra automatically computes thresholds to divide the noise range into segments proportional to each weight.

## The Core Algorithm

### Step 1: Weight Expansion (ProbabilityCollection.java)

Terra creates an internal array where each biome is repeated according to its weight. For the temperature example above:

| Biome | Weight | Array Indices |
|-------|--------|---------------|
| ice-cap | 1 | [0] |
| tundra | 1 | [1] |
| boreal-snowy | 1 | [2] |
| boreal-cold | 1 | [3] |
| boreal-warm | 1 | [4] |
| boreal-hot | 1 | [5] |
| temperate-cold | 1 | [6] |
| temperate-warm | 3 | [7, 8, 9] |
| temperate-hot | 2 | [10, 11] |
| tropical-savanna-wet | 1 | [12] |
| tropical-monsoon | 1 | [13] |
| tropical-rainforest | 4 | [14, 15, 16, 17] |

**Total array size = 18** (sum of all weights)

### Step 2: Noise Value Normalization (NormalizationFunctions.java)

The noise sampler (e.g., `temperature(x, z)`) typically outputs values in the **[-1, 1]** range.

The `normalizeIndex` function converts this to an array index using:

```java
index = ((noiseValue + 1.0) / 2.0) * arraySize
// Clamped to [0, arraySize - 1]
```

**Mathematical breakdown:**
1. `noiseValue + 1.0` shifts [-1, 1] to [0, 2]
2. `/ 2.0` scales [0, 2] to [0, 1]
3. `* arraySize` scales [0, 1] to [0, arraySize]
4. Result is clamped to valid array bounds

### Step 3: Implied Threshold Boundaries

Given the formula, each array index corresponds to a noise range:

| Index | Noise Range |
|-------|-------------|
| 0 | [-1.000, -0.889) |
| 1 | [-0.889, -0.778) |
| 2 | [-0.778, -0.667) |
| ... | ... |
| 17 | [0.889, 1.000] |

Each segment has width = `2.0 / arraySize = 2.0 / 18 = 0.111`

## Threshold Calculation for Temperature Example

For the 18-element array (sum of weights = 1+1+1+1+1+1+1+3+2+1+1+4 = 18):

| Biome | Weight | Cumulative | Noise Threshold Range | Percentage |
|-------|--------|------------|----------------------|------------|
| ice-cap | 1 | 0-1 | [-1.000, -0.889) | 5.56% |
| tundra | 1 | 1-2 | [-0.889, -0.778) | 5.56% |
| boreal-snowy | 1 | 2-3 | [-0.778, -0.667) | 5.56% |
| boreal-cold | 1 | 3-4 | [-0.667, -0.556) | 5.56% |
| boreal-warm | 1 | 4-5 | [-0.556, -0.444) | 5.56% |
| boreal-hot | 1 | 5-6 | [-0.444, -0.333) | 5.56% |
| temperate-cold | 1 | 6-7 | [-0.333, -0.222) | 5.56% |
| **temperate-warm** | **3** | 7-10 | **[-0.222, 0.111)** | **16.67%** |
| **temperate-hot** | **2** | 10-12 | **[0.111, 0.333)** | **11.11%** |
| tropical-savanna-wet | 1 | 12-13 | [0.333, 0.444) | 5.56% |
| tropical-monsoon | 1 | 13-14 | [0.444, 0.556) | 5.56% |
| **tropical-rainforest** | **4** | 14-18 | **[0.556, 1.000]** | **22.22%** |

**Key insight**: Biomes with higher weights occupy larger noise ranges.

## The Normalize Flag

The `normalize` configuration allows you to transform the noise values **before** they reach the distribution algorithm.

### What "Automatic Threshold Determination" Really Means

The Terra documentation states that thresholds are "automatically determined." This refers to **two things**:

1. **Thresholds are derived from weights** - You never explicitly specify threshold values like `-0.5` or `0.3`. Instead, the system calculates them from the weight proportions.

2. **The noise range is assumed to be [-1, 1]** - The `normalizeIndex` function expects input in this range. This is the "automatic" assumption.

**There is NO automatic detection of the actual noise range.** If your noise function outputs a different range, you must use a normalizer.

### Normalizer Default Values

**LINEAR Normalizer** (`LinearNormalizerTemplate.java:18-28`):
```java
@Value("max")
private @Meta double max;  // NO @Default - REQUIRED

@Value("min")
private @Meta double min;  // NO @Default - REQUIRED
```
**min and max are REQUIRED** - there are no defaults. The config will fail to load without them.

**LINEAR_MAP Normalizer** (`LinearMapNormalizerTemplate.java:12-30`):
```java
@Value("from.a")
@Default
private @Meta double aFrom = -1;  // Default: -1

@Value("from.b")
@Default
private @Meta double bFrom = 1;   // Default: 1

@Value("to.a")
private @Meta double aTo;         // REQUIRED

@Value("to.b")
private @Meta double bTo;         // REQUIRED
```
**from range defaults to [-1, 1]**, but the **to range is REQUIRED**.

### Available Normalizers (NoiseAddon.java lines 107-114)

| Type | Purpose | Configuration |
|------|---------|---------------|
| `LINEAR` | Maps [min, max] to [-1, 1] | `normalize: { type: LINEAR, min: -1, max: 1 }` |
| `LINEAR_MAP` | Maps [aFrom, aTo] to [bFrom, bTo] | More flexible range mapping |
| `CLAMP` | Clamps to [min, max] | Prevents out-of-range values |
| `NORMAL` | Gaussian/normal distribution | Statistical normalization |
| `PROBABILITY` | Converts to probability [0, 1] | Cumulative distribution |
| `SCALE` | Multiplies by a scale factor | `normalize: { type: SCALE, scale: 2.0 }` |
| `POSTERIZATION` | Quantizes to discrete levels | Creates banding effects |
| `CUBIC_SPLINE` | Smooth spline interpolation | Non-linear remapping |

### Example: Linear Normalizer

```yaml
sampler:
  type: EXPRESSION
  expression: temperature(x, z)
  normalize:
    type: LINEAR
    min: -0.5
    max: 0.5
```

This normalizer:
1. Takes the raw noise output (assumed to be in [-0.5, 0.5])
2. Remaps it linearly to [0, 1]
3. The ProbabilityCollection then uses this [0, 1] value for indexing

**Formula**: `normalized = (value - min) / (max - min)`

### How Normalize Affects Distribution

**Without normalization**: The system assumes noise is [-1, 1] and uses `((val + 1) / 2) * size`

**With LINEAR normalization**: The system first maps [configuredMin, configuredMax] to [0, 1], then uses that directly

**Effect**: If your noise function outputs a different range (e.g., [-0.5, 0.5]), normalizing ensures the full weight distribution is utilized.

## Complete Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONFIGURATION                                 │
├─────────────────────────────────────────────────────────────────┤
│  sampler: temperature(x, z)                                     │
│  default-to: [{ice-cap: 1}, {tundra: 1}, ..., {rainforest: 4}] │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 1: BUILD PROBABILITY ARRAY                    │
├─────────────────────────────────────────────────────────────────┤
│  [ice-cap, tundra, ..., rainforest, rainforest, rainforest,    │
│   rainforest]                                                   │
│  Array size = 18 (sum of all weights)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 2: SAMPLE NOISE AT (x, z)                     │
├─────────────────────────────────────────────────────────────────┤
│  noiseValue = temperature(x, z)  // e.g., returns 0.3          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 3: (OPTIONAL) APPLY NORMALIZER                     │
├─────────────────────────────────────────────────────────────────┤
│  If normalize config exists:                                    │
│    normalizedValue = normalizer.apply(noiseValue)              │
│  Else:                                                          │
│    normalizedValue = noiseValue (assumed [-1, 1])              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 4: COMPUTE ARRAY INDEX                        │
├─────────────────────────────────────────────────────────────────┤
│  index = ((normalizedValue + 1) / 2) * 18                      │
│  index = ((0.3 + 1) / 2) * 18 = 11.7 → 11                      │
│  index = clamp(index, 0, 17)                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 5: RETURN BIOME                               │
├─────────────────────────────────────────────────────────────────┤
│  array[11] = temperate-hot                                      │
│  Result: This location gets temperate-hot biome                 │
└─────────────────────────────────────────────────────────────────┘
```

## Key Source Files Reference

| File | Location | Purpose |
|------|----------|---------|
| `ProbabilityCollection.java` | `Terra/common/api/src/main/java/com/dfsek/terra/api/util/collection/` | Core weighted distribution container (lines 34-77) |
| `ReplaceListStage.java` | `Terra/common/addons/biome-provider-pipeline/src/main/java/.../stage/mutators/` | REPLACE_LIST stage implementation (lines 38-48) |
| `NormalizationFunctions.java` | Seismic library | `normalizeIndex` formula: `((val + 1) / 2) * size` |
| `LinearNormalizerTemplate.java` | `Terra/common/addons/config-noise-function/src/main/java/.../normalizer/` | LINEAR normalizer config (lines 18-28) |
| `NoiseAddon.java` | `Terra/common/addons/config-noise-function/src/main/java/.../` | Registers all normalizer types (lines 107-114) |
| `ProbabilityCollectionLoader.java` | `Terra/common/implementation/base/src/main/java/com/dfsek/terra/config/loaders/` | YAML `[{item: weight}]` parsing (lines 54-73) |

---

## Detailed Code Excerpts

### 1. Weight Expansion (`ProbabilityCollection.java:34-43`)

```java
public ProbabilityCollection<E> add(E item, int probability) {
    if(!cont.containsKey(item)) size++;
    cont.computeIfAbsent(item, i -> new MutableInteger(0)).increment();
    int oldLength = array.length;
    Object[] newArray = new Object[array.length + probability];
    System.arraycopy(array, 0, newArray, 0, array.length); // Expand array.
    array = newArray;
    for(int i = oldLength; i < array.length; i++) array[i] = item;  // Fill with item
    return this;
}
```

### 2. Noise-to-Index Conversion (`ProbabilityCollection.java:74-77`)

```java
public E get(Sampler n, double x, double z, long seed) {
    if(array.length == 0) return null;
    return (E) array[(int) NormalizationFunctions.normalizeIndex(n.getSample(seed, x, z), array.length)];
}
```

### 3. normalizeIndex Formula (Seismic `NormalizationFunctions.java`)

```java
// Converts noise value [-1, 1] to array index [0, size-1]
public static int normalizeIndex(double val, int size) {
    return Math.max(Math.min((int) (((val + 1D) / 2D) * size), size - 1), 0);
}
```

### 4. LINEAR Normalizer Formula (Seismic `LinearNormalizer.java`)

```java
// Maps [min, max] to [-1, 1]
@Override
protected double normalize(double in) {
    return (in - min) * (2 / (max - min)) - 1;
}
```

### 5. REPLACE_LIST Stage Application (`ReplaceListStage.java:38-48`)

```java
@Override
public PipelineBiome apply(BiomeChunkImpl.ViewPoint viewPoint) {
    PipelineBiome center = viewPoint.getBiome();
    if(replace.containsKey(center)) {
        PipelineBiome biome = replace.get(center).get(sampler, viewPoint.worldX(), viewPoint.worldZ(), viewPoint.worldSeed());
        return biome.isSelf() ? viewPoint.getBiome() : biome;
    }
    if(viewPoint.getBiome().getTags().contains(defaultTag)) {
        PipelineBiome biome = replaceDefault.get(sampler, viewPoint.worldX(), viewPoint.worldZ(), viewPoint.worldSeed());
        return biome.isSelf() ? viewPoint.getBiome() : biome;
    }
    return center;
}
```

### 6. YAML Weighted List Parsing (`ProbabilityCollectionLoader.java:54-73`)

```java
// Parses: [{biome1: 1}, {biome2: 3}, ...]
} else if(o instanceof List) {
    List<Map<Object, Object>> list = (List<Map<Object, Object>>) o;
    if(list.size() == 1) {
        Map<Object, Object> map = list.getFirst();
        if(map.size() == 1) {
            for(Object value : map.keySet()) {
                return new ProbabilityCollection.Singleton<>(configLoader.loadType(generic, value, depthTracker));
            }
        }
    }
    for(int i = 0; i < list.size(); i++) {
        Map<Object, Object> map = list.get(i);
        for(Entry<Object, Object> entry : map.entrySet()) {
            if(entry.getValue() == null) throw new LoadException("No probability defined for entry \"" + entry.getKey() + "\"",
                depthTracker);
            Object val = configLoader.loadType(generic, entry.getKey(), depthTracker.index(i).entry((String) entry.getKey()));
            collection.add(val,
                configLoader.loadType(Integer.class, entry.getValue(), depthTracker.entry((String) entry.getKey())));
        }
    }
}
```

---

## Summary

1. **Weights become array repetitions**: A weight of 3 means 3 copies in the internal array
2. **Noise range is [-1, 1]** by default (hardcoded assumption in `normalizeIndex`)
3. **Index formula**: `index = ((noise + 1) / 2) * totalWeight`
4. **Thresholds are implicit**: They're evenly distributed across the noise range based on weight proportions
5. **Normalize flag**: Transforms noise values before distribution, useful when:
   - Your noise function outputs a different range than [-1, 1]
   - You want to remap values non-linearly (e.g., with CUBIC_SPLINE)
   - You want to clamp extreme values
6. **No automatic range detection**: The system assumes [-1, 1]. If your sampler outputs something else, you MUST use a normalizer
