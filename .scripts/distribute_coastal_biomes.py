import yaml
from pathlib import Path

# Coastal biome distributions with integer weights
coastal_distributions = {
    'ARID_COAST_FLAT': ['BEACH', 'ARID_PALE_GARDEN_COAST', 'ORANGE_ARID_PALE_GARDEN_COAST', 'RED_ARID_PALE_GARDEN_COAST'],
    'BOREAL_COAST_HIGHLANDS': ['ROCKY_SEA_CAVES'],
    'POLAR_COAST_FLAT': ['FROZEN_BEACH', 'FROSTY_FINGERS', 'FRIGID_WASTELANDS'],
    'POLAR_COAST_HIGHLANDS': ['SNOWY_SEA_CAVES'],
    'TEMPERATE_COAST_FLAT': ['BEACH', 'SHRUB_BEACH', 'PINE_BARRENS'],
    'TEMPERATE_COAST_HIGHLANDS': [],
    'TROPICAL_COAST_FLAT': ['MUDDY_COASTS', 'PALM_BEACH', 'MANGROVE_SWAMP'],
    'TROPICAL_COAST_HIGHLANDS': ['LUSH_SEA_CAVES'],
}

coasts_file = Path("C:/Projects/ORIGEN2/biome-distribution/stages/add_coast.yml")
with open(coasts_file, 'r', encoding='utf-8') as f:
    data = yaml.safe_load(f)

stage = data['stages'][0]
to_section = stage['to']

for coast_type, biomes in coastal_distributions.items():
    if not biomes:
        continue
    
    # Use integer weights: distribute evenly
    num_biomes = len(biomes)
    weight_per_biome = 4 // num_biomes
    remainder = 4 % num_biomes
    
    to_section[coast_type] = []
    for i, biome in enumerate(biomes):
        weight = weight_per_biome + (1 if i < remainder else 0)
        to_section[coast_type].append({biome: weight})
    
    total_weight = sum(w for item in to_section[coast_type] for w in item.values())
    to_section[coast_type].append({'SELF': total_weight})

with open(coasts_file, 'w', encoding='utf-8') as f:
    yaml.dump(data, f, default_flow_style=False, sort_keys=False)

print("Updated add_coast.yml with integer weights")
for coast_type, biomes in coastal_distributions.items():
    if biomes:
        weights = to_section[coast_type]
        print(f"  {coast_type}: {weights}")
