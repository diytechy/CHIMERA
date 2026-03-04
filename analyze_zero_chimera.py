import csv
import re

# Read the BiomeTable.csv
biome_data = {}
with open('.artifacts/BiomeTable.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        biome_data[row['BiomeID']] = row

# Filter for 0% CHIMERA biomes
zero_chimera = {}
for biome_id, row in biome_data.items():
    if row['CHIMERA'] == '0.0000%':
        zero_chimera[biome_id] = row

# Sort by biome ID
sorted_zero = sorted(zero_chimera.items())

print(f"Found {len(sorted_zero)} biomes with 0% in CHIMERA\n")
print("=" * 150)

# Categorize biomes
for biome_id, row in sorted_zero:
    source = row.get('Source', 'N/A')
    category = row.get('Category', 'N/A')
    extends = row.get('Extends', '')
    elevation = float(row.get('Elevation', 0.5))
    biome_type = row.get('Type', '')
    
    print(f"\nBiomeID: {biome_id}")
    print(f"  Source: {source}")
    print(f"  Category: {category}")
    print(f"  Type: {biome_type}")
    print(f"  Elevation: {elevation} (Flat={elevation < 0.7}, Highland={elevation >= 0.7})")
    print(f"  Extends: {extends[:100]}")
