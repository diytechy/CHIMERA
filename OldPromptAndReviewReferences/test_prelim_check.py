from pathlib import Path
from calculate_biome_percentages import PresetAnalyzer, BiomeReader
import yaml

# Prepare test preset with plaintext stage string marker
preset_path = Path('.scripts/test_preset_prelim.yml')
preset_path.parent.mkdir(parents=True, exist_ok=True)
with open(preset_path, 'w', encoding='utf-8') as f:
    yaml.dump({'biomes': {'provider': {'pipeline': {'stages': ['***PRELIM_CHK_HERE***']}}}}, f)

pa = PresetAnalyzer(preset_path)
stages = pa.get_stage_files()
print('Stages:', stages)
assert ('INLINE', '***PRELIM_CHK_HERE***') in stages

# Prepare a stage file that contains the marker without a comment character
stage_path = Path('.scripts/stage_with_marker.yml')
with open(stage_path, 'w', encoding='utf-8') as f:
    f.write('***PRELIM_CHK_HERE***\n')

assert pa._has_prelim_check_marker(stage_path) is True

print('Prelim marker detection tests passed')
