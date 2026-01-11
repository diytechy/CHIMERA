from pathlib import Path
import yaml
from calculate_biome_percentages import PresetAnalyzer

orig = Path('biome-distribution/presets/origen2.yml')
preset = yaml.safe_load(open(orig))

stages = preset['biomes']['provider']['pipeline']['stages']
# find index of elevation.yml reference
for idx, s in enumerate(stages):
    if isinstance(s, str) and 'elevation.yml' in s:
        insert_idx = idx + 1
        break
else:
    insert_idx = len(stages)

stages.insert(insert_idx, '***PRELIM_CHK_HERE***')
# write temp preset
ptest = Path('.scripts/test_origin2_prelim.yml')
with open(ptest, 'w', encoding='utf-8') as f:
    yaml.dump(preset, f)

pa = PresetAnalyzer(ptest)
# Remove any existing placeholder
ph = Path('biomes/abstract/placeholders') / 'boreal-shallow-ocean.yml'
if ph.exists():
    ph.unlink()

# run the calculation
pa.calculate_percentages()

csv_path = Path('.scripts') / f'preliminary_biomes_{pa.preset_name}.csv'
print('CSV exists:', csv_path.exists())
if csv_path.exists():
    print(open(csv_path).read()[:1000])
print('Placeholder created:', ph.exists())
if ph.exists():
    print(open(ph).read())
else:
    print('No placeholder')
