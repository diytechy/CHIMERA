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
uniformly random valid match using reservoir sampling (`nextInt(found + 1) == 0`).

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
**1 quart = 1 pipeline unit.** Every pipeline cell is quart-aligned. The pack comment is correct:
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

## `findBiomeHorizontal` is the Exclusive Entry Point

A full search of the Paper codebase confirms that `findBiomeHorizontal` is called in exactly
**one location** outside its own definition:

**`ChunkGeneratorStructureState.java:229`** — the stronghold ring position search.

Regular chunk generation never calls `findBiomeHorizontal`; it calls `getNoiseBiome` directly.
`/locate biome` uses the separate `findClosestBiome3d` method. No other structure placement
type (e.g., `RandomSpreadStructurePlacement`) calls it — only `ConcentricRingsStructurePlacement`.
This means overriding `findBiomeHorizontal` in `NMSBiomeProvider` affects **only** stronghold
searches and cannot interfere with standard biome queries.

---

## Two-Phase Placement Architecture

Stronghold placement works in two entirely separate phases with different biome checks.

### Phase 1 — Ring position search (startup)

`ChunkGeneratorStructureState.generateRingPositions` calls `BiomeSource.findBiomeHorizontal`
checking **`#minecraft:stronghold_biased_to`** (39 land/cave biomes). This records a `ChunkPos`
for each of the 128 strongholds. The biome check here only influences *where* a stronghold
will be attempted — it does not guarantee or prevent generation.

### Phase 2 — Chunk generation (when the chunk is loaded/generated)

When the designated chunk actually generates, `ChunkGenerator.createStructures` calls
`tryGenerateStructure`. The flow:

1. `featurePlacement.isStructureChunk(state, chunkX, chunkZ)` — concentric rings checks
   whether the chunk matches a recorded ring position. If yes:
2. `structure.biomes()` is fetched → `#minecraft:has_structure/stronghold`
3. `biomePredicate = biomeAllowedForStructure::contains`
4. `structure.generate(...)` → `findValidGenerationPoint(context)`
   → `findGenerationPoint(context)` returns a `GenerationStub`
   → `isValidBiome(stub, context)` is called

`isValidBiome` queries the **actual biome at the structure's proposed position**:

```java
context.chunkGenerator.getBiomeSource().getNoiseBiome(
    QuartPos.fromBlock(startPos.getX()),
    QuartPos.fromBlock(startPos.getY()),   // Y = 0
    QuartPos.fromBlock(startPos.getZ()),
    context.randomState.sampler()
)
```

`StrongholdStructure.findGenerationPoint` returns
`context.chunkPos().getWorldPosition()` which is `new BlockPos(minX, **0**, minZ)` —
Y = 0, identical to the Y used by the ring position search. Both phases check biomes at
sea level.

### The Phase 2 biome tag is `#is_overworld` — effectively unrestricted

`#has_structure/stronghold` is defined as a single include: **`#minecraft:is_overworld`**,
which contains every overworld biome without exception — including all ocean variants,
`minecraft:river`, `minecraft:frozen_river`, beaches, swamps, caves, and deep dark.

**Consequence: the Phase 2 biome check never rejects a stronghold for any CHIMERA biome.**
CHIMERA maps all of its biomes to vanilla overworld IDs. Every one of those IDs is in
`#is_overworld`, so `isValidBiome` always returns `true`.

### What happens if the actual chunk biome is a river or ocean

If the ring position search placed a stronghold at a chunk whose real biome turns out to
be `minecraft:river` (not in `#stronghold_biased_to`):

| Step | Result |
|---|---|
| `isStructureChunk` | **true** — chunk matches a ring position |
| `isValidBiome` at Y=0 | `river` is in `#is_overworld` → **true** |
| Stronghold generates? | **Yes — always** |

The stronghold is never silently omitted. Phase 1 only biases the *location* toward land
biomes; Phase 2 never rejects based on biome for any overworld generator.

### Implications for the fast path (Method 2)

Fast path misclassification has entirely benign consequences:

| Fast path error | Phase 1 effect | Phase 2 effect |
|---|---|---|
| Land misclassified as ocean | Position skipped; search picks a nearby land point instead | No impact — different position used |
| Ocean misclassified as land | Ocean position enters reservoir and may be selected | Stronghold still generates — `#is_overworld` accepts ocean biomes |

In the ocean-misclassified case, a stronghold would generate underwater/underground at
an ocean chunk. It is still valid, still reachable by ender eye, and still contains an
End Portal. The only user-visible difference is that players may have to dig down through
ocean floor to reach it — equivalent to a ring position that legitimately landed near an
ocean/land border.

---

## What Biomes the Stronghold Search Checks: `#minecraft:stronghold_biased_to`

The stronghold structure set (`data/minecraft/worldgen/structure_set/strongholds.json`) uses:
```json
"preferred_biomes": "#minecraft:stronghold_biased_to"
```

This tag (`data/minecraft/tags/worldgen/biome/stronghold_biased_to.json`) contains **39 land
and cave biomes**:

```
minecraft:plains            minecraft:sunflower_plains    minecraft:snowy_plains
minecraft:ice_spikes        minecraft:desert
minecraft:forest            minecraft:flower_forest       minecraft:birch_forest
minecraft:dark_forest       minecraft:pale_garden         minecraft:old_growth_birch_forest
minecraft:old_growth_pine_taiga    minecraft:old_growth_spruce_taiga
minecraft:taiga             minecraft:snowy_taiga
minecraft:savanna           minecraft:savanna_plateau
minecraft:windswept_hills   minecraft:windswept_gravelly_hills
minecraft:windswept_forest  minecraft:windswept_savanna
minecraft:jungle            minecraft:sparse_jungle       minecraft:bamboo_jungle
minecraft:badlands          minecraft:eroded_badlands     minecraft:wooded_badlands
minecraft:meadow            minecraft:cherry_grove        minecraft:grove
minecraft:snowy_slopes      minecraft:frozen_peaks        minecraft:jagged_peaks
minecraft:stony_peaks       minecraft:mushroom_fields
minecraft:dripstone_caves   minecraft:lush_caves
```

**Absent from the tag:** all ocean variants (`ocean`, `cold_ocean`, `frozen_ocean`,
`lukewarm_ocean`, `warm_ocean`, `deep_*`), rivers, beaches, nether, end, void.

The search in `findBiomeHorizontal` checks `preferredBiomes::contains` for each sampled
position. Only positions whose returned biome is in this tag contribute to the reservoir.
Importantly, `generateRingPositions` uses only the **position** (`BlockPos`) from the
returned `Pair<BlockPos, Holder<Biome>>` — the biome identity itself is discarded after the
eligibility check.

### How CHIMERA Biomes Map to This Tag

Terra biomes declare their vanilla equivalent via the `vanilla:` field in their YAML config,
stored as `NMSBiomeInfo(ResourceKey<Biome> biomeKey)`. The `getNoiseBiome` method returns
`biomeRegistry.getOrThrow(biomeKey)` — a standard Minecraft `Holder<Biome>`.

**CHIMERA ocean biomes → vanilla ocean IDs (NEVER in `#stronghold_biased_to`):**
- `minecraft:ocean`, `minecraft:cold_ocean`, `minecraft:frozen_ocean`,
  `minecraft:lukewarm_ocean`, `minecraft:deep_cold_ocean`, `minecraft:deep_frozen_ocean`,
  `minecraft:deep_lukewarm_ocean`

**CHIMERA land biomes → vanilla land IDs (all IN `#stronghold_biased_to`):**
- Examples: `minecraft:plains`, `minecraft:snowy_plains`, `minecraft:snowy_taiga`,
  `minecraft:jagged_peaks`, `minecraft:frozen_peaks`, `minecraft:ice_spikes`, etc.

**CHIMERA cave biomes → `minecraft:dripstone_caves` / `minecraft:lush_caves` (IN the tag)**

**CHIMERA river/coastal biomes → mixed:**
- `minecraft:frozen_river` (NOT in tag), `minecraft:snowy_beach` (NOT in tag),
  `minecraft:beach` (NOT in tag), `minecraft:river` (NOT in tag)
- Exception: `chilly_creek_river` → `minecraft:snowy_taiga` (IS in tag);
  `frostbite_rivers` → `minecraft:frozen_peaks` (IS in tag)

The CHIMERA mapping is effectively a clean **ocean = not eligible / land = eligible** split,
with a small number of coastal edge cases that are harmless since their positions are rare.

---

## Methods for Terra to Detect Stronghold Queries

### Method 1: Thread name inspection — DOES NOT WORK IN PRODUCTION

The stronghold tasks use `Util.backgroundExecutor().forName("structureRings")`. Inspection of
`TracingExecutor.forName` reveals it only renames the thread in IDE mode
(`SharedConstants.IS_RUNNING_IN_IDE = true`). In **production builds**, `forName` either opens
a Tracy profiling zone without renaming the thread, or — if Tracy is unavailable — returns the
raw executor with no wrapping at all. The thread name stays `"Worker-Main-N"` regardless.

**Thread name inspection cannot be used in production code.**

---

### Method 2: Override `findBiomeHorizontal` in NMSBiomeProvider — BEST OPTION

Since `findBiomeHorizontal` is the sole entry point for stronghold searches, and it calls
`this.getNoiseBiome(...)` via polymorphism, `NMSBiomeProvider` can intercept it with a
`ThreadLocal` flag and use a fast path in `getNoiseBiome`:

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
        return fastStructureBiomeLookup(x, z);
    }
    return biomeRegistry.getOrThrow(...delegate.getBiome(x << 2, y << 2, z << 2, seed)...);
}
```

**Why this is safe:** `findBiomeHorizontal` is called in exactly one place in the entire
Paper codebase. The `ThreadLocal` flag is correctly scoped to the calling thread and is
cleared in a `try/finally` block. Zero overhead on the normal path.

**No changes to Paper required** — completely self-contained within Terra's NMS layer.

---

### What `fastStructureBiomeLookup` Should Return

The search uses `preferredBiomes::contains` to check eligibility, and only the position
(not the biome) is used in the final result. The fast path therefore only needs to return
a `Holder<Biome>` that is correctly IN or OUT of `#minecraft:stronghold_biased_to` based on
whether the position is land or ocean.

**Correct return values:**
- **Land position → `minecraft:plains`** (always in `#stronghold_biased_to`)
- **Ocean position → `minecraft:ocean`** (never in `#stronghold_biased_to`)

These holders can be obtained via `biomeRegistry.getOrThrow(ResourceKey.create(Registries.BIOME,
ResourceLocation.withDefaultNamespace("plains")))` cached at startup.

**Determining land vs. ocean cheaply:** The fast path needs a single cheap signal to
distinguish ocean from land without running the full pipeline. Options in Terra:

1. **Call `BiomeProvider.getBaseBiome(x, z, seed)`** — `PipelineBiomeProvider` already
   overrides this to return `Optional.of(getBiome(x, z, seed))` (full pipeline). If Terra
   adds a true lightweight override that calls only the source + first stage, this becomes
   the natural API hook.

2. **Expose a per-position source query on `PipelineBiomeProvider`** — evaluate just the
   source sampler (`spotPlacer` → ocean/land/spot classification) and the first REPLACE stage
   (`continentalDistribution` → ocean vs. land), returning a category rather than a full
   biome. This is 2 noise evaluations per query instead of thousands.

3. **Per-position pipeline evaluation without chunk cache** — call `pipeline.generateChunk`
   for a 1×1 array. Eliminates the 4,096-cell amplification while keeping full accuracy.
   More expensive than options 1–2 but still eliminates the dominant cost.

For CHIMERA specifically, option 2 is ideal: `continentalDistribution(x, z)` is a single
EXPRESSION noise call that already determines ocean vs. land before any biome-specific logic.

---

### Method 3: Paper thread-local API (cooperative, most explicit)

Paper adds a `public static ThreadLocal<Boolean>` to an accessible class, sets it `true`
before each ring search task's `findBiomeHorizontal` call, and clears it after. Terra reads
it in `getNoiseBiome`.

**Pros:** Explicit documented contract across server implementations.
**Cons:** Requires Paper API change; other platforms need the same addition.

---

### Method 4: Call stack inspection — NOT PRACTICAL

Walking `Thread.currentThread().getStackTrace()` is prohibitively expensive per biome query.

---

### Method 5: Separate BiomeSource for structure placement (API change)

A new API method (e.g., `ChunkGenerator.getStructurePlacementBiomeSource()`) lets Terra
return a lightweight `BiomeSource` for structure searches. Clean but requires Paper/Bukkit
API additions.

---

## Summary

| Method | Requires Paper change | Works in production | Overhead on normal path |
|---|---|---|---|
| 1. Thread name | No | **No** (broken) | n/a |
| 2. Override `findBiomeHorizontal` | No | Yes | Zero |
| 3. Paper ThreadLocal API | Yes | Yes | Zero |
| 4. Call stack | No | Yes | Prohibitive |
| 5. Separate BiomeSource API | Yes | Yes | Zero |

**Recommendation:** Method 2 is the most practical immediate solution. It requires no changes
outside Terra's own codebase, is correct (only stronghold searches call `findBiomeHorizontal`),
and eliminates the pipeline cache amplification entirely. The implementation challenge is the
fast biome lookup — for CHIMERA, evaluating only `continentalDistribution(x, z)` to determine
ocean vs. land and returning `minecraft:plains` or `minecraft:ocean` is sufficient and correct.
