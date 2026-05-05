# Implementation Plan: Stronghold Search Fast-Path Biome Provider

## Problem Summary

When a new world is created with Terra, the stronghold ring position search
(`ChunkGeneratorStructureState.generateRingPositions`) queries `BiomeSource.findBiomeHorizontal`
for each of 128 positions. Each call issues 57×57 = 3,249 biome queries. Each query misses
Terra's pipeline chunk cache (or hits a peripheral chunk generating 4,096 cells for 1–2 used
values), resulting in 100–2,000× more noise evaluations than strictly necessary.

The fix: intercept `findBiomeHorizontal` at the platform biome source layer and route those
queries through a pack-configured fast-path provider instead of the full pipeline.

---

## Layer Overview

```
Platform biome source (NMSBiomeProvider / TerraBiomeSource)
    ↓ delegates to
BiomeProvider (PipelineBiomeProvider)
    ↓ built from
BiomePipelineTemplate (config)
```

The fast path requires changes at every layer:

1. **`BiomeProvider` API** — new optional method for structure placement biome lookup
2. **`PipelineBiomeProvider`** — implements the fast path if configured
3. **`BiomePipelineTemplate`** — reads fast-path config from pack YAML
4. **Platform biome sources** — intercept `findBiomeHorizontal` (Bukkit + Fabric)
5. **Pack YAML** — declares the fast-path provider or sampler

---

## Step 1 — `BiomeProvider` API: Add `getStructurePlacementBiome`

**File:** `common/api/src/main/java/com/dfsek/terra/api/world/biome/generation/BiomeProvider.java`

Add a default method that returns `Optional.empty()` — meaning "no fast path, use full
pipeline." Only providers that explicitly opt into the fast path override it.

```java
/**
 * Returns a biome for structure placement searching, bypassing expensive pipeline
 * evaluation. Implementations may return a coarse approximation sufficient for
 * determining structure eligibility (e.g. ocean vs land). Returns empty to indicate
 * no fast path is available and the caller should fall back to getBiome().
 *
 * Coordinates are in block space.
 */
default Optional<Biome> getStructurePlacementBiome(int x, int z, long seed) {
    return Optional.empty();
}
```

---

## Step 2 — `PipelineBiomeProvider`: Implement the fast path

**File:** `common/addons/biome-provider-pipeline/src/main/java/com/dfsek/terra/addons/biome/pipeline/PipelineBiomeProvider.java`

Add a nullable `structureFastPathProvider` field populated from config. Override
`getStructurePlacementBiome` to delegate to it when present.

```java
// New field (set via constructor or setter from BiomePipelineTemplate)
private final @Nullable BiomeProvider structureFastPathProvider;

@Override
public Optional<Biome> getStructurePlacementBiome(int x, int z, long seed) {
    if (structureFastPathProvider == null) return Optional.empty();
    return Optional.of(structureFastPathProvider.getBiome(x, 0, z, seed));
}
```

The fast-path provider is itself a `BiomeProvider` — it can be a simple single-biome provider,
a minimal pipeline, or a sampler-backed provider (see Step 3).

---

## Step 3 — New: `StructureSearchBiomeProvider`

**File:** `common/addons/biome-provider-pipeline/src/main/java/com/dfsek/terra/addons/biome/pipeline/StructureSearchBiomeProvider.java`
(or place in a dedicated `structure-search` addon)

A lightweight `BiomeProvider` that evaluates a single sampler and maps the result to one of
two biomes — "eligible" or "ineligible" — based on a configurable threshold. This replaces
the entire pipeline for the purpose of determining ocean vs land.

```java
public class StructureSearchBiomeProvider implements BiomeProvider {
    private final Sampler classifierSampler;  // e.g. continentalDistribution
    private final double threshold;           // negative = ineligible, positive = eligible
    private final Biome eligibleBiome;        // returned when above threshold (land)
    private final Biome ineligibleBiome;      // returned when below threshold (ocean)

    @Override
    public Biome getBiome(int x, int y, int z, long seed) {
        double value = classifierSampler.getSample(seed, x, z);
        return value >= threshold ? eligibleBiome : ineligibleBiome;
    }

    @Override
    public Iterable<Biome> getBiomes() {
        return List.of(eligibleBiome, ineligibleBiome);
    }
}
```

The two biomes (`eligibleBiome`, `ineligibleBiome`) are references to existing Terra biomes
from the pack's registry, so their `vanilla:` mappings are respected. This keeps all vanilla
biome ID translation intact.

Alternatively, pack authors may supply a full alternative `BiomeProvider` (e.g., a minimal
pipeline with only the first stage) instead of just a sampler — both options should be
supported.

---

## Step 4 — `BiomePipelineTemplate`: Read fast-path config

**File:** `common/addons/biome-provider-pipeline/src/main/java/com/dfsek/terra/addons/biome/pipeline/config/BiomePipelineTemplate.java`

Add optional YAML keys under `structure-search`:

```java
@Value("structure-search")
@Default
@Nullable
private @Meta StructureSearchConfig structureSearch = null;
```

Where `StructureSearchConfig` is a new `ObjectTemplate` reading:

```yaml
structure-search:
  # Sampler whose sign determines eligibility (positive = eligible / land)
  classifier:
    type: EXPRESSION
    expression: continentalDistribution(x, z)
  threshold: 0.0        # default: 0 (positive = eligible)
  eligible-biome: PLAINS    # Terra biome ID — returned for eligible positions
  ineligible-biome: OCEAN   # Terra biome ID — returned for ineligible positions
```

Or, for packs with more complex requirements, allow an alternate full provider:

```yaml
structure-search:
  # Full alternative BiomeProvider (any type supported in the biomes: key)
  provider:
    type: PIPELINE
    resolution: 256   # very coarse — just ocean/land
    pipeline:
      source: ...
      stages: [...]   # minimal stages only
```

In `BiomePipelineTemplate.get()`, if `structureSearch` is non-null, build the
`StructureSearchBiomeProvider` (or alternate provider) and pass it to
`PipelineBiomeProvider`'s constructor:

```java
@Override
public BiomeProvider get() {
    PipelineImpl pipeline = new PipelineImpl(source, stages, resolution, 64, profiler, ...);
    BiomeProvider fastPath = structureSearch != null ? structureSearch.build(registry) : null;
    return new PipelineBiomeProvider(pipeline, resolution, blendSampler, blendAmplitude,
                                     profiler, fastPath);
}
```

---

## Step 5 — Platform: Bukkit (`NMSBiomeProvider`)

**File:** `platforms/bukkit/nms/src/main/java/com/dfsek/terra/bukkit/nms/NMSBiomeProvider.java`

Override `findBiomeHorizontal` (the 9-argument form) to set a `ThreadLocal` flag, then
use the fast path in `getNoiseBiome` when the flag is active.

```java
private static final ThreadLocal<Boolean> IN_STRUCTURE_SEARCH =
    ThreadLocal.withInitial(() -> false);

// Intercept all findBiomeHorizontal calls (stronghold search is the only caller)
@Override
public @Nullable Pair<BlockPos, Holder<Biome>> findBiomeHorizontal(
        int x, int y, int z, int radius, int skipSteps,
        Predicate<Holder<Biome>> allowed, RandomSource random,
        boolean findClosest, Climate.Sampler sampler) {
    IN_STRUCTURE_SEARCH.set(true);
    try {
        return super.findBiomeHorizontal(x, y, z, radius, skipSteps,
                                         allowed, random, findClosest, sampler);
    } finally {
        IN_STRUCTURE_SEARCH.set(false);
    }
}

@Override
public @NotNull Holder<Biome> getNoiseBiome(int x, int y, int z,
                                             @NotNull Climate.Sampler sampler) {
    biomeQueryCount.incrementAndGet();

    if (IN_STRUCTURE_SEARCH.get()) {
        Optional<com.dfsek.terra.api.world.biome.Biome> fast =
            delegate.getStructurePlacementBiome(x << 2, z << 2, seed);
        if (fast.isPresent()) {
            return biomeRegistry.getOrThrow(
                ((BukkitPlatformBiome) fast.get().getPlatformBiome())
                    .getContext().get(NMSBiomeInfo.class).biomeKey());
        }
    }

    return biomeRegistry.getOrThrow(
        ((BukkitPlatformBiome) delegate.getBiome(x << 2, y << 2, z << 2, seed)
            .getPlatformBiome()).getContext().get(NMSBiomeInfo.class).biomeKey());
}
```

Note: `y` coordinate is intentionally not passed to `getStructurePlacementBiome` — the
search always uses Y=0 and the fast path is 2D only.

---

## Step 6 — Platform: Fabric/Forge (`TerraBiomeSource`)

**File:** `platforms/mixin-common/src/main/java/com/dfsek/terra/mod/generation/TerraBiomeSource.java`

The Fabric `BiomeSource` class provides the same `findBiomeHorizontally` method (yarn
mapping) that stronghold searches use on that platform. `TerraBiomeSource` extends
`BiomeSource` and can override it identically to the Bukkit approach:

```java
private static final ThreadLocal<Boolean> IN_STRUCTURE_SEARCH =
    ThreadLocal.withInitial(() -> false);

@Override
public Optional<RegistryEntry<Biome>> findBiomeHorizontally(
        int x, int y, int z, int radius, int skipSteps,
        Predicate<RegistryEntry<Biome>> predicate,
        Random random, boolean bl, MultiNoiseSampler noiseSampler) {
    IN_STRUCTURE_SEARCH.set(true);
    try {
        return super.findBiomeHorizontally(x, y, z, radius, skipSteps,
                                           predicate, random, bl, noiseSampler);
    } finally {
        IN_STRUCTURE_SEARCH.set(false);
    }
}

@Override
public RegistryEntry<Biome> getBiome(int biomeX, int biomeY, int biomeZ,
                                      MultiNoiseSampler noiseSampler) {
    long seed = SeedHack.getSeed(noiseSampler);

    if (IN_STRUCTURE_SEARCH.get()) {
        Optional<com.dfsek.terra.api.world.biome.Biome> fast =
            pack.getBiomeProvider().getStructurePlacementBiome(
                biomeX << 2, biomeZ << 2, seed);
        if (fast.isPresent()) {
            return ((ProtoPlatformBiome) fast.get().getPlatformBiome()).getDelegate();
        }
    }

    return ((ProtoPlatformBiome) pack.getBiomeProvider()
        .getBiome(biomeX << 2, biomeY << 2, biomeZ << 2, seed)
        .getPlatformBiome()).getDelegate();
}
```

The Fabric mapping for the search method may differ between MC versions; this should be
verified against the current Fabric API when implementing. The ThreadLocal pattern itself
is identical.

---

## Step 7 — Platform: Minestom and Allay

**No changes required.** Neither platform has a native structure generation system that
queries a `BiomeSource` for ring position computation. Minestom and Allay don't call
`findBiomeHorizontal` or any equivalent during world creation. The stronghold performance
problem is specific to platforms that use vanilla Minecraft's structure pipeline.

---

## Pack Config Changes (CHIMERA example)

In `biome-distribution/presets/CHIMERA.yml` (or the referenced preset), add a
`structure-search` block inside the `provider` section:

```yaml
biomes:
  type: EXTRUSION
  extrusions:
    - << biome-distribution/extrusions/add_deep_dark.yml:extrusions
    - << biome-distribution/extrusions/add_special_caves.yml:extrusions
    - << biome-distribution/extrusions/add_cave_biomes.yml:extrusions
  provider:
    type: PIPELINE
    resolution: 4
    y-resolution: 8

    # Fast-path for stronghold ring position search.
    # Evaluated instead of the full pipeline for the 415,872 biome queries
    # issued during world creation. Must correctly classify positions as
    # eligible (land) or ineligible (ocean) for stronghold placement.
    # The biome IDs used here must map to vanilla biomes in/out of
    # #minecraft:stronghold_biased_to respectively.
    structure-search:
      classifier:
        type: EXPRESSION
        expression: continentalDistribution(x, z)
      threshold: 0.0
      eligible-biome: TEMPERATE_GRASSLAND    # maps to minecraft:plains (in tag)
      ineligible-biome: OCEAN                # maps to minecraft:ocean (not in tag)

    blend:
      amplitude: 3
      sampler:
        type: OPEN_SIMPLEX_2
        frequency: 0.05
    pipeline:
      source: ...
      stages: ...
```

`continentalDistribution` is already a pack-level sampler in CHIMERA
(`math/samplers/continents.yml`) — no new samplers need to be defined. The fast path
reduces the 415,872 full-pipeline evaluations to 415,872 single-sampler evaluations,
eliminating the pipeline chunk cache amplification entirely.

---

## Platform Support Summary

| Platform | `findBiomeHorizontal` equivalent | Overridable | Fast path viable |
|---|---|---|---|
| **Bukkit/Paper** | `BiomeSource.findBiomeHorizontal` | Yes | **Yes** |
| **Fabric/Forge** | `BiomeSource.findBiomeHorizontally` | Yes | **Yes** |
| **Minestom** | None (no vanilla structure pipeline) | N/A | N/A |
| **Allay** | None (no vanilla structure pipeline) | N/A | N/A |

Both NMS-based platforms (`bukkit/nms` and `mixin-common`) use the same Minecraft codebase
for structure generation and share the same biome source inheritance hierarchy. The
implementation is structurally identical between them — only method names and registry types
differ due to mapping differences (Mojang mappings for Bukkit, Yarn/Intermediary for Fabric).

---

## Implementation Order

1. `BiomeProvider` API — add `getStructurePlacementBiome` default method
2. `StructureSearchBiomeProvider` — new class with sampler-based classification
3. `BiomePipelineTemplate` — add `structure-search` YAML key and wire to constructor
4. `PipelineBiomeProvider` — add fast-path field and override `getStructurePlacementBiome`
5. `NMSBiomeProvider` (Bukkit) — override `findBiomeHorizontal`, add fast path in `getNoiseBiome`
6. `TerraBiomeSource` (Fabric) — identical pattern with Fabric-specific types
7. CHIMERA pack YAML — add `structure-search` block

Steps 1–4 are platform-agnostic and live in the common addon. Steps 5–6 are NMS-specific
and do not affect each other. Step 7 can be done independently of the code.
