import yaml
from pathlib import Path
from collections import defaultdict

BIOMES_DIR = Path("biomes")

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

def get_features_from_parent(parent_id):
    """Get features from a parent biome, recursively if needed."""
    parent_file = find_biome_file(parent_id)
    if not parent_file:
        return None
    
    try:
        with open(parent_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        # If this parent has features, return them
        if data and data.get("features"):
            return data.get("features")
        
        # Otherwise, check its extends
        extends = data.get("extends", [])
        if not isinstance(extends, list):
            extends = [extends] if extends else []
        
        for parent in extends:
            features = get_features_from_parent(parent)
            if features:
                return features
    except Exception:
        pass
    
    return None

# Find all river biomes (extend EQ_GLOBAL_RIVER)
river_biomes = {}
for f in BIOMES_DIR.rglob("*.yml"):
    try:
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data and data.get("type") == "BIOME":
            biome_id = data.get("id")
            extends = data.get("extends", [])
            if not isinstance(extends, list):
                extends = [extends] if extends else []
            
            # Check if extends contains EQ_GLOBAL_RIVER
            if biome_id and any("EQ_GLOBAL_RIVER" in str(e) for e in extends):
                river_biomes[biome_id] = {"file": f, "extends": extends, "data": data}
    except Exception:
        continue

print(f"Found {len(river_biomes)} biomes extending EQ_GLOBAL_RIVER\n")

updated = []
skipped = defaultdict(list)

for biome_id in sorted(river_biomes.keys()):
    info = river_biomes[biome_id]
    biome_file = info["file"]
    extends = info["extends"]
    data = info["data"]
    
    # Check if it already has features
    if data.get("features"):
        # Check if postprocessors already has RIVER_SOULSAND
        features = data.get("features", {})
        if isinstance(features, dict):
            postprocessors = features.get("postprocessors", [])
            if not isinstance(postprocessors, list):
                postprocessors = [postprocessors] if postprocessors else []
            
            if "RIVER_SOULSAND" in postprocessors:
                skipped["already_has_postprocessor"].append(biome_id)
            else:
                # Add postprocessor to existing features
                postprocessors.append("RIVER_SOULSAND")
                features["postprocessors"] = postprocessors
                data["features"] = features
                
                with open(biome_file, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
                
                updated.append((biome_id, "postprocessor_added", None))
                print(f"[+] {biome_id}: added RIVER_SOULSAND to existing features postprocessors")
        else:
            skipped["features_not_dict"].append(biome_id)
        continue
    
    # Find features from first extending parent
    features = None
    source_parent = None
    for parent_id in extends:
        features = get_features_from_parent(parent_id)
        if features:
            source_parent = parent_id
            break
    
    if not features:
        skipped["no_features_in_parents"].append(biome_id)
        continue
    
    # Make a copy of features and ensure it's a dict
    if isinstance(features, dict):
        features = dict(features)
    else:
        # If features is not a dict, create one
        features = {}
    
    # Add postprocessors
    postprocessors = features.get("postprocessors", [])
    if not isinstance(postprocessors, list):
        postprocessors = [postprocessors] if postprocessors else []
    
    if "RIVER_SOULSAND" not in postprocessors:
        postprocessors.append("RIVER_SOULSAND")
    features["postprocessors"] = postprocessors
    
    # Add features to biome
    data["features"] = features
    
    # Write back to file
    with open(biome_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    updated.append((biome_id, "features_copied", source_parent))
    print(f"[+] {biome_id}: copied features from {source_parent}, added RIVER_SOULSAND postprocessor")

print(f"\n{'='*70}")
print(f"Updated: {len(updated)}")
if skipped:
    print(f"Skipped:")
    for reason, biomes in sorted(skipped.items()):
        print(f"  {reason}: {len(biomes)}")
        if len(biomes) <= 10:
            for b in sorted(biomes):
                print(f"    - {b}")
        else:
            for b in sorted(biomes)[:5]:
                print(f"    - {b}")
            print(f"    ... +{len(biomes)-5} more")
