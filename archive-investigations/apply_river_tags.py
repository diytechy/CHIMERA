#!/usr/bin/env python3
"""
apply_river_tags.py

Applies river tags to biome YAML files based on the inferred assignments
from RiverAssignments.md.

Reads the assignments and adds the appropriate river tag to each biome's tags list.
"""

import yaml
from pathlib import Path

PACK_ROOT = Path(__file__).parent.parent
BIOMES_DIR = PACK_ROOT / "biomes"

# River assignments from RiverAssignments.md (inferred + direct)
ASSIGNMENTS = {
    # Direct matches (BIOME_RIVER files exist)
    "DRY_TEMPERATE_MOUNTAINS": "DRY_TEMPERATE_MOUNTAINS_RIVER",
    "DRY_TEMPERATE_WHITE_MOUNTAINS": "DRY_TEMPERATE_WHITE_MOUNTAINS_RIVER",
    "HIGHLANDS": "HIGHLANDS_RIVER",
    "MOUNTAINS": "MOUNTAINS_RIVER",
    "ORANGE_XERIC_MOUNTAINS": "ORANGE_XERIC_MOUNTAINS_RIVER",
    "RED_XERIC_MOUNTAINS": "RED_XERIC_MOUNTAINS_RIVER",
    "SNOWY_BLACKSTONE_MOUNTAINS": "SNOWY_BLACKSTONE_MOUNTAINS_RIVER",
    "SNOWY_TUFF_MOUNTAINS": "SNOWY_TUFF_MOUNTAINS_RIVER",
    "XERIC_MOUNTAINS": "XERIC_MOUNTAINS_RIVER",

    # USE_COLD_RIVER
    "AUTUMNAL_WOODLANDS": "USE_COLD_RIVER",
    "ENCHANTED_WOODLANDS": "USE_COLD_RIVER",
    "SAKURA_WOODLANDS": "USE_COLD_RIVER",
    "SUNFLOWER_PRAIRIE": "USE_COLD_RIVER",
    "VERTICAL_VISTAS": "USE_COLD_RIVER",
    "VERTICAL_VISTAS_WARM": "USE_COLD_RIVER",

    # USE_DESERT_RIVER
    "CARVING_CREAKS": "USE_DESERT_RIVER",

    # USE_FROZEN_RIVER
    "FROSTBOUND_CHASMS": "USE_FROZEN_RIVER",
    "FROSTCOATED_BOG": "USE_FROZEN_RIVER",
    "FROZEN_SPIRES": "USE_FROZEN_RIVER",
    "ICE_CAPS": "USE_FROZEN_RIVER",
    "SEARING_TORS": "USE_FROZEN_RIVER",
    "VERTICAL_VISTAS_FROZEN": "USE_FROZEN_RIVER",

    # USE_LUKEWARM_RIVER
    "DIKSAM_PLATEAU": "USE_LUKEWARM_RIVER",
    "GRASS_SAVANNA": "USE_LUKEWARM_RIVER",
    "WET_SAVANNA": "USE_LUKEWARM_RIVER",

    # USE_RIVER
    "SAKURA_STREAMS": "USE_RIVER",
    "TEMPERATE_ALPHA_MOUNTAINS": "USE_RIVER",

    # USE_TROPICAL_RIVER
    "BAMBOO_BASIN": "USE_TROPICAL_RIVER",
}


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


def add_tag_to_biome(biome_id, tag):
    """Add a tag to a biome's YAML file."""
    biome_file = find_biome_file(biome_id)
    if not biome_file:
        print(f"  ERROR: Could not find biome file for {biome_id}")
        return False

    try:
        with open(biome_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Get existing tags
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        # Check if tag already exists
        if tag in tags:
            print(f"  SKIP: {biome_id} already has {tag}")
            return False

        # Add tag
        tags.append(tag)
        data["tags"] = tags

        # Write back
        with open(biome_file, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        print(f"  OK: {biome_id} <- {tag}")
        return True

    except Exception as e:
        print(f"  ERROR: {biome_id}: {e}")
        return False


def main():
    print("Applying river tags to biome files...\n")

    success_count = 0
    skip_count = 0
    error_count = 0

    for biome_id, tag in sorted(ASSIGNMENTS.items()):
        result = add_tag_to_biome(biome_id, tag)
        if result is True:
            success_count += 1
        elif result is False:
            skip_count += 1
        else:
            error_count += 1

    print(f"\nSummary:")
    print(f"  Added: {success_count}")
    print(f"  Skipped (already had tag): {skip_count}")
    print(f"  Errors: {error_count}")


if __name__ == "__main__":
    main()
