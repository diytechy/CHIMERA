import yaml
import re
from pathlib import Path

eq_files = [
    ("EQ_ERODED_MOUNTAINS", "biomes/abstract/terrain/land/legacy/eq_eroded_mountains.yml"),
    ("EQ_ERODED_VALLEY_MOUNTAINS", "biomes/rearth/base/eq_eroded_valley_mountains.yml"),
    ("EQ_GLACIAL_OVERHANGS", "biomes/equations/biome_specific/eq_glacial_overhangs.yml"),
    ("EQ_HILLS", "biomes/abstract/terrain/land/legacy/eq_hills.yml"),
    ("EQ_LOWLAND_HILLS", "biomes/rearth/base/eq_lowland_hillds.yml"),
    ("EQ_MOUNTAIN_SPOTS", "biomes/rearth/base/eq_mountain_spots.yml"),
    ("EQ_PILLARS", "biomes/rearth/base/eq_pillars.yml"),
    ("EQ_SMALL_MOUNTAINS", "biomes/equations/eq_small_mountains.yml"),
    ("EQ_SNOWDRIFT_COASTS", "biomes/equations/biome_specific/eq_snowdrift_coasts.yml"),
    ("EQ_TERRACED_MOUNTAINS", "biomes/equations/eq_terraced_mountains.yml"),
    ("EQ_TERRACE_MOUNTAINS", "biomes/rearth/base/eq_terrace_mountain.yml"),
    ("EQ_TILTED_PLATEAU", "biomes/rearth/base/eq_tilted_plateau.yml"),
    ("EQ_PLAINS", "biomes/equations/eq_plains.yml"),
    ("EQ_FLAT_BUMPY", "biomes/abstract/terrain/land/legacy/eq_flat_bumpy.yml"),
    ("EQ_FLAT_ERODED", "biomes/abstract/terrain/land/legacy/eq_flat_eroded.yml"),
    ("EQ_CRACKED_FLATS", "biomes/abstract/terrain/land/legacy/eq_cracked_flats.yml"),
    ("EQ_BUTTES", "biomes/abstract/terrain/land/legacy/eq_buttes.yml"),
    ("EQ_BOG", "biomes/equations/eq_bog.yml"),
    ("EQ_WARPED_WETLANDS", "biomes/abstract/terrain/land/legacy/eq_warped_wetlands.yml"),
    ("EQ_SWAMP", "biomes/abstract/terrain/land/legacy/eq_swamp.yml"),
    ("EQ_MANGROVE_SWAMP", "biomes/abstract/terrain/land/legacy/eq_mangrove_swamp.yml"),
    ("EQ_CELL_MARSH", "biomes/abstract/terrain/land/legacy/eq_cell_marsh.yml"),
]

base_dir = Path("C:/Projects/ORIGEN2")

for eq_id, rel_path in eq_files:
    eq_file = base_dir / rel_path
    if not eq_file.exists():
        print(f"SKIP: {eq_id} - file not found")
        continue
    
    with open(eq_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if base is set to terrain-base-y-level or legacy-terrain-base-y-level
    if 'terrain-base-y-level' not in content and 'legacy-terrain-base-y-level' not in content:
        print(f"SKIP: {eq_id} - no terrain-base-y-level")
        continue
    
    # Check if already has BiomeShapeLandmassBaseOffset
    if 'BiomeShapeLandmassBaseOffset' in content:
        print(f"SKIP: {eq_id} - already has BiomeShapeLandmassBaseOffset")
        continue
    
    # Replace -y + base with -y+base+BiomeShapeLandmassBaseOffset(x,z)
    original = content
    content = re.sub(r'-y\s*\+\s*base\b', '-y+base+BiomeShapeLandmassBaseOffset(x,z)', content)
    
    if content != original:
        with open(eq_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"UPDATED: {eq_id}")
    else:
        print(f"SKIP: {eq_id} - no -y + base pattern found")
