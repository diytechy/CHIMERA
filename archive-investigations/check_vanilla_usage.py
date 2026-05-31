import csv

def vanilla_id_to_lower(vanilla_id):
    """Convert Vanilla ID (e.g., BIOME_OCEAN) to the format used in BiomeTable.csv (e.g., ocean)"""
    # Remove BIOME_ prefix and convert to lowercase
    if vanilla_id.startswith('BIOME_'):
        return vanilla_id[6:].lower()
    return vanilla_id.lower()

# Read BiomeTable.csv to extract used vanilla biome IDs
used_vanilla_ids = set()
with open('.artifacts/BiomeTable.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        vanilla_id = row.get('VanillaID', '').strip()
        if vanilla_id:
            used_vanilla_ids.add(vanilla_id)

print(f"Found {len(used_vanilla_ids)} unique vanilla biomes used in BiomeTable.csv")

# Read VanillaJavaBiomes.csv and add "Used In BiomeTable" column
rows = []
with open('VanillaJavaBiomes.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames

    # Add "Used In BiomeTable" column if it doesn't exist
    if 'Used In BiomeTable' not in fieldnames:
        fieldnames = fieldnames + ['Used In BiomeTable']

    # Process each row
    for row in reader:
        vanilla_id = vanilla_id_to_lower(row['Vanilla ID'])
        if vanilla_id in used_vanilla_ids:
            row['Used In BiomeTable'] = 'Yes'
        else:
            row['Used In BiomeTable'] = 'No'
        rows.append(row)

# Write the updated VanillaJavaBiomes.csv
with open('VanillaJavaBiomes.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"[DONE] Updated VanillaJavaBiomes.csv with 'Used In BiomeTable' column")

# Print statistics
total = len(rows)
used_count = sum(1 for row in rows if row['Used In BiomeTable'] == 'Yes')
unused_count = sum(1 for row in rows if row['Used In BiomeTable'] == 'No')

print("\nVanilla biome usage statistics:")
print(f"  Total vanilla biomes: {total}")
print(f"  Used in BiomeTable: {used_count}")
print(f"  NOT used in BiomeTable: {unused_count}")

print("\nVanilla biomes NOT used in BiomeTable:")
for row in rows:
    if row['Used In BiomeTable'] == 'No':
        print(f"  {row['Base Name']:30} | Vanilla ID: {row['Vanilla ID']:35} | Used: {row['Used In BiomeTable']}")
