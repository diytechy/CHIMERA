![CHIMERA](docs/img/screenshots/TitleSnap_Cropped2.jpg)

# CHIMERA

A comprehensive overworld configuration pack for Minecraft 26.1+ and [Abhorant vibe-coded Terra](https://github.com/diytechy/Terra).

CHIMERA brings together content from four separate Terra config packs into a single unified world generation experience, featuring hundreds of diverse biomes spanning overworld land, ocean, cave, and river environments.

It also features rolling rivers that flow up terrain while remaining boat-traversable, and are fully interconnected into a global river network.

> This pack could potentially use more tuning — bugs and issues are to be expected.

## Combined Packs

CHIMERA integrates content from the following projects:

| Pack | Description |
|------|-------------|
| [TerraOverworldConfig](https://github.com/PolyhedralDev/TerraOverworldConfig) | The base Terra overworld pack providing the core climate system, terrain framework, and many foundational biomes |
| [Origen](https://github.com/Rearth/Origen) | Adds dramatic and creative terrain biomes including towering plateaus, deep gorges, cavernous river systems, and more |
| [Hydraxia](https://github.com/justaureus/Hydraxia) | Contributes a large collection of cold/arctic biomes with detailed terrain and custom ore distributions |
| [Substratum](https://github.com/PolyhedralDev/Substratum) | Provides the cave biome layer — unique underground environments from fungal grottos to molten passages |

Most top-level settings such as biome and river sizes can be found in [customization.yml](customization.yml).


---

## Tools

Recompiled companion tools for visualizing and tuning CHIMERA's generation:

| Tool | Description |
|------|-------------|
| [NoiseTool](https://github.com/diytechy/NoiseTool) | Visualize and debug Terra noise samplers / expressions used throughout the pack |
| [BiomeTool](https://github.com/diytechy/BiomeTool) | Render and benchmark biome distribution across the world (used to tune the land-surface biome spread) |

### Build & Analysis Scripts

Repository scripts for packaging the config and analyzing/tuning its generation. See [.scripts/README.md](.scripts/README.md) for the full set and usage details.

| Script | Description |
|--------|-------------|
| [.scripts/AuditAndPackage.bat](.scripts/AuditAndPackage.bat) / [.scripts/pack.sh](.scripts/pack.sh) | One-command build: zip the pack and regenerate `resolved_samplers.yml` + `BiomeTable.csv` (`pack.sh` creates just the zip) |
| [.scripts/resolve_samplers.py](.scripts/resolve_samplers.py) | Flatten the `math/` sampler tree (resolving `$file.yml:key` refs and constant expressions) into a single YAML for loading in **NoiseTool** |
| [.scripts/calculate_biome_percentages.py](.scripts/calculate_biome_percentages.py) | Trace the biome pipeline per preset into `BiomeTable.csv` (distribution % and expected climate) — the data behind **BiomeTool** tuning |
| [.scripts/analyze_land_spread.py](.scripts/analyze_land_spread.py) | Classify biomes and report land-surface spread, excluding oceans, coasts, and special biomes |
| [tools/slant_convert.py](tools/slant_convert.py) | Convert legacy Derivative slant thresholds to the DotProduct method (`2.0 / threshold`) |
| [.scripts/biome_colorizer.py](.scripts/biome_colorizer.py) | Generate `biomes/colors.generated.yml` from `BiomeTable.csv` using a Munsell-like H/C/V color mapping |
| [.scripts/extract_vanilla_biome.py](.scripts/extract_vanilla_biome.py) | Extract a vanilla biome's complete worldgen def (biome JSON, features, **surface rules**, noises) from the bundled Mojang server jar — the input for porting it into the pack |

### Porting a vanilla biome into CHIMERA

When Minecraft/Paper adds a biome that should be mirrored here, use the
**`port-vanilla-biome`** agent skill ([.claude/skills/port-vanilla-biome/SKILL.md](.claude/skills/port-vanilla-biome/SKILL.md)).
It guides the full port — extract → translate → build configs → validate — and exists so the
process (and its hard-won gotchas) isn't re-derived each time.

- **Trigger it** by asking an agent (Claude Code) to *port / mirror / add a vanilla biome*
  (e.g. "port the new `pale_garden` biome into CHIMERA"); the skill auto-activates on that
  intent, or invoke it explicitly with `/port-vanilla-biome`.
- It drives [.scripts/extract_vanilla_biome.py](.scripts/extract_vanilla_biome.py) (pulls the
  vanilla data) and [docs/VANILLA_TO_TERRA_MAP.md](docs/VANILLA_TO_TERRA_MAP.md) (the
  vanilla→Terra translation table). Worked example: [docs/SULFUR_CAVES_STATUS_REPORT.md](docs/SULFUR_CAVES_STATUS_REPORT.md).

---


## Installation

CHIMERA is a config pack the comes with [Abhorant vibe-coded Terra](https://github.com/diytechy/Terra).  Due to custom samplers in Chimera, this is the only tested method, though it should be possible to strip the relevent add-ons and use in the official Terra package.

Refer to the custom Terra build for generation information.

---

## Screenshots

![](docs/img/screenshots/2026-05-16_21.55.18.jpg)
![](docs/img/screenshots/2026-05-16_22.00.33.jpg)
![](docs/img/screenshots/2026-05-16_22.06.20.jpg)
![](docs/img/screenshots/2026-05-16_22.08.29.jpg)
![](docs/img/screenshots/2026-05-16_22.11.22.jpg)
![](docs/img/screenshots/2026-05-16_22.12.17.jpg)
![](docs/img/screenshots/2026-05-16_22.14.13.jpg)
![](docs/img/screenshots/2026-05-16_22.19.56.jpg)
![](docs/img/screenshots/2026-05-16_22.22.18.jpg)
![](docs/img/screenshots/2026-05-17_12.29.17.jpg)
![](docs/img/screenshots/2026-05-17_13.35.45.jpg)
![](docs/img/screenshots/2026-05-17_15.26.18.jpg)
![](docs/img/screenshots/2026-05-17_15.40.13.jpg)
![](docs/img/screenshots/2026-05-17_15.41.04.jpg)
![](docs/img/screenshots/2026-05-17_17.04.40.jpg)
![](docs/img/screenshots/2026-05-17_17.06.49.jpg)
![](docs/img/screenshots/2026-05-17_17.08.09.jpg)
![](docs/img/screenshots/2026-05-17_17.09.25.jpg)
![](docs/img/screenshots/2026-05-17_17.24.26.jpg)
![](docs/img/screenshots/2026-05-17_19.09.14.jpg)
![](docs/img/screenshots/2026-05-18_12.22.06.jpg)
![](docs/img/screenshots/2026-05-18_12.47.20.jpg)
![](docs/img/screenshots/2026-05-18_19.47.54.jpg)
![](docs/img/screenshots/2026-05-18_19.53.30.jpg)
![](docs/img/screenshots/2026-05-18_22.40.34.jpg)
![](docs/img/screenshots/2026-05-18_22.41.46.jpg)
![](docs/img/screenshots/2026-05-18_22.42.21.jpg)
![](docs/img/screenshots/2026-05-18_22.43.44.jpg)
![](docs/img/screenshots/2026-05-18_22.57.24.jpg)
![](docs/img/screenshots/2026-05-19_12.13.48.jpg)
![](docs/img/screenshots/2026-05-19_12.14.27.jpg)
![](docs/img/screenshots/2026-05-19_12.16.47.jpg)
![](docs/img/screenshots/2026-05-19_12.18.53.jpg)
![](docs/img/screenshots/2026-05-19_12.19.27.jpg)
![](docs/img/screenshots/2026-05-19_13.22.05.jpg)
![](docs/img/screenshots/2026-05-19_13.33.23.jpg)
![](docs/img/screenshots/2026-05-19_13.33.52.jpg)
![](docs/img/screenshots/2026-05-19_13.35.41.jpg)
![](docs/img/screenshots/2026-05-19_13.39.38.jpg)
![](docs/img/screenshots/2026-05-19_15.22.29.jpg)
![](docs/img/screenshots/2026-05-19_15.23.14.jpg)
![](docs/img/screenshots/2026-05-19_15.25.08.jpg)
![](docs/img/screenshots/2026-05-25_18.08.04.jpg)
![](docs/img/screenshots/2026-05-25_18.10.06.jpg)
![](docs/img/screenshots/2026-05-26_23.02.36.jpg)
![](docs/img/screenshots/2026-05-29_19.39.18.jpg)
![](docs/img/screenshots/2026-05-29_23.21.10.jpg)
![](docs/img/screenshots/2026-05-30_01.51.56.jpg)
![](docs/img/screenshots/2026-05-30_09.24.15.jpg)
![](docs/img/screenshots/2026-05-30_09.30.52.jpg)
![](docs/img/screenshots/2026-05-31_00.17.50.jpg)

---

## Navigating the Config (Copied from Origen)

This pack is organized into top-level directories, each containing configs specific to a different domain:

- `biomes/` — All biome configs. Organized by climate/environment type, with subdirectories for `rearth/` (Origen biomes), `biomes/` (Hydraxia biomes), and `cave/substratum/` (Substratum cave biomes).
- `biome-distribution/` — Configuration for *where* biomes generate.
- `structures/` — All structure files loaded by the pack (trees, boulders, flora patches, etc.).
- `features/` — Feature configs that determine *how* structures generate in the world.
- `palettes/` — Palette configs that determine what blocks make up the base terrain.
- `math/` — Common mathematical functions and generic noise samplers used across the pack.

For more detail on each directory, refer to the README files within them.

---