# Terra / ORIGEN2 Project Structure

## Repositories
| Path | Purpose |
|------|---------|
| `c:\Projects\Terra` | Terra engine source (main branch: `main`) |
| `c:\Projects\ORIGEN2` | Config pack under development (ID: `EXPLORE_TEST`) |
| `c:\Projects\BiomeTool` | Standalone biome visualisation tool (Kotlin, uses AbstractPlatform) |
| `c:\Projects\DendryTerra` | DendryNoise addon for Terra (addon ID: `dendry-noise`) |
| `c:\Projects\NoiseTool` | Noise visualisation tool |

## Publish / dependency setup
- Terra artifacts published to Repsy: `https://repo.repsy.io/mvn/diytechy/terra`
- Version suffix format: `1.0.0-BETA-ec788bf` (commit hash, no `+`)
- `mavenLocal()` added to DendryTerra repos for local testing

## Key Terra source files
- `common/implementation/base/.../config/pack/ConfigPackTemplate.java` — pack.yml template
- `common/addons/config-noise-function/.../NoiseAddon.java` — registers built-in samplers at priority 50, calls `event.loadTemplate()` inside handler
- `common/implementation/base/.../event/FunctionalEventHandlerImpl.java` — event handler gate: checks `pack.addons().containsKey(addon)`
- `common/implementation/base/.../config/loaders/GenericTemplateSupplierLoader.java` — source of "No such entry: X" errors
- `common/api/.../registry/Registry.java` — `getByID(id)` without namespace uses `getMatches()` (matches ID portion only)

## BiomeTool pack loading
- Packs are copied from source (e.g. `C:\Projects\ORIGEN2`) into `build\libs\packs\terra-origen\` before launch
- BiomeTool addon JARs live in `build\libs\addons\`
- All addon JARs share one `BootstrapAddonClassLoader` (no isolation)
