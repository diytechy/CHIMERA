# NoiseTool Capture Manifest

This file lists every documentation screenshot, where it lives, and the **exact
NoiseTool CLI command** that regenerates it. Run these from the NoiseTool directory
(so `addons/` resolves) — `RenderNoise.bat` `cd`s to the JAR directory for you.

> Status: the images below are **placeholders**. They have not been captured yet.
> Run the commands to populate `docs/img/`. See the NoiseTool headless CLI docs in
> `C:\Projects\NoiseTool\README.md` for the full flag reference.

## Conventions

- **Tool:** `C:\Projects\NoiseTool\RenderNoise.bat` (no-window, no-pause wrapper around
  `java -jar NoiseTool-*-all.jar --headless ...`).
- **Common file:** most CHIMERA samplers are *named pack samplers*, so they need
  `--common <pack>\.artifacts\resolved_samplers.yml` to be in scope. Regenerate that file
  first with `.scripts\resolve_samplers.py` (it resolves `math/samplers/*.yml` into one file).
- **Sampler stubs:** the tiny `type: EXPRESSION` files the CLI renders live in
  [docs/noise/](noise/). Each just calls one named sampler, e.g. `temperature(x, z)`.
- **Seed/origin:** use a fixed `--seed 2403 --origin 0,0` so captures are reproducible.
- **Multiplier:** climate/continent fields are very low frequency — use a large
  `--multiplier` (e.g. 24–64) so one image covers many biomes. Detail samplers use 1–4.
- **Output:** PNGs go under [docs/img/](img/) in the subfolder that matches the README
  that references them.

Let `PACK=C:\Projects\CHIMERA` and `RES=%PACK%\.artifacts\resolved_samplers.yml`.

## Samplers (referenced from [math/README.md](../math/README.md))

| Image | Command |
|---|---|
| `docs/img/samplers/fbm_demo.png` | `RenderNoise.bat --in %PACK%\docs\noise\fbm_demo.yml --out %PACK%\docs\img\samplers\fbm_demo.png --seed 2403 --size 512x512 --multiplier 2` |
| `docs/img/samplers/temperature.png` | `RenderNoise.bat --common %RES% --in %PACK%\docs\noise\temperature.yml --out %PACK%\docs\img\samplers\temperature.png --seed 2403 --size 512x512 --multiplier 24` |
| `docs/img/samplers/precipitation.png` | `RenderNoise.bat --common %RES% --in %PACK%\docs\noise\precipitation.yml --out %PACK%\docs\img\samplers\precipitation.png --seed 2403 --size 512x512 --multiplier 24` |
| `docs/img/samplers/continents.png` | `RenderNoise.bat --common %RES% --in %PACK%\docs\noise\continents.yml --out %PACK%\docs\img\samplers\continents.png --seed 2403 --size 512x512 --multiplier 48` |
| `docs/img/samplers/elevation.png` | `RenderNoise.bat --common %RES% --in %PACK%\docs\noise\elevation.yml --out %PACK%\docs\img\samplers\elevation.png --seed 2403 --size 512x512 --multiplier 24 --color-scale terrain` |

## Biome distribution (referenced from [biome-distribution/README.md](../biome-distribution/README.md))

These stages do not have a single sampler; capture the **driver sampler** behind each stage
to illustrate the partition it produces.

| Image | Driver | Command |
|---|---|---|
| `docs/img/distribution/continents.png` | continent/ocean split (source stage) | same as `continents.png` above, copied into `distribution/` |
| `docs/img/distribution/temperature_bands.png` | `temperature` field (drives the band `REPLACE_LIST`) | `RenderNoise.bat --common %RES% --in %PACK%\docs\noise\temperature.yml --out %PACK%\docs\img\distribution\temperature_bands.png --seed 2403 --size 512x512 --multiplier 24` |

To add a new capture: drop a stub in `docs/noise/`, add a row here, run the command, and
reference `docs/img/<folder>/<name>.png` from the relevant README.
