# Stronghold Ring Position Biome Query Analysis

## Background

When Minecraft generates a new world, it must compute positions for all 128 strongholds using
`ConcentricRingsStructurePlacement`. Each stronghold position is found by searching for a
suitable biome within a 112-block radius of a candidate location. These 128 searches run as
parallel `CompletableFuture` tasks on `Util.backgroundExecutor()`.

## Biome Query Volume

Each ring position search calls `BiomeSource.findBiomeHorizontal()` with:
- `searchRadius = 112` blocks → `noiseRadius = 28` quart units
- `skipSteps = 1`, `findClosest = false`

Because `findClosest = false`, the method sets `startRadius = noiseRadius = 28` and runs a
**single while-loop pass** covering the full square: z from -28 to +28, x from -28 to +28
(no edge-only filtering since `findClosest` is false). It samples every position and picks a
uniformly random valid match.

**Per ring position:** 57 × 57 = **3,249 biome queries**
**For all 128 strongholds:** 128 × 3,249 = **415,872 biome queries**

All queries are at standard quart-grid coordinates (multiples of 4 blocks, anchored at world
origin). Y is always 0 (sea level), quart Y = 0.

## Terra's Pipeline Cache Amplification (CHIMERA pack)

### Coordinate Chain

CHIMERA sets `resolution: 4` in its pipeline config. With biome caching disabled (the default:
`biomeCache = false` in ConfigPackTemplate — CHIMERA does not override this), the call chain is:

```
Minecraft: getNoiseBiome(quartX, 0, quartZ, sampler)
  NMSBiomeProvider: delegate.getBiome(quartX * 4, 0, quartZ * 4, seed)  // quart → block
  PipelineBiomeProvider.getBiome(blockX=quartX*4, 0, blockZ=quartZ*4, seed):
    x /= resolution (4)  →  quartX * 4 / 4 = quartX  (pipeline units)
```

The `* 4` in NMSBiomeProvider and `/ resolution(4)` in PipelineBiomeProvider cancel exactly.
**1 quart = 1 pipeline unit.** Every pipeline cell is quart-aligned. The pack comment is accurate:
`resolution: 4` aligns the pipeline grid exactly with Minecraft's biome sampling grid.

Note: `CachingBiomeProvider` is NOT in this chain because `biomeCache` defaults to `false`.

### Pipeline Chunk Cache

`PipelineBiomeProvider` maintains a shared (non-ThreadLocal) Caffeine cache keyed by
`SeededVector2Key(chunkWorldX, chunkWorldZ, seed)` with `maximumSize(256)`. On a cache miss
for **any** coordinate within a pipeline chunk, `pipeline.generateChunk()` constructs a
`BiomeChunkImpl` computing **all** `arraySize × arraySize` cells in the working array.
`maxArraySize` is hardcoded to **64** in `BiomePipelineTemplate`.

### Stronghold Query Geometry

The stronghold search has radius 28 quart units (= 28 pipeline units), diameter 57. The
pipeline chunk is 64 units wide. Since 57 < 64, the search fits within at most 2 pipeline
chunks per dimension (4 total), depending on where the search center falls relative to
chunk boundaries.

**Amplification per pipeline chunk:**

| Scenario | Chunk's role | Queries served | Cells computed | Waste ratio |
|---|---|---|---|---|
| Central (best) | Search center near chunk middle | ~3,249 | 4,096 | ~1.3× |
| Peripheral (worst) | Barely within search radius | **~2** | 4,096 | **~2,048×** |

A peripheral pipeline chunk — where the search center is ~26 quart units outside its boundary —
contributes only 1–2 quart queries yet generates its full 4,096-cell array through all of
CHIMERA's pipeline stages (source, many REPLACE stages, 2 SMOOTH stages, rivers, trenches).

For 128 ring positions, each touching 1–4 pipeline chunks (many peripheral), total noise
evaluations are **conservatively 100–2,000× the 415,872 nominally needed**.

---

## Methods for Terra to Detect Stronghold Queries

### Method 1: Thread name inspection — DOES NOT WORK IN PRODUCTION

The stronghold tasks are submitted via `Util.backgroundExecutor().forName("structureRings")`.
Inspection of `TracingExecutor.forName` (Paper source):

```java
public Executor forName(final String name) {
    if (SharedConstants.IS_RUNNING_IN_IDE) {
        // IDE only: actually renames the thread to "structureRings"
        return command -> this.service.execute(() -> {
            thread.setName(name);
            try { command.run(); } finally { thread.setName(oldName); }
        });
    } else {
        // PRODUCTION: only opens a Tracy profiling zone — thread name is UNCHANGED
        return TracyClient.isAvailable()
            ? command -> this.service.execute(() -> { try(Zone z = TracyClient.beginZone(name, false)) { command.run(); } })
            : this.service;  // If Tracy unavailable: raw executor, zero wrapping
    }
}
```

**In production builds, `forName` does not rename the thread.** The thread name stays
`"Worker-Main-N"` (from `makeExecutor("Main", -1)`). Thread name inspection via
`Thread.currentThread().getName()` is completely unreliable outside IDE mode and cannot be
used in production code.

---

### Method 2: Override `findBiomeHorizontal` in NMSBiomeProvider — BEST OPTION

`BiomeSource.findBiomeHorizontal` is the method called by `ChunkGeneratorStructureState`
during stronghold searches. It calls `this.getNoiseBiome(...)` in a loop. Since
`NMSBiomeProvider extends BiomeSource`, it can override `findBiomeHorizontal` to set a
`ThreadLocal` flag before delegating to the default implementation:

```java
// In NMSBiomeProvider:
private static final ThreadLocal<Boolean> IN_STRUCTURE_SEARCH = ThreadLocal.withInitial(() -> false);

@Override
public @Nullable Pair<BlockPos, Holder<Biome>> findBiomeHorizontal(
        int x, int y, int z, int radius, int skipSteps,
        Predicate<Holder<Biome>> allowed, RandomSource random,
        boolean findClosest, Climate.Sampler sampler) {
    IN_STRUCTURE_SEARCH.set(true);
    try {
        return super.findBiomeHorizontal(x, y, z, radius, skipSteps, allowed, random, findClosest, sampler);
    } finally {
        IN_STRUCTURE_SEARCH.set(false);
    }
}

@Override
public @NotNull Holder<Biome> getNoiseBiome(int x, int y, int z, @NotNull Sampler sampler) {
    if (IN_STRUCTURE_SEARCH.get()) {
        // Fast path: bypass expensive pipeline cache
        return fastStructureBiomeLookup(x, y, z);
    }
    // Normal path (unchanged)
    return biomeRegistry.getOrThrow(...delegate.getBiome(x << 2, y << 2, z << 2, seed)...);
}
```

**Why this works:**
- `findBiomeHorizontal` is called on the `NMSBiomeProvider` instance by the stronghold search
- Its default implementation in `BiomeSource` calls `this.getNoiseBiome(...)` via polymorphism
- The `ThreadLocal` correctly scopes the flag to the calling thread (no cross-thread pollution)
- `try/finally` ensures cleanup even if an exception occurs
- **Requires no changes to Paper** — completely self-contained within Terra's NMS layer
- Zero overhead on the normal (non-structure-search) path

**What `fastStructureBiomeLookup` would need to do:**
Stronghold placement calls `preferredBiomes::contains` on the returned biome to decide if the
location is valid. The fast path needs to return the same Minecraft `Biome` holder that the
full pipeline would return, just computed cheaply. Options:
- Run only the first stage of the pipeline (ocean vs. land) and return a representative biome
  for each category — sufficient for the binary "strongholds don't spawn in ocean" check
- Use a separate coarse `BiomeProvider` that evaluates only the source sampler
- Consult a pre-built mapping from rough position to biome category using only the source noise

The key insight is that stronghold placement only needs to distinguish "this is a biome where
strongholds can generate" from "this is not." For CHIMERA this is approximately ocean vs.
land, which the source sampler (`continentalDistribution`) already resolves cheaply.

---

### Method 3: Paper thread-local API (cooperative, most explicit)

Paper sets a `public static ThreadLocal<Boolean>` in an accessible class before and after each
stronghold ring search task, and Terra reads it. More explicit contract than overriding
`findBiomeHorizontal`, but requires Paper cooperation:

In `ChunkGeneratorStructureState.generateRingPositions`, inside the `supplyAsync` lambda:
```java
// Paper: set before the findBiomeHorizontal call, clear after
SomeAccessibleClass.STRUCTURE_SEARCH_CONTEXT.set(true);
try {
    Pair<BlockPos, Holder<Biome>> result = biomeSource.findBiomeHorizontal(...);
} finally {
    SomeAccessibleClass.STRUCTURE_SEARCH_CONTEXT.set(false);
}
```

Terra then reads `SomeAccessibleClass.STRUCTURE_SEARCH_CONTEXT.get()` in `getNoiseBiome`.

**Pros:** Explicit, documented, cross-generator contract.
**Cons:** Requires Paper API change; other server implementations (Fabric, etc.) would need
the same addition for the optimization to apply there.

---

### Method 4: Call stack inspection — NOT PRACTICAL

Terra could walk `Thread.currentThread().getStackTrace()` looking for `findBiomeHorizontal`
or `generateRingPositions`. This works but is prohibitively expensive (stack trace capture
is very slow) and completely defeats the purpose of a fast path. Not viable.

---

### Method 5: Separate BiomeSource for structure placement (Bukkit/Paper API change)

A new Bukkit/Paper API method, e.g. `ChunkGenerator.getStructurePlacementBiomeSource()`,
would allow Terra to return a lightweight `BiomeSource` used only for structure searches. Terra
would implement it with a single-level noise lookup (no pipeline stages, no chunk cache).

**Pros:** Clean architectural separation; optimizes all structure searches, not just strongholds.
**Cons:** Requires Bukkit/Paper API addition and likely a MCDev contributor discussion.

---

## Recommendation

**Method 2** (override `findBiomeHorizontal` in `NMSBiomeProvider`) is the most practical
immediate solution. It requires no changes outside Terra's own codebase and eliminates the
pipeline cache amplification entirely for all `findBiomeHorizontal` calls (stronghold search,
`/locate biome`, structure searches). The implementation challenge is building a sufficiently
accurate fast biome lookup that Terra's pipeline can short-circuit to.

**Method 3** (Paper thread-local API) is worth pursuing as a follow-on if a formal API
contract is desired, making the intent explicit across server implementations.

**Method 4 (caching, already implemented):** Paper's `26.1_RestoreStrongholdLocationsFromFile`
branch caches computed stronghold positions to `data/stronghold_positions.dat`. This eliminates
the problem for all subsequent server starts. The first-creation cost remains but happens only
once per world seed.
