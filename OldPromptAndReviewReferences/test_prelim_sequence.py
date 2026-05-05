from pathlib import Path
from calculate_biome_percentages import PresetAnalyzer, BiomeReader
import yaml

preset_path = Path('.scripts/test_preset_prelim2.yml')
with open(preset_path, 'w', encoding='utf-8') as f:
    yaml.dump({'biomes': {'provider': {'pipeline': {'stages': ['<< biome-distribution/stages/climate/elevation.yml:stages', '***PRELIM_CHK_HERE***']}}}}, f)

# Remove placeholder if exists
ph = Path('biomes/abstract/placeholders') / 'boreal-shallow-ocean.yml'
if ph.exists():
    ph.unlink()

pa = PresetAnalyzer(preset_path)
# Run calculate_percentages which should process the elevation stage then hit the marker
dist = pa.calculate_percentages()

csv_path = Path('.scripts') / f'preliminary_biomes_{pa.preset_name}.csv'
print('CSV exists:', csv_path.exists())
if csv_path.exists():
    print(open(csv_path).read())
print('Placeholder exists:', ph.exists())
if ph.exists():
    print(open(ph).read())
else:
    print('Placeholder was not created')
