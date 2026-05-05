from pathlib import Path
import shutil
import yaml
import sys

# Ensure .scripts is on the import path so we can import the module
sys.path.insert(0, str(Path('.scripts').resolve()))
from calculate_biome_percentages import BiomeReader

# Prepare a temporary test biomes directory
test_dir = Path('biomes/test_merge')
if test_dir.exists():
    shutil.rmtree(test_dir)
test_dir.mkdir(parents=True, exist_ok=True)

# Parent biome with LAND_CAVES and vanilla mapping
parent = {
    'type': 'BIOME',
    'id': 'PARENT_BIOME',
    'tags': ['LAND_CAVES'],
    'vanilla': 'minecraft:plains'
}
with open(test_dir / 'parent.yml', 'w', encoding='utf-8') as f:
    yaml.safe_dump(parent, f)

# Child biome that extends parent and adds USE_RIVER and SPECIAL_CAVES
child = {
    'type': 'BIOME',
    'id': 'CHILD_BIOME',
    'extends': 'PARENT_BIOME',
    'tags': ['USE_RIVER', 'SPECIAL_CAVES']
}
with open(test_dir / 'child.yml', 'w', encoding='utf-8') as f:
    yaml.safe_dump(child, f)

# Reset BiomeReader cache and rebuild from test dir
BiomeReader.reset_cache()
BiomeReader.build_cache(biomes_dir=test_dir)

# Read metadata for child and assert merged properties
meta = BiomeReader.read_biome_metadata('CHILD_BIOME')
assert meta.land_caves is True, 'LAND_CAVES should be inherited from parent'
assert meta.special_caves is True, 'SPECIAL_CAVES should be present on child'
assert meta.caverns_land is False, 'CAVERNS_LAND should be absent'
assert meta.river == 'General', f"Expected river 'General', got '{meta.river}'"
assert meta.vanilla_match == 'plains', f"Expected vanilla_match 'plains', got '{meta.vanilla_match}'"

print('test_biome_metadata_merge passed')