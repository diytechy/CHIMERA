#!/usr/bin/env python3
"""
Script to ensure all RIVER-type biomes have 'LAND_CAVES' in their tags section,
but only when it is not already inherited via the extends chain.
"""

import csv
import re
import yaml
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
CSV_PATH = SCRIPT_DIR / ".artifacts" / "BiomeTable.csv"
BIOMES_DIR = SCRIPT_DIR / "biomes"


# ---------------------------------------------------------------------------
# Step 1: Load all biome YAML files into a lookup map
# ---------------------------------------------------------------------------

def load_all_biomes():
    """Return dict: biome_id -> {file, extends: list[str], tags: list[str]}"""
    biomes = {}
    for yml_file in BIOMES_DIR.rglob("*.yml"):
        try:
            data = yaml.safe_load(yml_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not data or not isinstance(data, dict):
            continue
        biome_id = data.get("id")
        if not biome_id:
            continue

        extends = data.get("extends") or []
        if not isinstance(extends, list):
            extends = [extends]
        extends = [str(e) for e in extends if e]

        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags]
        tags = [str(t) for t in tags if t]

        biomes[biome_id] = {
            "file": yml_file,
            "extends": extends,
            "tags": tags,
        }
    return biomes


# ---------------------------------------------------------------------------
# Step 2: Resolve effective (inherited) tags by walking the extends chain
# ---------------------------------------------------------------------------

def get_inherited_tags(biome_id, biomes, _visited=None):
    """
    Return the set of tags that biome_id inherits from its extends chain
    (NOT including its own tags — only what parents contribute).
    """
    if _visited is None:
        _visited = set()
    if biome_id in _visited or biome_id not in biomes:
        return set()
    _visited.add(biome_id)

    result = set()
    for parent_id in biomes[biome_id]["extends"]:
        if parent_id in biomes:
            result |= set(biomes[parent_id]["tags"])
            result |= get_inherited_tags(parent_id, biomes, _visited)
    return result


# ---------------------------------------------------------------------------
# Step 3: CSV — find all river biome IDs
# ---------------------------------------------------------------------------

def get_river_biome_ids():
    """Return set of BiomeIDs where Category == RIVER."""
    river_ids = set()
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("Category", "").strip().upper() == "RIVER":
                river_ids.add(row["BiomeID"].strip())
    return river_ids


# ---------------------------------------------------------------------------
# Step 4: Text-based YAML editing (preserves comments and formatting)
# ---------------------------------------------------------------------------

def file_has_land_caves_tag(text):
    """Check whether LAND_CAVES appears directly in the file's tags section."""
    in_tags = False
    for line in text.splitlines():
        if re.match(r"^tags\s*:", line):
            in_tags = True
            continue
        if in_tags:
            stripped = line.strip()
            if re.match(r"^-\s*LAND_CAVES\s*$", stripped):
                return True
            # End of tags block: non-indented, non-empty, non-comment line
            if stripped and not stripped.startswith("-") and not stripped.startswith("#"):
                if not line[0].isspace():
                    break
    return False


def add_land_caves_to_text(text):
    """
    Add LAND_CAVES to an existing tags: block, or create a new tags: block
    before features: (or at end of file). Preserves all existing content.
    """
    lines = text.splitlines(keepends=True)

    # Find existing tags: block
    tags_idx = None
    for i, line in enumerate(lines):
        if re.match(r"^tags\s*:", line):
            tags_idx = i
            break

    if tags_idx is not None:
        # Append after the last item in the tags block
        insert_after = tags_idx
        for i in range(tags_idx + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("-") or stripped.startswith("#") or stripped == "":
                insert_after = i
            else:
                if not lines[i][0].isspace():
                    break
        lines.insert(insert_after + 1, "- LAND_CAVES\n")
    else:
        # Create a new tags: block before features: (or at end)
        insert_before = None
        for i, line in enumerate(lines):
            if re.match(r"^features\s*:", line):
                insert_before = i
                break

        tag_block = "tags:\n- LAND_CAVES\n"
        if insert_before is not None:
            lines.insert(insert_before, tag_block)
        else:
            if lines and not lines[-1].endswith("\n"):
                lines.append("\n")
            lines.append(tag_block)

    return "".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Loading all biome YAML files from: {BIOMES_DIR}")
    biomes = load_all_biomes()
    print(f"  Loaded {len(biomes)} biomes")

    print(f"Reading river biomes from: {CSV_PATH}")
    river_ids = get_river_biome_ids()
    print(f"  Found {len(river_ids)} RIVER-type biomes\n")

    skipped_inherited = []
    skipped_direct   = []
    updated          = []
    missing          = []

    for biome_id in sorted(river_ids):
        if biome_id not in biomes:
            missing.append(biome_id)
            continue

        own_tags      = set(biomes[biome_id]["tags"])
        inherited     = get_inherited_tags(biome_id, biomes)
        effective     = own_tags | inherited

        if "LAND_CAVES" not in effective:
            # Need to add it directly to this file
            yml_file = biomes[biome_id]["file"]
            text     = yml_file.read_text(encoding="utf-8")
            new_text = add_land_caves_to_text(text)
            yml_file.write_text(new_text, encoding="utf-8")
            updated.append((biome_id, yml_file.relative_to(SCRIPT_DIR)))
            inherited_from = "none"
            print(f"  [UPDATED]  {biome_id}")
        elif "LAND_CAVES" in inherited and "LAND_CAVES" not in own_tags:
            # Already satisfied by inheritance — do nothing
            source = next(
                (p for p in biomes[biome_id]["extends"] if "LAND_CAVES" in get_inherited_tags(p, biomes) | set(biomes.get(p, {}).get("tags", []))),
                "unknown"
            )
            skipped_inherited.append((biome_id, source))
        else:
            # Has it directly in own tags
            skipped_direct.append(biome_id)

    print()
    print("=== Summary ===")
    print(f"Updated (added LAND_CAVES):         {len(updated)}")
    print(f"Skipped (inherited from extends):   {len(skipped_inherited)}")
    print(f"Skipped (already in own tags):      {len(skipped_direct)}")
    print(f"Not found (no YAML):                {len(missing)}")

    if skipped_inherited:
        print("\nInherited from extends chain:")
        for biome_id, source in sorted(skipped_inherited):
            print(f"  {biome_id:45s}  (via {source})")

    if skipped_direct:
        print("\nAlready had LAND_CAVES directly:")
        for b in sorted(skipped_direct):
            print(f"  {b}")

    if missing:
        print("\nNo YAML file found:")
        for b in sorted(missing):
            print(f"  {b}")


if __name__ == "__main__":
    main()
