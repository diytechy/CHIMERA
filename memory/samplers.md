# ORIGEN2 Sampler Tooling

## resolve_samplers.py
Location: `C:\Projects\ORIGEN2\.scripts\resolve_samplers.py`

Resolves all sampler definitions from `math/samplers/` into a single
`.artifacts/resolved_samplers.yml` for use by NoiseTool.

### Key features
- Resolves `$file.yml:key.path` and `${file.yml:key}` inline references
- Evaluates constant math expressions (`"1 / 1000"` → `0.001`)
- Topologically orders samplers (dependencies first) for sequential loading
- Removes pack-level sampler names from local `samplers:` dicts (they're
  available via `globalSamplers` in NoiseTool's sequential loader)
- Keeps `sampler:` (singular) entries inline (wrapper types like FBM/CACHE
  load them directly)

### Validation added (session Feb 2026)
`validate_expression_samplers()` runs after all samplers/functions are
collected, before building output:
- **Error**: EXPRESSION sampler calls `foo(x,z)` where `foo` is a pack-level
  sampler name but is NOT declared in the local `samplers:` section.
  (Skips identifiers in `all_functions`; skips identifiers not in
  `all_samplers` — assumed built-ins like `if`, `sin`, etc.)
- **Warning**: Local `samplers:` entry declared but never called in expression.

### EXPRESSION sampler local samplers: rule
A sampler used in an expression MUST be declared in the local `samplers:`
section of that EXPRESSION node in the source YAML. Terra loads pack-level
samplers in file-merge order; if the referenced sampler's file is merged
after the current file, it won't be in `globalSamplers` at parse time.

Example fix (elevation.yml — elevationDetailed):
```yaml
samplers:
  continentalRiverDist: $math/samplers/rivers.yml:samplers.continentalRiverDist
  elevationWithRivers: $math/samplers/elevation.yml:samplers.elevationWithRivers
  noisyelevation:
    ...  # inline local-only sampler
```

### copy_resolved_samplers.py
Copies the resolved output to NoiseTool for visualization.
