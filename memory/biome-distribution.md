# Terra Biome Distribution System

## REPLACE_LIST / ProbabilityCollection

### List order
The **first entry** in a YAML list corresponds to the **lowest sampler value**,
the **last entry** corresponds to the **highest**.

Implementation (`ProbabilityCollection.get()`):
```java
array[(int) NormalizationFunctions.normalizeIndex(n.getSample(seed, x, z), array.length)]
```

`normalizeIndex` formula (from Seismic library — no local source, lives in JAR):
```java
Math.max(Math.min((int)(((val + 1.0) / 2.0) * size), size - 1), 0)
```
- `val = -1` → index `0` (first entry)
- `val =  0` → index `size/2`
- `val = +1` → index `size-1` (last entry)

Weights in the list expand the array proportionally:
```yaml
- biomeA: 1   # 1 slot  (low values)
- biomeB: 3   # 3 slots (mid-high values)
- biomeC: 1   # 1 slot  (high values)
# total array size = 5
```

### Sampler range assumption
`normalizeIndex` **hardcodes** the input range as `[-1, 1]`.
If a sampler outputs a different range, you MUST normalise it first using
a `LINEAR`, `LINEAR_MAP`, or `CLAMP` wrapper before passing it to a
distribution. There is no automatic range detection.

### Key implementation files
| File | Role |
|------|------|
| `common/api/.../util/collection/ProbabilityCollection.java` | Maps sampler value → list index |
| `common/addons/biome-provider-pipeline/.../stage/mutators/ReplaceListStage.java` | REPLACE_LIST stage |
| Seismic JAR: `com.dfsek.seismic.math.normalization.NormalizationFunctions` | `normalizeIndex()` formula |

### Example (temperature.yml)
`C:\Projects\ORIGEN2\biome-distribution\stages\climate\temperature.yml`
— 12 climate biomes listed coldest→hottest, each with a weight.
Lowest temperature sampler output → first biome (ice-cap),
highest → last biome (tropical-rainforest).
