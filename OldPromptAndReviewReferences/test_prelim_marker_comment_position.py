from pathlib import Path
from calculate_biome_percentages import PresetAnalyzer
import yaml

# Create preset where the marker is a commented line after elevation stage
orig = Path('biome-distribution/presets/origen2.yml')
preset = yaml.safe_load(open(orig))
# Find elevation stage line and insert a comment marker after it in the file text
text = open(orig, 'r', encoding='utf-8').read().splitlines()
new_text = []
for i, line in enumerate(text):
    new_text.append(line)
    if 'climate/elevation.yml:stages' in line:
        new_text.append('        # ***PRELIM_CHK_HERE***')

ptest = Path('.scripts/test_origin2_prelim_comment.yml')
with open(ptest, 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_text) + '\n')

pa = PresetAnalyzer(ptest)
stages = pa.get_stage_files()
print('Stage refs now include marker? ', ('INLINE','***PRELIM_CHK_HERE***') in stages)
print('Stages order:')
for s in stages[:12]:
    print(' ', s)

# Run calculation to ensure placeholders are created
ph = Path('biomes/abstract/placeholders') / 'boreal-shallow-ocean.yml'
if ph.exists():
    ph.unlink()

pa.calculate_percentages()
print('Placeholder created:', ph.exists())
if ph.exists():
    print(open(ph).read())
else:
    print('Not created')
