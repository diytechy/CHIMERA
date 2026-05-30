# Structures

This directory contains config files intended to be loaded as structures.
A structure can be thought of as any kind of *action* done at and or around any
given block, such as placing a set of blocks like a tree, spawning entities,
etc.

Where these structures get placed in the world during generation is determined
via *features* which can be found in the `features` directory.

The simplest structures that just place blocks can be loaded from Sponge
schematics (`.schem` files, which is also what WorldEdit uses), however most of
the structures in this pack define these 'actions' procedurally via the
TerraScript language (`.tesf` files) instead. Using scripts for structures
allows for great variation and ease of modification without a lot of manual
work. Because of this, most structures from trees to boulders are implemented as
scripts rather than schematics. Understanding and tweaking these scripts may
require a bit of scripting knowledge, however if you just want to use them in a
feature as is then none of that is required.

## How structures relate to the rest of the pack

A structure is the **what** (the blocks/entities placed); a [feature](../features/) is the
**where/how** (distributor + locator) that invokes it; a [biome](../biomes/) lists features by
generation stage. So the call chain is:

```
biome.features.<stage>  ->  feature (distributor + locator + structures)  ->  structure (.tesf / .schem)
```

The subdirectory layout here mirrors [`features/`](../features/), so a feature at
`features/flora/bushes/acacia_bushes.yml` resolves its structure at
`structures/flora/bushes/acacia_bush.tesf`.

## Branch vs base

Both structure formats are 🟢 **base** Terra (see the legend in
[math/README.md](../math/README.md#branch-vs-base-legend)):

- **Sponge schematics** (`.schem`) via the `structure-sponge-loader` addon.
- **TerraScript** (`.tesf`) via `structure-terrascript-loader`. TerraScript syntax and the
  available functions are documented upstream:
  <https://terra.polydev.org/config/documentation/terrascript/index.html>.

TerraScript structures can call the noise samplers (`structure-function-check-noise-3d`), so a
structure's placement check can share the same pack samplers documented in
[math/README.md](../math/README.md). The structures themselves are not visualised through the
NoiseTool — render the *distributor* sampler of the feature that places them instead (see
[features/README.md](../features/README.md#screenshot-placeholders)).
