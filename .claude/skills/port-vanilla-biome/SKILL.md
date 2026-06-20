---
name: port-vanilla-biome
description: Port (mirror) a vanilla Minecraft biome into this CHIMERA Terra world-generation pack. Use when the user wants to add, mirror, or align a biome that exists in vanilla Minecraft (e.g. a biome from a new MC/Paper release) into the pack's biome/feature/palette/distribution configs.
---

# Port a vanilla biome into CHIMERA

Goal: reproduce a vanilla biome's **appearance and behavior** in this Terra pack. The
recurring failure mode is incompleteness — reading only the biome JSON and missing where
the real look is defined (surface rules, features). Follow every step.

## 1. Extract the complete vanilla definition
```
python .scripts/extract_vanilla_biome.py <biome_id> [mojang.jar | cache_dir]
```
Jar resolution: 2nd arg → `$CHIMERA_MOJANG_JAR` → `$CHIMERA_MC_CACHE/mojang_*.jar` (newest)
→ built-in fallback (the server backup's `cache/`). Output: `.artifacts/vanilla-extract/<biome>/`.
If the jar isn't found, ask the user for the path to the server's `cache/` dir or a
`mojang_<version>.jar`.

## 2. Read ALL of it (not just the biome JSON)
Open `.artifacts/vanilla-extract/<biome>/SUMMARY.md`, then read:
- `biome/<biome>.json` — colors, climate, spawners, carvers, the feature list (by step).
- **`surface_rules_for_biome.json`** — the wall/floor block material. **Never skip this** —
  it's where sulfur caves' sulfur/cinnabar walls were defined, and skipping it caused a
  wrong port.
- the `configured_feature/` + `placed_feature/` files for anything biome-specific (ignore
  the standard ores/disks/springs unless they differ).

## 3. Translate using docs/VANILLA_TO_TERRA_MAP.md
That map is the source of truth for vanilla→Terra. Key conversions and the gotchas:
- surface_rule noise bands → palette `materials:` weights + sampler.
- `placed_feature count:N + in_square` → **per-column `SAMPLER`, threshold ≈ N/256** (NOT
  `PADDED_GRID`, which clusters).
- `lake`/`speleothem`/`root_system`/`template` → `.tesf` structures + features.
- spawners/colors/climate → set `vanilla: minecraft:<biome>` (spawns) + `colors:`/`climate:`.
- SAMPLER places where value **< threshold**; mixins override per-stage (use a free stage).
If you hit a vanilla type not in the map, work out the equivalent and **add a row to the map**.

## 4. Build the CHIMERA configs
- `biomes/cave|land/.../<biome>.yml` (extends the right base, `vanilla:`, colors, climate,
  palette, tags, features in the right STAGES — sulfur-before-spikes style ordering).
- palettes under `palettes/`, structures under `structures/`, features under `features/`.
- colors in `biomes/colors.yml` (+ substratum colors for caves).
- Place it in `biome-distribution/` (extrusions/stages) per the multinoise/rarity, or leave
  unplaced if the user wants to add it later.

## 5. Validate
- YAML parses; `python .scripts/calculate_biome_percentages.py` resolves with no schema
  errors and the biome appears (0% if unplaced is fine).
- These check **wiring only**. Densities and appearance MUST be confirmed in-world
  (`docs/CAPTURES.md`) — the static predictor also over-reports spatially-gated biomes.

## 6. Record what's new
If the biome introduced a new vanilla feature type or a Terra gotcha, add it to
`docs/VANILLA_TO_TERRA_MAP.md` and/or a memory so the next port is easier.
