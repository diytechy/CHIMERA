# Terra Sampler Configuration & Optimization Reference

A practical guide for pack authors and AI agents writing Terra YAML configurations.
Covers how sampler instances are created, shared, and cached — and how configuration
layout affects performance.

---

## Table of Contents

1. [How Samplers Work](#1-how-samplers-work)
2. [Instance Sharing Rules](#2-instance-sharing-rules)
3. [Caching Layers](#3-caching-layers)
4. [The CACHE Sampler Wrapper](#4-the-cache-sampler-wrapper) — parameters: `exp`, `int`, `dimensions`
5. [Multi-Value Samplers](#5-multi-value-samplers)
6. [Available Sampler Types](#6-available-sampler-types)
7. [Optimization Guidelines](#7-optimization-guidelines)
8. [Common Patterns with YAML Examples](#8-common-patterns-with-yaml-examples)
9. [Source File Reference](#9-source-file-reference)

---

## 1. How Samplers Work

A sampler is a **stateless pure function**: given a seed and coordinates, it always
returns the same `double` value. Samplers hold their configuration parameters (frequency,
octaves, etc.) as immutable fields set at construction time.

```
Sampler.getSample(seed, x, z)     -> double   (2D)
Sampler.getSample(seed, x, y, z)  -> double   (3D)
```

Because samplers are stateless:
- Sharing an instance between callers is safe — no concurrency issues.
- Sharing does NOT provide caching. Calling `getSample(seed, 5, 10)` twice on the
  same instance computes the noise twice unless an explicit cache is in place.
- Each sampler tree (a root sampler and all its nested child samplers) is independent.
  Wrapping the same noise type in two different normalizers produces two separate
  computation trees.

---

## 2. Instance Sharing Rules

### 2.1 Inline Definitions — Separate Instances

Every sampler block defined directly in a YAML file creates a **new, independent instance**.

```yaml
# biome_a.yml
terrain:
  type: OPEN_SIMPLEX_2
  frequency: 0.01

# biome_b.yml
terrain:
  type: OPEN_SIMPLEX_2     # Same type and settings, but a DIFFERENT object
  frequency: 0.01
```

Even with identical parameters, these are two separate `OpenSimplex2Sampler` objects.
Each inline definition goes through the full create-template-load-instantiate pipeline
(`GenericTemplateSupplierLoader.load()`), producing a fresh instance every time.

YAML anchors (`&name` / `*name`) also create separate instances — SnakeYAML expands
the alias into a copy of the map values before Terra's config system sees it, and the
config loader instantiates independently at each reference site.

**Anchor scope:** Anchors work anywhere within the **same** `.yml` file. Each file is
parsed independently by SnakeYAML (`YamlAddon` creates a separate `YamlConfiguration`
per file), so an anchor defined in one file cannot be aliased in a different file.
For cross-file value references, use Terra's Meta syntax: `<<: $other-file.yml:key`.

```yaml
# Within a single .yml file — anchors work at any nesting level
base-noise: &base              # Anchor defined at root level
  type: FBM
  octaves: 4
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.01

terrain:
  type: EXPRESSION
  dimensions: 2
  expression: "a(x, z) * 0.7 + b(x, z) * 0.3"
  samplers:
    a:
      <<: *base                # Alias works — same file, resolved by SnakeYAML
    b:
      <<: *base                # Also works — but creates a SEPARATE sampler instance
```

### 2.2 Pack-Level Named Samplers — Shared Instance

Samplers defined in the pack manifest's `samplers:` section are loaded **once** into
a shared map. When multiple EXPRESSION samplers reference the same pack-level sampler
by name, they all use the **same underlying object**.

```yaml
# In pack.yml
samplers:
  continentNoise:           # <-- loaded once into the packSamplers map
    dimensions: 2
    type: FBM
    octaves: 4
    sampler:
      type: OPEN_SIMPLEX_2
      frequency: 0.003
```

```yaml
# In any EXPRESSION sampler (in any YAML file in this pack)
type: EXPRESSION
expression: "continentNoise(x, z) * 64 + 64"
# continentNoise here is the SAME object as in every other expression
# that references it. No duplicate memory, no duplicate construction.
```

**What this means for optimization:**
- Defining frequently-reused noise at the pack level saves memory (one object vs many).
- It does NOT save computation — calling `continentNoise(x, z)` in two different
  expressions at the same coordinates evaluates the noise twice.
- To also save computation, wrap the pack-level sampler with `type: CACHE` (see
  Section 4).

### 2.3 Summary Table

| Scenario                                          | Same Object? | Computation Shared? |
|---------------------------------------------------|:------------:|:-------------------:|
| Same type defined inline in 2 different YAML files | No          | No                  |
| YAML anchor `*name` referencing same definition    | No          | No                  |
| Pack-level sampler referenced by name in EXPRESSION| **Yes**     | No (without CACHE)  |
| Pack-level sampler wrapped in CACHE                | **Yes**     | **Yes**             |

---

## 3. Caching Layers

Terra has two distinct caching mechanisms. Understanding which one does what is
critical for optimization.

### 3.1 SamplerProvider — Chunk-Level Object Cache (Automatic)

**What it caches:** Entire `Sampler3D` chunk objects — precomputed noise grids for a
given chunk coordinate, seed, and height range.

**When it activates:** Automatically during chunk generation in `NoiseChunkGenerator3D`.
Every call goes through `SamplerProvider`, which checks if the chunk's noise grid
has already been computed.

**What it does NOT cache:** Individual `getSample()` evaluations. This cache stores
the compiled chunk object so that when a chunk is revisited (e.g., during decoration
after initial generation), the noise doesn't need to be recomputed from scratch.

**Configuration** (in `config.yml`):
```yaml
cache:
  structure: 32      # Structure cache size
  sampler: 1024      # Sampler3D chunk cache size (default)
  biome-provider: 32 # Biome provider cache size
```

Increase `cache.sampler` if you have enough memory and want to keep more chunks'
noise grids cached. Each entry holds a precomputed noise grid for one chunk column.

### 3.2 CacheSampler — Per-Evaluation Result Cache (Explicit)

**What it caches:** Individual `getSample(seed, x, z)` return values.

**When it activates:** Only when you explicitly wrap a sampler with `type: CACHE`
in your YAML configuration.

**What it does:** Stores the result of each evaluation keyed by (seed, x, z) or
(seed, x, y, z). If the same coordinates are queried again, the cached result is
returned without recomputing the noise.

**This is the cache you use to prevent redundant calculations** when the same sampler
is evaluated at the same coordinates from multiple call sites.

See Section 4 for full details.

---

## 4. The CACHE Sampler Wrapper

### 4.1 What It Does

`type: CACHE` wraps any sampler and memoizes its results per-thread. When the same
(seed, x, z) or (seed, x, y, z) coordinates are queried:
- **Cache hit:** Returns the stored value immediately (no noise computation).
- **Cache miss:** Evaluates the underlying sampler, stores the result, returns it.

### 4.2 YAML Syntax

```yaml
type: CACHE
dimensions: 2          # 2 for 2D cache, 3 for 3D cache
int: false             # Round coordinates to int32 (default: false)
exp: 8                 # Cache size = 2^exp slots (default: 8 for 2D, 17 for 3D)
sampler:
  type: OPEN_SIMPLEX_2
  frequency: 0.01
```

All parameters are optional. A minimal CACHE block only needs `sampler`:

```yaml
type: CACHE
dimensions: 2
sampler:
  type: FBM
  octaves: 6
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.005
```

### 4.3 The `exp` Parameter

`exp` controls cache size as a power of two: the cache holds `2^exp` slots.

| exp | Slots   | 2D memory/thread | 2D + int | 3D memory/thread | 3D + int |
|-----|---------|------------------|----------|------------------|----------|
| 0   | 1       | negligible       | —        | negligible       | —        |
| 4   | 16      | ~1 KB            | —        | ~1 KB            | —        |
| 8   | 256     | ~8 KB            | ~6 KB    | —                | —        |
| 12  | 4,096   | ~128 KB          | ~96 KB   | —                | —        |
| 17  | 131,072 | —                | —        | ~5 MB            | ~3.5 MB  |
| 20  | 1M      | ~32 MB           | ~24 MB   | ~40 MB           | ~28 MB   |

**Defaults:** `exp: 8` for 2D (256 slots), `exp: 17` for 3D (131,072 slots).

**Valid range:** 0–20. Values outside this range produce a load error.

**The within-chunk zero-collision guarantee** (all 256 positions in a 16×16 chunk
mapping to distinct slots) holds when `exp >= 8` for 2D and `exp >= 13` for 3D.
At lower `exp` values the cache still works correctly but has more collisions.

**When to tune `exp`:**
- **Increase** if a 3D sampler is called many times per chunk at distinct coordinates
  and you observe high miss rates. A full chunk column has 16×16×384 = 98,304 unique
  3D points — well above the default 131,072 for 3D.
- **Decrease** if memory is a concern (especially for 3D caches on servers with many
  concurrent chunk-gen threads). A 3D CACHE with `exp: 13` (8,192 slots, ~320 KB)
  covers one full chunk column for x,z while giving up inter-chunk reuse.
- **Leave at default** for most 2D use cases; 256 slots covers a full 16×16 chunk
  with zero collisions and uses only ~8 KB per thread.

### 4.4 The `int` Parameter

When `int: true`, CacheSampler rounds all input coordinates to the nearest integer
(saturating at int32 bounds) **before** both cache lookup and sampler evaluation.
This has two effects:

1. **Higher cache hit rate:** Fractional coordinates that round to the same integer
   (e.g., 5.1 and 5.4 both become 5) produce cache hits instead of misses. This is
   especially beneficial when coordinates have sub-integer jitter or interpolation.

2. **Reduced memory:** Coordinate keys are stored as `int[]` (4 bytes each) instead
   of `double[]` (8 bytes each), saving 4 bytes per coordinate per cache slot.

**Trade-off:** All sub-integer coordinate variation is lost. Two queries at (5.1, 10.7)
and (5.4, 10.2) return the same value — the noise at (5, 11). Use `int: true` only
when integer-resolution noise is acceptable (terrain generation, biome selection, etc.).

The cached value is still stored as a `double` — only the coordinate keys are narrowed.

### 4.5 Implementation Details

The cache uses a **direct-mapped** design with parallel primitive arrays (no object
allocation, no autoboxing). One cache instance per thread via `ThreadLocal`.

**Hash design:** The lower 8 bits of the hash index encode chunk-local x and z
coordinates: `((int)x & 0xF) | (((int)z & 0xF) << 4)`. When `exp >= 8`, all 256
positions within a 16×16 chunk map to **distinct** cache slots — zero collisions
within any single chunk. Higher bits encode chunk identity across the wider table.

**Conflict resolution:** Direct-mapped (like a CPU L1 cache). When two different
coordinates hash to the same slot, the newer entry overwrites the older. There is no
eviction tracking, no LRU, no frequency counting. For chunk generation's sequential
spatial access pattern, this is optimal — the most recently computed nearby coordinates
are what you want cached, and that's what naturally stays.

**Thread safety:** Each thread has its own cache arrays via `ThreadLocal`. No locking,
no contention. Total memory = `(number of CACHE samplers) × (server chunk-gen threads)
× (per-thread array size)`. See the `exp` table in Section 4.3 for per-thread sizes.

### 4.6 When to Use CACHE

Use `type: CACHE` when:
- A sampler is **evaluated at the same coordinates from multiple call sites** (e.g.,
  the same pack-level sampler referenced in several expressions that all process the
  same chunk).
- The sampler is **computationally expensive** (high-octave FBM, deep expression
  trees, PSEUDOEROSION).
- The sampler uses **integer coordinates** (standard chunk generation). The hash
  is optimized for integer values.

Do NOT use `type: CACHE` when:
- The sampler is only evaluated once per coordinate (no redundant calls to eliminate).
- The sampler is trivially cheap (e.g., `CONSTANT`, simple `WHITE_NOISE`).
- The sampler is only used in 3D and memory is tight (default ~5 MB per thread per
  cached sampler; reduce with a lower `exp` value or `int: true`).

### 4.7 CACHE at the Pack Level

The most impactful use of CACHE is wrapping pack-level samplers. Since pack-level
samplers are already shared instances (Section 2.2), adding CACHE means that any
expression referencing the sampler by name benefits from the cached results of every
other expression that already evaluated it at those coordinates.

```yaml
# In pack.yml — the shared + cached pattern
samplers:
  continentNoise:
    dimensions: 2
    type: CACHE               # <-- wrap the entire tree
    sampler:
      type: FBM
      octaves: 6
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.003

  erosionValue:
    dimensions: 2
    type: CACHE
    sampler:
      type: PSEUDOEROSION
      frequency: 1
      octaves: 4
      strength: 0.04
      erosion-frequency: 0.02
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.02
```

Now every expression in the pack that calls `continentNoise(x, z)` or
`erosionValue(x, z)` shares both the same instance AND the same cached results.

### 4.8 Caching Inline Samplers

You can also cache inline samplers, but the cache is only useful within that single
sampler tree. This is mainly valuable for self-referencing scenarios where the same
sub-sampler is evaluated multiple times in one computation:

```yaml
type: EXPRESSION
dimensions: 2
expression: "base(x, z) * 0.7 + base(x + 100, z + 100) * 0.3"
samplers:
  base:
    type: CACHE          # Caches both the (x,z) and (x+100,z+100) evaluations
    dimensions: 2
    sampler:
      type: FBM
      octaves: 4
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.01
```

Without CACHE here, `base` would be computed twice per coordinate (once at `(x,z)`
and once at `(x+100, z+100)`). With CACHE, the second call at `(x+100, z+100)` is
a fresh computation, but if this expression is evaluated at shifted coordinates later,
those earlier results may still be in the cache.

### 4.9 Expression Functions and Repeated Evaluation

When a function is defined in the `functions:` section of an EXPRESSION sampler
(or at the pack level), the function body is **compiled once** into an AST. The
function object is cached globally by its `FunctionTemplate` via a static map in
`UserDefinedFunction`. However, each time the function appears in an expression
string, it is **fully evaluated** — there is no automatic memoization of results.

```yaml
type: EXPRESSION
dimensions: 2
expression: "myFunc(x, z) + myFunc(x+10, z+10) + myFunc(x, z)"
functions:
  myFunc:
    arguments: [x, z]
    expression: "expensiveNoise(x, z) * 2"
```

When this expression is evaluated at coordinates (100, 200):

| Call                  | Arguments   | Sampler Evaluation           |
|-----------------------|-------------|------------------------------|
| `myFunc(x, z)`        | (100, 200)  | `expensiveNoise(100, 200)`   |
| `myFunc(x+10, z+10)`  | (110, 210)  | `expensiveNoise(110, 210)`   |
| `myFunc(x, z)`        | (100, 200)  | `expensiveNoise(100, 200)` — **redundant** |

The first and third calls compute identical results. The same applies to pack-level
samplers referenced by name in expressions — calling `myNoise(x, z)` three times
in the same expression evaluates the sampler three times.

**To eliminate redundant evaluations**, wrap the sampler with `type: CACHE`:

```yaml
# Pack-level or inline — CACHE prevents recomputation at same coordinates
samplers:
  expensiveNoise:
    dimensions: 2
    type: CACHE
    sampler:
      type: FBM
      octaves: 6
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.005
```

With CACHE, the third call above becomes a cache hit from the first call's result.
This also works across different expressions — if two separate EXPRESSION samplers
both call the same pack-level cached sampler at the same coordinates during the
same chunk's generation, the second expression benefits from the first's cached
results.

---

## 5. Multi-Value Samplers

Most samplers return a single `double`. Two patterns exist for extracting single
values from sources that produce multiple values.

### 5.1 DerivativeSampler — Noise + Partial Derivatives

Some noise types compute partial derivatives alongside the noise value:

- **2D:** `double[3]` = `[value, dX, dZ]`
- **3D:** `double[4]` = `[value, dX, dY, dZ]`

**Derivative-capable types:** `OPEN_SIMPLEX_2`, `OPEN_SIMPLEX_2S`, `PERLIN`, `SIMPLEX`
**Conditionally derivative:** `FBM` (only if its input sampler is derivative-capable)

When used as a regular sampler (the normal case), only the noise value is returned.
Derivatives are only computed when explicitly requested by a consumer that requires
them, such as `PSEUDOEROSION`:

```yaml
type: PSEUDOEROSION
sampler:
  type: OPEN_SIMPLEX_2     # Must be derivative-capable
  frequency: 0.02
```

No special handling is needed to "extract" the noise value — it's the default behavior.

### 5.2 ColorSampler + CHANNEL — Extracting from Packed ARGB

`ColorSampler` returns a packed ARGB integer (4 values in one int). The `CHANNEL`
sampler type extracts a single channel as a standard `double`:

```yaml
type: CHANNEL
channel: RED              # RED, GREEN, BLUE, ALPHA, or GRAYSCALE
normalize: true           # Map 0-255 to [-1, 1] (default: true)
premultiply: false        # Multiply RGB by alpha first (default: false)
color-sampler:
  type: SINGLE_IMAGE
  image: heightmap.png
```

This allows a single image to encode multiple data layers in its color channels.

---

## 6. Available Sampler Types

All sampler types registered in `NoiseAddon.java`:

| Category        | Types |
|-----------------|-------|
| **Noise**       | `OPEN_SIMPLEX_2`, `OPEN_SIMPLEX_2S`, `PERLIN`, `SIMPLEX`, `GABOR`, `VALUE`, `VALUE_CUBIC`, `CELLULAR` |
| **Fractal**     | `FBM`, `PING_PONG`, `RIDGED` |
| **Erosion**     | `PSEUDOEROSION` |
| **Random**      | `WHITE_NOISE`, `POSITIVE_WHITE_NOISE`, `GAUSSIAN` |
| **Normalizer**  | `LINEAR`, `LINEAR_MAP`, `NORMAL`, `CLAMP`, `PROBABILITY`, `SCALE`, `POSTERIZATION`, `CUBIC_SPLINE` |
| **Arithmetic**  | `ADD`, `SUB`, `MUL`, `DIV`, `MAX`, `MIN` |
| **Domain**      | `DOMAIN_WARP`, `TRANSLATE` |
| **Expression**  | `EXPRESSION`, `EXPRESSION_NORMALIZER` |
| **Utility**     | `CONSTANT`, `DISTANCE`, `KERNEL`, `LINEAR_HEIGHTMAP`, `CACHE` |
| **Image**       | `CHANNEL` (from library-image addon) |

Every type accepts `dimensions: 2` or `3` (default: `2`).

---

## 7. Optimization Guidelines

### 7.1 Reduce Redundant Computation

**Problem:** The same expensive noise is evaluated at the same coordinates by multiple
consumers.

**Solution:** Define the sampler at the pack level and wrap it in CACHE.

```yaml
# pack.yml samplers section
samplers:
  expensiveNoise:
    dimensions: 2
    type: CACHE
    sampler:
      type: FBM
      octaves: 8
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.002
```

Every EXPRESSION in the pack that calls `expensiveNoise(x, z)` now shares cached
results. If biome selection evaluates `expensiveNoise` at (100, 200) and then terrain
shaping also evaluates it at (100, 200), the second call is a cache hit.

### 7.2 Reduce Memory with Pack-Level Samplers

**Problem:** The same noise configuration is copy-pasted across many YAML files,
creating redundant objects.

**Solution:** Define it once at the pack level and reference by name in expressions.

Before (wasteful):
```yaml
# biome_plains.yml
terrain:
  type: FBM
  octaves: 4
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.01

# biome_forest.yml
terrain:
  type: FBM              # Identical config = separate duplicate object
  octaves: 4
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.01
```

After (shared):
```yaml
# pack.yml
samplers:
  terrainBase:
    dimensions: 2
    type: FBM
    octaves: 4
    sampler:
      type: OPEN_SIMPLEX_2
      frequency: 0.01

# biome_plains.yml — reference by name in an expression
terrain:
  type: EXPRESSION
  dimensions: 2
  expression: "terrainBase(x, z) * 64 + 64"

# biome_forest.yml — same shared instance
terrain:
  type: EXPRESSION
  dimensions: 2
  expression: "terrainBase(x, z) * 48 + 80"
```

### 7.3 Place CACHE at the Right Level

Wrap CACHE around the **outermost** sampler that you want to deduplicate, not around
inner components. Caching the final result of a computation tree saves more than
caching an intermediate step.

Good — caches the full FBM result:
```yaml
type: CACHE
dimensions: 2
sampler:
  type: FBM
  octaves: 6
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.005
```

Less useful — only caches the raw simplex, FBM still recomputes each octave lookup:
```yaml
type: FBM
octaves: 6
sampler:
  type: CACHE
  dimensions: 2
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.005
```

Note: Caching inner samplers can still be beneficial if that specific inner sampler
is shared across multiple outer trees. Use judgment based on the computation graph.

### 7.4 Prefer 2D Over 3D When Possible

2D caches use ~131 KB per thread. 3D caches use ~3 MB per thread. If a noise value
only varies in x/z (like continent shape, temperature, moisture), declare it as
`dimensions: 2` to use the smaller, more efficient 2D cache and 2D evaluation path.

### 7.5 Don't Cache Cheap Operations

`CONSTANT`, `WHITE_NOISE`, simple `LINEAR` normalizers, and basic arithmetic (`ADD`,
`MUL`) are cheap enough that the cache lookup overhead provides no benefit. Reserve
CACHE for expensive computations:
- High-octave `FBM` (6+ octaves)
- `PSEUDOEROSION`
- Deep `EXPRESSION` trees
- `CELLULAR` noise (distance calculations)
- Deeply nested sampler trees

### 7.6 Understand the SamplerProvider Chunk Cache

The automatic `SamplerProvider` cache operates at a different level — it caches the
precomputed `Sampler3D` noise grid for entire chunks, not individual sample lookups.
This is useful when the same chunk is revisited during generation stages (initial
terrain, then decoration, etc.).

Increasing `cache.sampler` in `config.yml` keeps more chunk grids in memory:
```yaml
cache:
  sampler: 2048    # Default is 1024. Increase for larger view distances.
```

This does NOT replace `type: CACHE`. The SamplerProvider caches chunk-level objects;
`type: CACHE` caches individual coordinate evaluations within those computations.

### 7.7 CACHE + Frequency Scaling Caveat

The CACHE hash function is optimized for **integer coordinates**. After frequency
scaling (e.g., `frequency: 0.01`), coordinates become fractional. The hash truncates
to integer parts, so different fractional values with the same integer part will
collide in the hash — this causes cache misses (not incorrect results), reducing
hit rate.

For best cache performance, place CACHE **outside** (wrapping) the frequency-scaled
sampler, so the cache sees the original integer world coordinates:

```yaml
# Good: CACHE sees integer coordinates
type: CACHE
dimensions: 2
sampler:
  type: OPEN_SIMPLEX_2
  frequency: 0.01          # Frequency scaling happens inside, after cache lookup

# Less efficient: CACHE sees post-frequency fractional coordinates
type: OPEN_SIMPLEX_2       # This won't work anyway since OPEN_SIMPLEX_2 can't wrap CACHE,
frequency: 0.01            # but the principle applies to EXPRESSION wrappers and similar
```

In practice, Terra's sampler architecture applies frequency internally within each
noise function, so wrapping with CACHE at the top level naturally receives integer
coordinates.

### 7.8 Tune `exp` and `int` for Memory vs. Hit Rate

These two parameters together give precise control over per-thread cache memory:

**`int: true`** — reduces key storage from `double[]` (8 bytes) to `int[]` (4 bytes),
saving ~25% (2D) or ~30% (3D) at a given `exp`. Also collapses sub-integer coordinate
variation into integer slots, increasing hit rate when coordinates have fractional jitter.

**`exp`** — halving the exponent by 1 halves the number of slots and halves the memory.
Going from `exp: 17` to `exp: 13` cuts a 3D cache from ~5 MB to ~320 KB per thread.

```yaml
# High-importance shared sampler: max hit rate, default memory
type: CACHE
dimensions: 2
int: true              # ~6 KB/thread
sampler: { ... }

# Memory-constrained server with many chunk-gen threads:
type: CACHE
dimensions: 3
exp: 13                # 8192 slots, ~320 KB/thread instead of ~5 MB
int: true              # ~240 KB/thread
sampler: { ... }

# Maximum coverage for a heavily reused 3D sampler:
type: CACHE
dimensions: 3
exp: 17                # 131072 slots (default), ~5 MB/thread
sampler: { ... }
```

Do NOT use `int: true` for samplers that intentionally rely on sub-integer coordinate
precision (e.g., domain-warped noise where the warp offsets are fractional).

The within-chunk zero-collision guarantee holds when `exp >= 8` (2D) or `exp >= 13`
(3D). Below those thresholds the cache is still correct but collisions increase.

---

## 8. Common Patterns with YAML Examples

### 8.1 Pack-Level Shared + Cached Noise

```yaml
# pack.yml
samplers:
  continent:
    dimensions: 2
    type: CACHE
    sampler:
      type: FBM
      octaves: 5
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.002

  temperature:
    dimensions: 2
    type: CACHE
    sampler:
      type: FBM
      octaves: 3
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.005

  moisture:
    dimensions: 2
    type: CACHE
    sampler:
      type: FBM
      octaves: 3
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.004
```

All biomes, terrain shapers, and feature placement that reference `continent`,
`temperature`, or `moisture` by name in their expressions share both the sampler
instance and cached results.

### 8.2 Expression Referencing Pack Samplers

```yaml
# terrain_shaper.yml
type: EXPRESSION
dimensions: 2
expression: "continent(x, z) * 128 + temperature(x, z) * 10"
# continent and temperature are resolved from the pack-level samplers map.
# No need to redefine them here.
```

### 8.3 Combining Local and Pack Samplers in an Expression

```yaml
type: EXPRESSION
dimensions: 2
expression: "continent(x, z) * 0.7 + localDetail(x, z) * 0.3"
variables:
  scale: 0.5
samplers:
  localDetail:                  # Local to this expression only
    type: FBM
    octaves: 3
    sampler:
      type: OPEN_SIMPLEX_2
      frequency: 0.02
# continent is resolved from pack-level; localDetail is local.
# If both pack and local define the same name, local takes priority.
```

### 8.4 Arithmetic Combiners (No Expression Needed)

For simple combinations, arithmetic types avoid the overhead of expression parsing:

```yaml
type: ADD
dimensions: 2
left:
  type: FBM
  octaves: 4
  sampler:
    type: OPEN_SIMPLEX_2
    frequency: 0.01
right:
  type: MUL
  left:
    type: CELLULAR
    frequency: 0.02
  right:
    type: CONSTANT
    value: 0.5
```

### 8.5 Domain Warping

```yaml
type: DOMAIN_WARP
dimensions: 2
amplitude: 50
sampler:
  type: OPEN_SIMPLEX_2
  frequency: 0.01
warp:
  type: OPEN_SIMPLEX_2
  frequency: 0.005
```

### 8.6 Normalizing Output Range

```yaml
type: LINEAR
dimensions: 2
min: 0
max: 1
sampler:
  type: OPEN_SIMPLEX_2    # Output range [-1, 1]
  frequency: 0.01
# Remaps [-1, 1] to [0, 1]
```

### 8.7 Extracting Image Channels

```yaml
samplers:
  heightFromRed:
    dimensions: 2
    type: CHANNEL
    channel: RED
    normalize: true
    color-sampler:
      type: SINGLE_IMAGE
      image: terrain_data.png

  moistureFromGreen:
    dimensions: 2
    type: CHANNEL
    channel: GREEN
    normalize: true
    color-sampler:
      type: SINGLE_IMAGE
      image: terrain_data.png
```

---

## 9. Source File Reference

### Caching
| File | Role |
|------|------|
| `common/addons/config-noise-function/.../CacheSampler.java` | Direct-mapped per-evaluation cache |
| `common/addons/config-noise-function/.../CacheSamplerTemplate.java` | YAML config template for CACHE type |
| `common/addons/chunk-generator-noise-3d/.../SamplerProvider.java` | Automatic chunk-level Sampler3D cache |
| `common/implementation/base/.../PluginConfigImpl.java` | `config.yml` loading, `cache.sampler` default |

### Instance Creation & Sharing
| File | Role |
|------|------|
| `common/implementation/base/.../GenericTemplateSupplierLoader.java` | Creates new sampler per YAML definition |
| `common/addons/config-noise-function/.../NoiseAddon.java` | Registers all sampler types, loads pack samplers |
| `common/addons/config-noise-function/.../NoiseConfigPackTemplate.java` | Pack-level `samplers:` section definition |
| `common/addons/config-noise-function/.../FunctionUtil.java` | Wraps pack samplers as expression functions |

### Expression System
| File | Role |
|------|------|
| `common/addons/config-noise-function/.../ExpressionFunctionTemplate.java` | EXPRESSION sampler config (merges pack + local samplers) |
| `common/addons/config-noise-function/.../DimensionApplicableSampler.java` | Wraps sampler + dimension count |
| `common/addons/config-noise-function/.../SamplerTemplate.java` | Base template, provides `dimensions` field |

### Multi-Value
| File | Role |
|------|------|
| Seismic library: `DerivativeSampler.java` | Interface for noise + derivatives |
| Seismic library: `DerivativeNoiseFunction.java` | Base class for derivative-capable noise |
| `common/addons/library-image/.../ChannelSampler.java` | Extracts single channel from ColorSampler |
