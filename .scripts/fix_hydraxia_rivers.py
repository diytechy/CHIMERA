import yaml
from pathlib import Path
from collections import defaultdict

BIOMES_DIR = Path("biomes")

# Explicit mappings
FROSTBITE_BIOMES = {"FROZEN_SPIRES", "SEARING_TORS", "ARCTIC_MESA", "PERMAFROST_CLIFFS"}
CHILLY_CREEK_BIOMES = {"SUGAR_PINE_WOODLANDS", "REDWOOD_WOODLANDS", "ICEBOUND_JUNGLE"}

def find_biome_file(biome_id):
    """Find the biome YAML file for a given biome ID."""
    for f in BIOMES_DIR.rglob("*.yml"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data and data.get("id") == biome_id:
                return f
        except Exception:
            continue
    return None

def has_river_tag(tags):
    """Check if tags list contains any USE_*RIVER* tag."""
    return any(t.startswith("USE_") and "RIVER" in t for t in (tags or []))

def get_first_river_tag(tags):
    """Get the first USE_*RIVER* tag from tags list."""
    for t in (tags or []):
        if t.startswith("USE_") and "RIVER" in t:
            return t
    return None

def replace_river_tag(tags, old_tag, new_tag):
    """Replace a river tag in the tags list."""
    if not tags:
        return [new_tag]
    return [new_tag if t == old_tag else t for t in tags]

# Build map of all BASE_HYDRAXIA biomes
hydraxia_biomes = {}
for f in BIOMES_DIR.rglob("*.yml"):
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data and data.get("type") == "BIOME":
            biome_id = data.get("id")
            extends = data.get("extends", [])
            if not isinstance(extends, list):
                extends = [extends] if extends else []
            
            # Check if extends contains BASE_HYDRAXIA
            if biome_id and any("BASE_HYDRAXIA" in str(e) for e in extends):
                hydraxia_biomes[biome_id] = f
    except Exception:
        continue

print(f"Found {len(hydraxia_biomes)} biomes with BASE_HYDRAXIA in extends\n")

updated = []
skipped = defaultdict(list)

# Process explicit replacements
for biome_id in FROSTBITE_BIOMES | CHILLY_CREEK_BIOMES:
    biome_file = find_biome_file(biome_id)
    if not biome_file:
        skipped["not_found"].append(biome_id)
        continue
    
    with open(biome_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    tags = data.get("tags", []) or []
    old_tag = get_first_river_tag(tags)
    
    if not old_tag:
        skipped["no_river_tag"].append(biome_id)
        continue
    
    # Determine replacement tag
    if biome_id in FROSTBITE_BIOMES:
        new_tag = "USE_FROSTBITE_RIVERS"
    else:
        new_tag = "USE_CHILLY_CREEK_RIVER"
    
    if old_tag == new_tag:
        skipped["already_correct"].append(biome_id)
        continue
    
    # Replace the tag
    tags = replace_river_tag(tags, old_tag, new_tag)
    data["tags"] = tags
    
    with open(biome_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    updated.append((biome_id, old_tag, new_tag))
    print(f"[+] {biome_id}: {old_tag} -> {new_tag}")

# Process other BASE_HYDRAXIA biomes
print()
for biome_id in sorted(hydraxia_biomes.keys()):
    # Skip if already processed
    if biome_id in (FROSTBITE_BIOMES | CHILLY_CREEK_BIOMES):
        continue
    
    biome_file = hydraxia_biomes[biome_id]
    with open(biome_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    tags = data.get("tags", []) or []
    old_tag = get_first_river_tag(tags)
    
    if not old_tag:
        skipped["hydraxia_no_river"].append(biome_id)
        continue
    
    # Already correct?
    if old_tag in ("USE_CHILLY_CREEK_RIVER", "USE_FROSTBITE_RIVERS"):
        skipped["hydraxia_already_correct"].append(biome_id)
        continue
    
    # Replace with USE_DRAFTY_STREAM_RIVER
    new_tag = "USE_DRAFTY_STREAM_RIVER"
    tags = replace_river_tag(tags, old_tag, new_tag)
    data["tags"] = tags
    
    with open(biome_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    updated.append((biome_id, old_tag, new_tag))
    print(f"[+] {biome_id}: {old_tag} -> {new_tag}")

print(f"\n{'='*70}")
print(f"Updated: {len(updated)}")
print(f"Skipped:")
for reason, biomes in sorted(skipped.items()):
    print(f"  {reason}: {len(biomes)} - {', '.join(sorted(biomes)[:5])}" + 
          (f" ... +{len(biomes)-5} more" if len(biomes) > 5 else ""))
