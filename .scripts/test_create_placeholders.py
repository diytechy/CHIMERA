from pathlib import Path
from calculate_biome_percentages import PresetAnalyzer, BiomeReader

# Need a minimal preset file for analyzer
preset_path = Path('.scripts/test_preset_prelim.yml')
pa = PresetAnalyzer(preset_path)

# Ensure test biome does not exist
test_biome = 'TEST_PLACEHOLDER_ISLAND'
# Remove any existing placeholder if present
ph = Path('biomes/abstract/placeholders') / f"{test_biome}.yml"
if ph.exists():
    ph.unlink()

# Call the check routine directly
pa._check_and_create_placeholder_biomes(set([test_biome]))

# Verify file created
assert ph.exists(), f"Placeholder not created: {ph}"
print('Placeholder file created:', ph)

# Verify BiomeReader can find it (cache was refreshed)
found = BiomeReader.find_biome_file(test_biome)
assert found is not None and Path(found).exists(), 'BiomeReader did not find the created placeholder'
print('BiomeReader now finds the placeholder:', found)

# Cleanup
#ph.unlink()
print('Placeholder creation test passed')
