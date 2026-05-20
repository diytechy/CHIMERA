import csv
import os
import yaml

# Read BiomeTable.csv
biomes_needing_tag = []
with open(r'c:\Projects\ORIGEN2\.artifacts\BiomeTable.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        biome_id = row['BiomeID']
        tags = row['Tags']
        
        # Skip if already has SPECIAL_CAVES tag
        if 'SPECIAL_CAVES' not in tags:
            biomes_needing_tag.append(biome_id)

print(f"Found {len(biomes_needing_tag)} biomes without SPECIAL_CAVES tag")
print(f"\nFirst 20 biomes: {biomes_needing_tag[:20]}")
