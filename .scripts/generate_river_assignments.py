#!/usr/bin/env python3
"""
generate_river_assignments.py

Reads BiomeTable.csv and set_biomes_in_climates_origen.yml to produce a river
assignment document listing each qualifying land biome and its recommended river
biome or river tag.

Qualifying biomes:
  - Origin == "Land" (or archipelago-like Ocean biomes such as ARCHIPELAGO)
  - Not a river biome itself (Category != RIVER, not ending in _RIVER)
  - Not a subsurface biome (Category != SUBSURFACE)
  - River column is empty (no existing river tag defined)

River assignment rules:
  1. If a biome-specific river exists (e.g. BIOME_ID_RIVER as a biome file), use it.
  2. Otherwise, infer the river tag from the climate region where the biome
     appears in set_biomes_in_climates_origen.yml, with high preference on temperature.
"""

import csv
import yaml
from pathlib import Path
from collections import defaultdict

PACK_ROOT = Path(__file__).parent.parent
CSV_PATH = PACK_ROOT / ".artifacts" / "BiomeTable.csv"
CLIMATE_FILE = PACK_ROOT / "biome-distribution" / "stages" / "set_biomes_in_climates_origen.yml"
BIOMES_DIR = PACK_ROOT / "biomes"
OUTPUT_PATH = PACK_ROOT / ".artifacts" / "RiverAssignments.md"

# Map temperature zone prefix -> river tag, checked in order (first match wins).
# High preference on temperature as requested.
TEMPERATURE_PREFIX_TO_RIVER = [
    # (prefix, river_tag)
    ("ice-cap",              "USE_FROZEN_RIVER"),
    ("tundra",               "USE_FROZEN_RIVER"),
    ("boreal-snowy",         "USE_FROZEN_RIVER"),
    ("boreal",               "USE_COLD_RIVER"),
    ("temperate",            "USE_RIVER"),
    ("tropical-rainforest",  "USE_TROPICAL_RIVER"),
    ("tropical-monsoon",     "USE_TROPICAL_RIVER"),
    ("tropical-savanna",     "USE_LUKEWARM_RIVER"),
    ("tropical",             "USE_TROPICAL_RIVER"),
    ("hot-desert",           "USE_DESERT_RIVER"),
    ("hot-steppe",           "USE_LUKEWARM_RIVER"),
    ("hot",                  "USE_LUKEWARM_RIVER"),
    ("cold-desert",          "USE_DESERT_RIVER"),
    ("cold-steppe",          "USE_COLD_RIVER"),
    ("cold",                 "USE_COLD_RIVER"),
    ("lukewarm",             "USE_LUKEWARM_RIVER"),
    ("polar",                "USE_FROZEN_RIVER"),
    ("frozen",               "USE_FROZEN_RIVER"),
]

# All known river tags from add_rivers.yml for reference
KNOWN_RIVER_TAGS = [
    "USE_RIVER",
    "USE_DESERT_RIVER",
    "USE_RED_DESERT_RIVER",
    "USE_ORANGE_DESERT_RIVER",
    "USE_TAR_PIT_RIVER",
    "USE_RIVER_TEMPERATE_MARSH",
    "USE_PALE_GARDEN_RIVER",
    "USE_ARID_PALE_GARDEN_RIVER",
    "USE_ORANGE_ARID_PALE_GARDEN_RIVER",
    "USE_RED_ARID_PALE_GARDEN_RIVER",
    "USE_POLAR_PALE_GARDEN_RIVER",
    "USE_MUSHROOM_RIVER",
    "USE_POLAR_MUSHROOM_RIVER",
    "USE_RIVER_TEMPERATE_SWAMP",
    "USE_LUKEWARM_RIVER",
    "USE_TROPICAL_RIVER",
    "USE_RIVER_COASTAL_TROPICAL_SWAMP",
    "USE_COLD_RIVER",
    "USE_FROZEN_RIVER",
    "USE_LAND_GLACIER_RIVER",
    "USE_FROZEN_RIVER_FROZEN_MARSH",
]

# River column values from the CSV that indicate an existing river assignment
RIVER_COLUMN_VALUES = {"General", "Cold", "Desert"}


def get_all_biome_data():
    """Get set of all biome IDs and their tags from biome files.

    Returns:
        ids: set of all biome IDs
        biome_tags: dict mapping biome_id -> list of tags
    """
    ids = set()
    biome_tags = defaultdict(list)
    for f in BIOMES_DIR.rglob("*.yml"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data and data.get("type") == "BIOME" and not data.get("abstract", False):
                bid = data.get("id")
                if bid:
                    ids.add(bid)
                    tags = data.get("tags", [])
                    if isinstance(tags, list):
                        # Merge tags (biome may exist in multiple files)
                        existing = biome_tags.get(bid, [])
                        merged = list(dict.fromkeys(existing + tags))
                        biome_tags[bid] = merged
        except Exception:
            continue
    return ids, biome_tags


def get_existing_river_tags(biome_tags):
    """Find biomes that already have a river-related tag.

    Returns dict mapping biome_id -> list of river tags found.
    """
    river_tag_map = {}
    for biome_id, tags in biome_tags.items():
        river_tags = [t for t in tags if "RIVER" in t.upper()]
        if river_tags:
            river_tag_map[biome_id] = river_tags
    return river_tag_map


def find_direct_river_match(biome_id, all_biome_ids):
    """Check if a biome-specific river exists (BIOME_ID_RIVER)."""
    river_id = f"{biome_id}_RIVER"
    if river_id in all_biome_ids:
        return river_id
    return None


def parse_climate_regions():
    """
    Parse set_biomes_in_climates_origen.yml to build a mapping of
    biome_id -> list of (region_key, weight) tuples.
    """
    with open(CLIMATE_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    biome_regions = defaultdict(list)

    stages = data.get("stages", [])
    for stage in stages:
        if stage.get("type") != "REPLACE_LIST":
            continue

        # Process default-to
        default_from = stage.get("default-from", "")
        default_to = stage.get("default-to", [])
        if isinstance(default_to, list):
            for entry in default_to:
                if isinstance(entry, dict):
                    for biome_id, weight in entry.items():
                        if biome_id != "SELF":
                            biome_regions[biome_id].append((default_from, weight))

        # Process to section
        to_section = stage.get("to", {})
        if isinstance(to_section, dict):
            for region_key, biome_list in to_section.items():
                if isinstance(biome_list, list):
                    for entry in biome_list:
                        if isinstance(entry, dict):
                            for biome_id, weight in entry.items():
                                if biome_id != "SELF":
                                    biome_regions[biome_id].append((region_key, weight))
                elif isinstance(biome_list, str) and biome_list != "SELF":
                    biome_regions[biome_list].append((region_key, 1))

    return biome_regions


def infer_river_from_region(region_key):
    """
    Infer river tag from a climate region key.
    Temperature zone (first prefix) is the primary determinant.
    """
    key_lower = region_key.lower()

    for prefix, river_tag in TEMPERATURE_PREFIX_TO_RIVER:
        if key_lower.startswith(prefix):
            return river_tag

    return "USE_RIVER"  # fallback


def infer_river_for_biome(biome_id, regions):
    """
    Given a biome's climate region placements, determine the best river tag.
    If a biome appears in multiple regions, use weighted average to pick the dominant one.
    """
    if not regions:
        return None, "No climate region found"

    # Count votes for each river tag, weighted
    river_votes = defaultdict(float)
    for region_key, weight in regions:
        river_tag = infer_river_from_region(region_key)
        river_votes[river_tag] += weight

    # Pick the one with highest weight
    best_river = max(river_votes, key=river_votes.get)
    total = sum(river_votes.values())

    if len(river_votes) == 1:
        detail = f"from {regions[0][0]}"
    else:
        parts = []
        for river_tag, w in sorted(river_votes.items(), key=lambda x: -x[1]):
            pct = w / total * 100
            parts.append(f"{river_tag} ({pct:.0f}%)")
        detail = "averaged: " + ", ".join(parts)

    return best_river, detail


def main():
    print(f"Reading BiomeTable from {CSV_PATH}")
    print(f"Reading climate config from {CLIMATE_FILE}")

    # Load all biome IDs and tags for river matching
    all_biome_ids, biome_tags = get_all_biome_data()
    print(f"Found {len(all_biome_ids)} valid biome IDs")

    # Find biomes with existing river tags in their YAML files
    existing_river_tags = get_existing_river_tags(biome_tags)
    print(f"Found {len(existing_river_tags)} biomes with existing river tags in YAML files")

    # Parse climate regions
    biome_regions = parse_climate_regions()
    print(f"Found climate placements for {len(biome_regions)} biomes")

    # Read and filter CSV
    already_assigned = []  # biomes that already have river tags (CSV or YAML)
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        qualifying_biomes = []
        for row in reader:
            origin = row.get("Origin", "").strip()
            category = row.get("Category", "").strip()
            river_col = row.get("River", "").strip()
            biome_id = row["BiomeID"]
            biome_upper = biome_id.upper()

            # 1. Must be Land origin, or archipelago-type Ocean biomes
            is_archipelago = "ARCHIPELAGO" in biome_upper and origin == "Ocean"
            if origin != "Land" and not is_archipelago:
                continue

            # 2. Not a river biome itself
            if category == "RIVER":
                continue
            if biome_upper.endswith("_RIVER"):
                continue

            # 3. Not a subsurface/extrusion biome
            if category == "SUBSURFACE":
                continue

            # Skip spot sub-biomes (_INNER, _MIDDLE, _OUTER)
            if any(biome_upper.endswith(suffix) for suffix in ("_INNER", "_MIDDLE", "_OUTER")):
                continue

            # 4. Check for existing river assignment (CSV column OR YAML tags)
            if river_col:
                already_assigned.append((biome_id, f"CSV River column: {river_col}"))
                continue
            if biome_id in existing_river_tags:
                already_assigned.append((biome_id, f"YAML tags: {', '.join(existing_river_tags[biome_id])}"))
                continue

            qualifying_biomes.append(row)

    print(f"Biomes already assigned (CSV or YAML): {len(already_assigned)}")
    print(f"Qualifying biomes (no river assigned): {len(qualifying_biomes)}")

    # Build assignments
    assignments = []  # (biome_id, river, source, detail)
    for row in sorted(qualifying_biomes, key=lambda x: x["BiomeID"]):
        biome_id = row["BiomeID"]

        # Check for direct river match
        direct = find_direct_river_match(biome_id, all_biome_ids)
        if direct:
            assignments.append((biome_id, direct, "direct", "Biome-specific river file exists"))
            continue

        # Infer from climate regions
        regions = biome_regions.get(biome_id, [])
        river_tag, detail = infer_river_for_biome(biome_id, regions)
        if river_tag:
            assignments.append((biome_id, river_tag, "inferred", detail))
        else:
            assignments.append((biome_id, "UNKNOWN", "none", detail))

    # Generate output
    lines = []
    lines.append("# River Assignments for Land Biomes")
    lines.append("")
    lines.append("Generated from BiomeTable.csv and set_biomes_in_climates_origen.yml")
    lines.append("")
    lines.append("## Filters Applied")
    lines.append("- Origin: Land (+ archipelago Ocean biomes)")
    lines.append("- Excluded: River biomes, subsurface/extrusion biomes")
    lines.append("- Excluded: Biomes with existing river assignment (CSV River column OR YAML river tags)")
    lines.append("")

    # Group by assignment type
    direct_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "direct"]
    inferred_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "inferred"]
    unknown_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "none"]

    lines.append("## Summary")
    lines.append(f"- Total qualifying biomes: {len(assignments)}")
    lines.append(f"- Direct river match: {len(direct_assignments)}")
    lines.append(f"- Inferred from climate: {len(inferred_assignments)}")
    lines.append(f"- Unknown: {len(unknown_assignments)}")
    lines.append("")

    # Available river tags reference
    lines.append("## Available River Tags (from add_rivers.yml)")
    lines.append("")
    for tag in sorted(KNOWN_RIVER_TAGS):
        lines.append(f"- `{tag}`")
    lines.append("")

    # Direct matches
    lines.append("## Biome-Specific Rivers (Direct Match)")
    lines.append("")
    lines.append("| Biome | River |")
    lines.append("|-------|-------|")
    for biome_id, river, _, _ in direct_assignments:
        lines.append(f"| {biome_id} | {river} |")
    lines.append("")

    # Inferred - group by river tag
    lines.append("## Inferred River Assignments")
    lines.append("")

    river_groups = defaultdict(list)
    for biome_id, river_tag, _, detail in inferred_assignments:
        river_groups[river_tag].append((biome_id, detail))

    for river_tag in sorted(river_groups.keys()):
        biomes = river_groups[river_tag]
        lines.append(f"### {river_tag} ({len(biomes)} biomes)")
        lines.append("")
        lines.append("| Biome | Reasoning |")
        lines.append("|-------|-----------|")
        for biome_id, detail in biomes:
            lines.append(f"| {biome_id} | {detail} |")
        lines.append("")

    # Unknown
    if unknown_assignments:
        lines.append("## Unknown (No Climate Region Found)")
        lines.append("")
        lines.append("| Biome | Notes |")
        lines.append("|-------|-------|")
        for biome_id, _, _, detail in unknown_assignments:
            lines.append(f"| {biome_id} | {detail} |")
        lines.append("")

    # Already assigned (for reference)
    if already_assigned:
        lines.append("## Already Assigned (Excluded from Above)")
        lines.append("")
        lines.append("These biomes already have river tags via CSV River column or YAML tags.")
        lines.append("")
        lines.append("| Biome | Source |")
        lines.append("|-------|--------|")
        for biome_id, source in sorted(already_assigned):
            lines.append(f"| {biome_id} | {source} |")
        lines.append("")

    output = "\n".join(lines)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)

    print(f"\nOutput written to {OUTPUT_PATH}")
    print(f"\n{output}")


if __name__ == "__main__":
    main()
