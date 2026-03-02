import csv
import yaml
from pathlib import Path

biome_table = Path("C:/Projects/ORIGEN2/.artifacts/BiomeTable.csv")
biomes_dir = Path("C:/Projects/ORIGEN2/biomes")

# Read biomes without UsesElevation
biomes_without_elevation = set()
with open(biome_table, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get('UsesElevation', '').strip().lower() != 'true':
            biomes_without_elevation.add(row['BiomeID'])

# Find EQ_ files extended by these biomes
eq_files = set()
for biome_file in biomes_dir.rglob("*.yml"):
    try:
        with open(biome_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data and isinstance(data, dict):
                biome_id = data.get('id', '')
                extends = data.get('extends')
                
                if biome_id in biomes_without_elevation and extends:
                    if isinstance(extends, str) and extends.startswith('EQ_'):
                        eq_files.add(extends)
                    elif isinstance(extends, list):
                        for ext in extends:
                            if isinstance(ext, str) and ext.startswith('EQ_'):
                                eq_files.add(ext)
    except:
        pass

for eq in sorted(eq_files):
    print(eq)
