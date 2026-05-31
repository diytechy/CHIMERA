import yaml
from pathlib import Path

wetland_extends = ['EQ_BOG', 'EQ_WARPED_WETLANDS', 'EQ_SWAMP', 'EQ_MANGROVE_SWAMP', 'EQ_CELL_MARSH']
biomes_dir = Path("C:/Projects/ORIGEN2/biomes")

updated = 0
for biome_file in biomes_dir.rglob("*.yml"):
    try:
        with open(biome_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data or 'extends' not in data:
            continue
        
        extends = data['extends']
        if not isinstance(extends, list):
            extends = [extends]
        
        # Check if has wetland extend
        has_wetland = any(w in extends for w in wetland_extends)
        has_carving = 'EQ_CARVING_LAND' in extends
        
        if has_wetland and has_carving:
            extends.remove('EQ_CARVING_LAND')
            data['extends'] = extends
            
            with open(biome_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            
            updated += 1
            print(f"Removed EQ_CARVING_LAND from {data.get('id', biome_file.name)}")
    except:
        pass

print(f"\nTotal updated: {updated}")
