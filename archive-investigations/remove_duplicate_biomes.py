import yaml
from pathlib import Path
from collections import defaultdict

biomes_dir = Path("C:/Projects/ORIGEN2/biomes")

# Find all yml files and group by id
biomes_by_id = defaultdict(list)

for yml_file in biomes_dir.rglob("*.yml"):
    try:
        with open(yml_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            if data and isinstance(data, dict) and 'id' in data:
                biome_id = data['id']
                file_size = yml_file.stat().st_size
                biomes_by_id[biome_id].append((yml_file, file_size))
    except:
        pass

# Find and remove duplicates
for biome_id, files in biomes_by_id.items():
    if len(files) > 1:
        # Sort by size descending, keep largest
        files.sort(key=lambda x: x[1], reverse=True)
        print(f"\n{biome_id}: Found {len(files)} files")
        
        for i, (file_path, size) in enumerate(files):
            if i == 0:
                print(f"  KEEP: {file_path} ({size} bytes)")
            else:
                print(f"  DELETE: {file_path} ({size} bytes)")
                file_path.unlink()
