#!/usr/bin/env python3
"""
generate_coast_assignments.py

Reads BiomeTable.csv and set_biomes_in_climates_origen.yml to produce a coast
assignment document listing each qualifying land biome and its recommended coast.

Qualifying biomes:
  - Origin == "Land"
  - Not a river (River column is empty)
  - Not a wetland (extends/ID doesn't contain BOG, WETLANDS, SWAMP, MARSH)

Coast assignment rules:
  1. If a biome-specific coast exists (e.g. BIOME_ID_COAST as a biome file), use it.
  2. Otherwise, infer the coast category from the climate region where the biome
     appears in set_biomes_in_climates_origen.yml.
"""

import csv
import yaml
import re
from pathlib import Path
from collections import defaultdict

PACK_ROOT = Path(__file__).parent.parent
CSV_PATH = PACK_ROOT / ".artifacts" / "BiomeTable.csv"
CLIMATE_FILE = PACK_ROOT / "biome-distribution" / "stages" / "set_biomes_in_climates_origen.yml"
BIOMES_DIR = PACK_ROOT / "biomes"
OUTPUT_PATH = PACK_ROOT / ".artifacts" / "CoastAssignments.md"

WETLAND_KEYWORDS = ["BOG", "WETLANDS", "SWAMP", "MARSH"]

# Map the leading temperature zone prefix of climate region keys to coast categories.
# The climate pipeline is: temperature -> precipitation -> elevation
# Region keys from temperature.yml:
#   ice-cap, tundra, boreal-{snowy,cold,warm,hot}, temperate-{cold,warm,hot},
#   tropical-{savanna-wet,savanna-dry,monsoon,rainforest},
#   hot-{desert,steppe}, cold-{desert,steppe}
# Prefix matching is done longest-first so "ice-cap" beats "ice".
TEMPERATURE_PREFIX_TO_COAST = [
    # (prefix, coast_type)  — checked in order, first match wins
    ("ice-cap",              "polar"),
    ("tundra",               "polar"),
    ("boreal",               "boreal"),
    ("temperate",            "temperate"),
    ("tropical",             "tropical"),
    ("hot-desert",           "arid"),
    ("hot-steppe",           "tropical"),
    ("hot",                  "tropical"),
    ("cold-desert",          "arid"),
    ("cold-steppe",          "boreal"),
    ("cold",                 "boreal"),
    ("lukewarm",             "temperate"),
    ("polar",                "polar"),
    ("frozen",               "polar"),
]

ELEVATION_TO_SUFFIX = {
    "flat": "flat",
    "lowlands": "flat",
    "midlands": "flat",
    "highlands": "highlands",
    "mountains": "highlands",
}

COAST_CATEGORIES = [
    "arid-coast-flat", "arid-coast-highlands",
    "boreal-coast-flat", "boreal-coast-highlands",
    "polar-coast-flat", "polar-coast-highlands",
    "temperate-coast-flat", "temperate-coast-highlands",
    "tropical-coast-flat", "tropical-coast-highlands",
]


def get_all_biome_ids():
    """Get set of all biome IDs from biome files."""
    ids = set()
    for f in BIOMES_DIR.rglob("*.yml"):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
            if data and data.get("type") == "BIOME" and not data.get("abstract", False):
                bid = data.get("id")
                if bid:
                    ids.add(bid)
        except Exception:
            continue
    return ids


def find_direct_coast_match(biome_id, all_biome_ids):
    """Check if a biome-specific coast exists.

    Checks multiple naming patterns:
      1. BIOME_ID_COAST (standard)
      2. BIOME_ID with _FIELDS suffix stripped + _COAST (e.g. MUSHROOM_FIELDS -> MUSHROOM_COAST)
    """
    # Standard pattern
    coast_id = f"{biome_id}_COAST"
    if coast_id in all_biome_ids:
        return coast_id
    # Strip common suffixes and retry
    for suffix in ("_FIELDS",):
        if biome_id.endswith(suffix):
            alt = biome_id[:-len(suffix)] + "_COAST"
            if alt in all_biome_ids:
                return alt
    return None


def parse_climate_regions():
    """
    Parse set_biomes_in_climates_origen.yml to build a mapping of
    biome_id -> list of (region_key, weight) tuples.

    The YAML structure has REPLACE_LIST stages where `to:` maps region names
    to weighted biome lists.
    """
    with open(CLIMATE_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    biome_regions = defaultdict(list)  # biome_id -> [(region_key, weight)]

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


def infer_coast_from_region(region_key):
    """
    Infer coast category from a climate region key.

    The first segment of the region key is the temperature zone from the
    pipeline.  This is the primary determinant of coast type.  Elevation
    (flat vs highlands) is determined from the last segment if present.
    """
    key_lower = region_key.lower()

    # Determine temperature -> coast type via prefix matching
    coast_type = None
    for prefix, ct in TEMPERATURE_PREFIX_TO_COAST:
        if key_lower.startswith(prefix):
            coast_type = ct
            break

    if coast_type is None:
        coast_type = "temperate"  # fallback

    # Determine elevation from the last segment(s)
    parts = key_lower.split("-")
    elevation = "flat"  # default
    for part in reversed(parts):
        if part in ELEVATION_TO_SUFFIX:
            elevation = ELEVATION_TO_SUFFIX[part]
            break

    return f"{coast_type}-coast-{elevation}"


def infer_coast_for_biome(biome_id, regions):
    """
    Given a biome's climate region placements, determine the best coast category.
    If a biome appears in multiple regions, use weighted average to pick the dominant one.
    """
    if not regions:
        return None, "No climate region found"

    # Count votes for each coast category, weighted
    coast_votes = defaultdict(float)
    for region_key, weight in regions:
        coast = infer_coast_from_region(region_key)
        coast_votes[coast] += weight

    # Pick the one with highest weight
    best_coast = max(coast_votes, key=coast_votes.get)
    total = sum(coast_votes.values())

    if len(coast_votes) == 1:
        detail = f"from {regions[0][0]}"
    else:
        parts = []
        for coast, w in sorted(coast_votes.items(), key=lambda x: -x[1]):
            pct = w / total * 100
            parts.append(f"{coast} ({pct:.0f}%)")
        detail = "averaged: " + ", ".join(parts)

    return best_coast, detail


def main():
    print(f"Reading BiomeTable from {CSV_PATH}")
    print(f"Reading climate config from {CLIMATE_FILE}")

    # Load all biome IDs for coast matching
    all_biome_ids = get_all_biome_ids()
    print(f"Found {len(all_biome_ids)} valid biome IDs")

    # Parse climate regions
    biome_regions = parse_climate_regions()
    print(f"Found climate placements for {len(biome_regions)} biomes")

    # Read and filter CSV
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        land_biomes = []
        for row in reader:
            if row["Origin"] != "Land":
                continue
            if row.get("River", "").strip():
                continue
            extends = row.get("Extends", "").upper()
            biome_id = row["BiomeID"]
            biome_upper = biome_id.upper()
            if any(kw in extends for kw in WETLAND_KEYWORDS) or any(kw in biome_upper for kw in WETLAND_KEYWORDS):
                continue
            # Also skip river variants (ID ends with _RIVER) and spot sub-biomes
            if biome_upper.endswith("_RIVER"):
                continue
            if any(biome_upper.endswith(suffix) for suffix in ("_INNER", "_MIDDLE", "_OUTER")):
                continue
            land_biomes.append(row)

    print(f"Qualifying land biomes: {len(land_biomes)}")

    # Build assignments
    assignments = []  # (biome_id, coast, source, detail)
    for row in sorted(land_biomes, key=lambda x: x["BiomeID"]):
        biome_id = row["BiomeID"]

        # Check for direct coast match
        direct = find_direct_coast_match(biome_id, all_biome_ids)
        if direct:
            assignments.append((biome_id, direct, "direct", f"Biome-specific coast file exists"))
            continue

        # Infer from climate regions
        regions = biome_regions.get(biome_id, [])
        coast, detail = infer_coast_for_biome(biome_id, regions)
        if coast:
            assignments.append((biome_id, coast, "inferred", detail))
        else:
            assignments.append((biome_id, "UNKNOWN", "none", detail))

    # Generate output
    lines = []
    lines.append("# Coast Assignments for Land Biomes")
    lines.append("")
    lines.append("Generated from BiomeTable.csv and set_biomes_in_climates_origen.yml")
    lines.append("")
    lines.append("## Filters Applied")
    lines.append("- Origin: Land only")
    lines.append("- Excluded: Rivers, Wetlands (BOG, WETLANDS, SWAMP, MARSH)")
    lines.append("")

    # Group by assignment type
    direct_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "direct"]
    inferred_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "inferred"]
    unknown_assignments = [(b, c, s, d) for b, c, s, d in assignments if s == "none"]

    lines.append(f"## Summary")
    lines.append(f"- Total qualifying biomes: {len(assignments)}")
    lines.append(f"- Direct coast match: {len(direct_assignments)}")
    lines.append(f"- Inferred from climate: {len(inferred_assignments)}")
    lines.append(f"- Unknown: {len(unknown_assignments)}")
    lines.append("")

    # Direct matches
    lines.append("## Biome-Specific Coasts (Direct Match)")
    lines.append("")
    lines.append("| Biome | Coast |")
    lines.append("|-------|-------|")
    for biome_id, coast, _, _ in direct_assignments:
        lines.append(f"| {biome_id} | {coast} |")
    lines.append("")

    # Inferred - group by coast category
    lines.append("## Inferred Coast Assignments")
    lines.append("")

    coast_groups = defaultdict(list)
    for biome_id, coast, _, detail in inferred_assignments:
        coast_groups[coast].append((biome_id, detail))

    for coast_cat in sorted(coast_groups.keys()):
        biomes = coast_groups[coast_cat]
        lines.append(f"### {coast_cat} ({len(biomes)} biomes)")
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

    output = "\n".join(lines)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(output)

    print(f"\nOutput written to {OUTPUT_PATH}")
    print(f"\n{output}")


if __name__ == "__main__":
    main()
