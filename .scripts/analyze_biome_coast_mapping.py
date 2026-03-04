import csv
import yaml
from pathlib import Path

# Read BiomeTable.csv
biome_table_path = Path("C:/Projects/ORIGEN2/.artifacts/BiomeTable.csv")
biomes_by_id = {}

with open(biome_table_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        biomes_by_id[row['BiomeID']] = row

# Read set_biomes_in_climates_origen.yml to understand biome placement
climates_path = Path("C:/Projects/ORIGEN2/biome-distribution/stages/set_biomes_in_climates_origen.yml")
with open(climates_path, 'r', encoding='utf-8') as f:
    climates_data = yaml.safe_load(f)

# Build mapping of biome to climate category
biome_to_climate = {}
for stage in climates_data.get('stages', []):
    if stage.get('type') == 'REPLACE_LIST':
        for key, value in stage.get('to', {}).items():
            if isinstance(value, dict):
                for biome_list in value.values():
                    if isinstance(biome_list, list):
                        for item in biome_list:
                            if isinstance(item, dict):
                                for biome_name in item.keys():
                                    biome_to_climate[biome_name] = key

# Known specific coast biomes
specific_coasts = {
    'ARID_PALE_GARDEN': 'ARID_PALE_GARDEN_COAST',
    'ORANGE_ARID_PALE_GARDEN': 'ORANGE_ARID_PALE_GARDEN_COAST',
    'PALE_GARDEN': 'PALE_GARDEN_COAST',
    'POLAR_PALE_GARDEN': 'POLAR_PALE_GARDEN_COAST',
    'RED_ARID_PALE_GARDEN': 'RED_ARID_PALE_GARDEN_COAST',
    'POLAR_MUSHROOM_FIELDS': 'POLAR_MUSHROOM_COAST',
    'MUSHROOM_FIELDS': 'MUSHROOM_COAST',
    'TROPICAL_MUSHROOM_FIELDS': 'TROPICAL_MUSHROOM_COAST'
}

# Filter land biomes (not rivers, not wetlands)
land_biomes = []
for biome_id, data in biomes_by_id.items():
    origin = data.get('Origin', '').strip()
    extends = data.get('Extends', '').upper()
    
    # Check if land origin
    if origin != 'Land':
        continue
    
    # Check if river
    if 'RIVER' in extends or data.get('IsRiver', '').strip().lower() == 'true':
        continue
    
    # Check if wetland
    if any(x in extends for x in ['BOG', 'WETLAND', 'SWAMP', 'MARSH']):
        continue
    
    land_biomes.append(biome_id)

# Determine coast mapping for each biome
results = []
for biome_id in sorted(land_biomes):
    # Check for direct coast match
    coast_match = f"{biome_id}_COAST"
    if coast_match in biomes_by_id:
        results.append((biome_id, coast_match, 'direct'))
        continue
    
    # Check specific coast mapping
    if biome_id in specific_coasts:
        results.append((biome_id, specific_coasts[biome_id], 'specific'))
        continue
    
    # Determine from climate placement
    climate = biome_to_climate.get(biome_id, '')
    
    # Map climate to coast type
    coast_type = None
    if 'polar' in climate or 'ice-cap' in climate or 'tundra' in climate:
        if 'flat' in climate:
            coast_type = 'polar-coast-flat'
        elif 'highland' in climate:
            coast_type = 'polar-coast-highlands'
        else:
            coast_type = 'polar-coast-flat'
    elif 'boreal' in climate:
        if 'flat' in climate:
            coast_type = 'boreal-coast-flat'
        elif 'highland' in climate:
            coast_type = 'boreal-coast-highlands'
        else:
            coast_type = 'boreal-coast-flat'
    elif 'temperate' in climate:
        if 'flat' in climate:
            coast_type = 'temperate-coast-flat'
        elif 'highland' in climate:
            coast_type = 'temperate-coast-highlands'
        else:
            coast_type = 'temperate-coast-flat'
    elif 'tropical' in climate or 'hot' in climate:
        if 'flat' in climate:
            coast_type = 'tropical-coast-flat'
        elif 'highland' in climate:
            coast_type = 'tropical-coast-highlands'
        else:
            coast_type = 'tropical-coast-flat'
    elif 'desert' in climate or 'steppe' in climate or 'arid' in climate:
        if 'flat' in climate:
            coast_type = 'arid-coast-flat'
        elif 'highland' in climate:
            coast_type = 'arid-coast-highlands'
        else:
            coast_type = 'arid-coast-flat'
    else:
        coast_type = 'temperate-coast-flat'  # default
    
    results.append((biome_id, coast_type, f'inferred from {climate}'))

# Write results
output_path = Path("C:/Projects/ORIGEN2/.artifacts/BIOME_COAST_MAPPING.md")
with open(output_path, 'w', encoding='utf-8') as f:
    f.write("# Biome to Coast Mapping\n\n")
    f.write(f"Total land biomes analyzed: {len(results)}\n\n")
    
    f.write("## Direct Coast Matches\n\n")
    f.write("| Biome | Coast | Notes |\n")
    f.write("|-------|-------|-------|\n")
    for biome, coast, method in results:
        if method == 'direct':
            f.write(f"| {biome} | {coast} | Direct match |\n")
    
    f.write("\n## Specific Coast Mappings\n\n")
    f.write("| Biome | Coast | Notes |\n")
    f.write("|-------|-------|-------|\n")
    for biome, coast, method in results:
        if method == 'specific':
            f.write(f"| {biome} | {coast} | Specific mapping |\n")
    
    f.write("\n## Inferred Coast Mappings\n\n")
    f.write("| Biome | Coast | Climate Source |\n")
    f.write("|-------|-------|----------------|\n")
    for biome, coast, method in results:
        if method.startswith('inferred'):
            f.write(f"| {biome} | {coast} | {method} |\n")

print(f"Analysis complete. Results written to {output_path}")
print(f"Total biomes: {len(results)}")
print(f"  Direct matches: {sum(1 for _, _, m in results if m == 'direct')}")
print(f"  Specific mappings: {sum(1 for _, _, m in results if m == 'specific')}")
print(f"  Inferred mappings: {sum(1 for _, _, m in results if m.startswith('inferred'))}")
