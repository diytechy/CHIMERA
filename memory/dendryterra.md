# DendryTerra Addon Integration

## Addon identity
- Addon ID: `dendry-noise`  (in `terra.addon.yml`)
- Version: `1.0.0`
- Sampler type registered as: `dendry-noise:DENDRY` (unqualified `DENDRY` also works in pack configs)

## Critical fixes made
### 1. Use NoiseAddon's TypeKey, not a custom one
DendryAddon must register into the same registry as NoiseAddon by using `NoiseAddon.NOISE_SAMPLER_TOKEN`:
```java
import com.dfsek.terra.addons.noise.NoiseAddon;
// ...
CheckedRegistry<Supplier<ObjectTemplate<Sampler>>> noiseRegistry =
    event.getPack().getOrCreateRegistry(NoiseAddon.NOISE_SAMPLER_TOKEN);
noiseRegistry.register(addon.key("DENDRY"), DendryTemplate::new);
```
(A custom `TypeKey<Supplier<ObjectTemplate<Sampler>>>` {}` would actually map to the same underlying registry due to Java type erasure / TypeKey equality, but using the constant is clearer.)

### 2. Priority must be < 50
NoiseAddon registers at `.priority(50)` and calls `event.loadTemplate(new NoiseConfigPackTemplate())` inside its handler — which triggers pack-level sampler loading. Any addon registering sampler types must do so at a lower priority number (runs first).
DendryAddon must use `.priority(0)`.

### 3. Pack must declare the addon
`pack.yml` (and its build copy) must include:
```yaml
addons:
  dendry-noise: "1.+"
```

### 4. build.gradle.kts dependencies
```kotlin
repositories {
    mavenLocal()
    mavenCentral()
    maven { name = "Solo Studios"; url = uri("https://maven.solo-studios.ca/releases") }
    maven { name = "Repsy-Terra"; url = uri("https://repo.repsy.io/mvn/diytechy/terra") }
}
dependencies {
    compileOnly("com.dfsek.terra:manifest-addon-loader:1.0.0-BETA-ec788bf")
    compileOnly("com.dfsek:seismic:0.8.2")
    compileOnly("com.dfsek.terra:base:7.0.0-BETA-ec788bf")
    compileOnly("com.dfsek.terra:config-noise-function:1.2.0-BETA-ec788bf")
    compileOnly("com.dfsek.tectonic:common:4.2.1")
    compileOnly("org.slf4j:slf4j-api:2.0.9")
    compileOnly("com.github.ben-manes.caffeine:caffeine:3.1.8")
}
```

## DendryAddon.java final state (key parts)
```java
platform.getEventManager()
    .getHandler(FunctionalEventHandler.class)
    .register(addon, ConfigPackPreLoadEvent.class)
    .then(event -> {
        CheckedRegistry<Supplier<ObjectTemplate<Sampler>>> noiseRegistry =
            event.getPack().getOrCreateRegistry(NoiseAddon.NOISE_SAMPLER_TOKEN);
        event.getPack().applyLoader(DendryReturnType.class,
            (type, o, loader, depthTracker) -> DendryReturnType.valueOf(((String) o).toUpperCase()));
        noiseRegistry.register(addon.key("DENDRY"), DendryTemplate::new);
    })
    .priority(0)
    .failThrough();
```
