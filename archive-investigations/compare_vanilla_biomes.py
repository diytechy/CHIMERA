import csv

def vanilla_id_to_lower(vanilla_id):
    """Convert Vanilla ID (e.g., BIOME_OCEAN) to the format used in BiomeTable.csv (e.g., ocean)"""
    # Remove BIOME_ prefix and convert to lowercase
    if vanilla_id.startswith('BIOME_'):
        return vanilla_id[6:].lower()
    return vanilla_id.lower()

# Read VanillaJavaBiomes.csv to extract vanilla biome IDs
vanilla_ids = set()
print("Vanilla biome IDs found:")
with open('VanillaJavaBiomes.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        biome_id = vanilla_id_to_lower(row['Vanilla ID'])
        vanilla_ids.add(biome_id)
        print(f"  - {biome_id}")

# Read BiomeTable.csv and add the "In Vanilla" column
rows = []
with open('.artifacts/BiomeTable.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames

    # Add "In Vanilla" column if it doesn't exist
    if 'In Vanilla' not in fieldnames:
        fieldnames = fieldnames + ['In Vanilla']

    # Process each row
    for row in reader:
        vanilla_id = row.get('VanillaID', '').strip()
        if vanilla_id and vanilla_id in vanilla_ids:
            row['In Vanilla'] = 'Yes'
        else:
            row['In Vanilla'] = 'No'
        rows.append(row)

# Write the updated BiomeTable.csv
with open('.artifacts/BiomeTable.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"\n[DONE] Updated BiomeTable.csv with 'In Vanilla' column")

# Print statistics
total = len(rows)
in_vanilla_count = sum(1 for row in rows if row['In Vanilla'] == 'Yes')
not_in_vanilla_count = sum(1 for row in rows if row['In Vanilla'] == 'No')

print("\nVanilla biome coverage statistics:")
print(f"  Total rows in BiomeTable: {total}")
print(f"  Rows with vanilla biomes: {in_vanilla_count}")
print(f"  Rows without vanilla biomes: {not_in_vanilla_count}")

# Show some examples
print("\nExamples of biomes IN vanilla:")
for i, row in enumerate(rows):
    if row['In Vanilla'] == 'Yes' and i < 10:
        print(f"  {row['BiomeID']:30} | VanillaID: {row['VanillaID']:25} | In Vanilla: {row['In Vanilla']}")

print("\nExamples of biomes NOT in vanilla:")
count = 0
for row in rows:
    if row['In Vanilla'] == 'No' and count < 10:
        print(f"  {row['BiomeID']:30} | VanillaID: {row['VanillaID']:25} | In Vanilla: {row['In Vanilla']}")
        count += 1
