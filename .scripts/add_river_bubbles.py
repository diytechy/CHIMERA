import re
from pathlib import Path

BIOMES_DIR = Path("biomes")

# Find all biome files
biome_files = list(BIOMES_DIR.rglob("*.yml"))

print(f"Found {len(biome_files)} yml files\n")

updated = []
skipped = []
errors = []

for biome_file in sorted(biome_files):
    try:
        with open(biome_file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Check if file contains "type: BIOME"
        if "type: BIOME" not in content:
            continue
        
        # Check if file contains "- RIVER_SOULSAND" (with proper indentation)
        if "- RIVER_SOULSAND" not in content:
            continue
        
        # Check if RIVER_BUBBLES already exists
        if "- RIVER_BUBBLES" in content:
            # Extract biome ID if possible
            biome_match = re.search(r'id:\s*(\S+)', content)
            if biome_match:
                skipped.append(biome_match.group(1))
            continue
        
        # Replace "- RIVER_SOULSAND" with "- RIVER_SOULSAND\n  - RIVER_BUBBLES"
        # This preserves indentation by looking at the actual indentation of RIVER_SOULSAND
        pattern = r'([ \t]*)- RIVER_SOULSAND'
        replacement = r'\1- RIVER_SOULSAND\n\1- RIVER_BUBBLES'
        
        new_content = re.sub(pattern, replacement, content)
        
        # Only write if content actually changed
        if new_content != content:
            with open(biome_file, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            # Extract biome ID
            biome_match = re.search(r'id:\s*(\S+)', content)
            if biome_match:
                updated.append(biome_match.group(1))
            print(f"[+] {biome_file.name}")
    except Exception as e:
        errors.append((biome_file, str(e)))

print(f"\n{'='*70}")
print(f"Updated: {len(updated)}")
if skipped:
    print(f"Skipped (already have RIVER_BUBBLES): {len(skipped)}")
    if len(skipped) <= 5:
        for b in sorted(skipped):
            print(f"  - {b}")
    else:
        for b in sorted(skipped)[:5]:
            print(f"  - {b}")
        print(f"  ... +{len(skipped)-5} more")
if errors:
    print(f"Errors: {len(errors)}")
    for f, e in errors[:3]:
        print(f"  {f}: {e}")
