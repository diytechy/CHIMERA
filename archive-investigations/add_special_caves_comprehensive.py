import csv
import os
import yaml
import re

# Read BiomeTable.csv to get biomes without SPECIAL_CAVES
biomes_needing_tag = set()
with open(r'c:\Projects\ORIGEN2\.artifacts\BiomeTable.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        biome_id = row['BiomeID']
        tags = row['Tags']
        if 'SPECIAL_CAVES' not in tags:
            biomes_needing_tag.add(biome_id)

print(f"Found {len(biomes_needing_tag)} biomes without SPECIAL_CAVES tag")

# Find all biome yml files
biome_files = []
for root, dirs, files in os.walk(r'c:\Projects\ORIGEN2\biomes'):
    for file in files:
        if file.endswith('.yml'):
            biome_files.append(os.path.join(root, file))

print(f"Found {len(biome_files)} biome files")

# Process each file
updated_count = 0
for filepath in biome_files:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Parse YAML to get biome ID
        try:
            data = yaml.safe_load(content)
            if not data or 'id' not in data:
                continue
            
            biome_id = data['id']
            
            # Skip if not in our list
            if biome_id not in biomes_needing_tag:
                continue
            
            # Check if file has tags section
            if 'tags' not in data:
                # No tags section, skip (abstract biomes, etc.)
                continue
            
            tags = data['tags']
            if not isinstance(tags, list):
                continue
            
            # Check if SPECIAL_CAVES already in tags
            if 'SPECIAL_CAVES' in tags:
                continue
            
            # Add SPECIAL_CAVES tag
            # Find the tags section in the file
            tags_match = re.search(r'^tags:\s*$', content, re.MULTILINE)
            if tags_match:
                # Find the next line after tags:
                start_pos = tags_match.end()
                lines = content[start_pos:].split('\n')
                
                # Find first tag line
                for i, line in enumerate(lines):
                    if line.strip() and line.strip().startswith('-'):
                        # Insert SPECIAL_CAVES before first tag
                        indent = len(line) - len(line.lstrip())
                        new_tag_line = ' ' * indent + '- SPECIAL_CAVES'
                        lines.insert(i, new_tag_line)
                        
                        # Reconstruct content
                        new_content = content[:start_pos] + '\n'.join(lines)
                        
                        # Write back
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(new_content)
                        
                        updated_count += 1
                        print(f"Updated: {biome_id}")
                        break
        except yaml.YAMLError:
            continue
            
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

print(f"\nUpdated {updated_count} biome files")
