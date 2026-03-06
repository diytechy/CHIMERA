import yaml
from pathlib import Path

coast_assignments = {
    'ARID_ARBORETUM': 'ARID_COAST_FLAT',
    'ASPEN_FOREST': 'TEMPERATE_COAST_FLAT',
    'BADLANDS': 'ARID_COAST_FLAT',
    'BAMBOO_BASIN': 'TROPICAL_COAST_FLAT',
    'BAMBOO_JUNGLE': 'TROPICAL_COAST_FLAT',
    'BARE_BOULDERFIELDS': 'POLAR_COAST_HIGHLANDS',
    'BIRCH_FOREST': 'TEMPERATE_COAST_FLAT',
    'BIRCH_WOODLANDS': 'BOREAL_COAST_FLAT',
    'BLACK_FOREST': 'TEMPERATE_COAST_FLAT',
    'BOREAL_MESA': 'BOREAL_COAST_FLAT',
    'BOREAL_SHRUBLAND': 'BOREAL_COAST_FLAT',
    'BROADLEAF_FOREST': 'TEMPERATE_COAST_FLAT',
    'CANOPY_CASCADES': 'TROPICAL_COAST_HIGHLANDS',
    'CHAPARRAL': 'TEMPERATE_COAST_FLAT',
    'CLOUD_FOREST': 'TROPICAL_COAST_HIGHLANDS',
    'COLD_DESERT_MESA': 'POLAR_COAST_FLAT',
    'COLD_STEPPE': 'BOREAL_COAST_FLAT',
    'DARK_FOREST': 'TEMPERATE_COAST_FLAT',
    'DRYBRUSH': 'ARID_COAST_FLAT',
    'DRY_FIR_FIELDS': 'BOREAL_COAST_FLAT',
    'DRY_PALM_FOREST': 'ARID_COAST_FLAT',
    'DRY_WOODLANDS': 'TROPICAL_COAST_FLAT',
    'FIR_FIELDS': 'BOREAL_COAST_FLAT',
    'FLOWERING_FOREST': 'TEMPERATE_COAST_FLAT',
    'FOLIAGE_FORTRESS_INNER': 'TEMPERATE_COAST_FLAT',
    'FOLIAGE_FORTRESS_MIDDLE': 'TEMPERATE_COAST_FLAT',
    'FOLIAGE_FORTRESS_OUTER': 'TEMPERATE_COAST_FLAT',
    'GLOOMY_GORGE': 'BOREAL_COAST_FLAT',
    'GRASS_SAVANNA': 'TROPICAL_COAST_FLAT',
    'ICE_CAPS': 'POLAR_COAST_HIGHLANDS',
    'ICE_SPIKES': 'POLAR_COAST_FLAT',
    'JUNGLE': 'TROPICAL_COAST_FLAT',
    'MAPLE_GROVE': 'BOREAL_COAST_FLAT',
    'MAPLE_WOODLANDS': 'BOREAL_COAST_FLAT',
    'MOORLAND': 'TEMPERATE_COAST_FLAT',
    'MOUNTAINS': 'TEMPERATE_COAST_HIGHLANDS',
    'OAK_FOREST': 'TEMPERATE_COAST_FLAT',
    'OAK_SAVANNA': 'TEMPERATE_COAST_FLAT',
    'OAK_WOODLANDS': 'BOREAL_COAST_FLAT',
    'PALM_FOREST': 'TEMPERATE_COAST_FLAT',
    'PEARLESCENT_DESERT': 'ARID_COAST_FLAT',
    'PINE_CANOPY': 'BOREAL_COAST_FLAT',
    'PRAIRIE': 'TEMPERATE_COAST_FLAT',
    'REDWOOD_WOODLANDS': 'BOREAL_COAST_FLAT',
    'ROCKY_DESERT': 'ARID_COAST_FLAT',
    'ROCKY_GRASSLAND': 'TEMPERATE_COAST_FLAT',
    'ROCKY_JUNGLE': 'TROPICAL_COAST_FLAT',
    'ROCKY_REFUGE': 'TEMPERATE_COAST_HIGHLANDS',
    'SAKURA_GROVE': 'TEMPERATE_COAST_FLAT',
    'SAKURA_STREAMS': 'TEMPERATE_COAST_FLAT',
    'SAKURA_WOODLANDS': 'BOREAL_COAST_FLAT',
    'SALT_FLATS': 'ARID_COAST_FLAT',
    'SAVANNA': 'TROPICAL_COAST_FLAT',
    'SEQUOIA_FOREST': 'BOREAL_COAST_FLAT',
    'SNOWDRIFT_MEADOWS': 'POLAR_COAST_FLAT',
    'SNOWY_BADLANDS': 'ARID_COAST_FLAT',
    'SNOWY_BIRCH_FOREST': 'BOREAL_COAST_FLAT',
    'SNOWY_MEADOW': 'POLAR_COAST_FLAT',
    'SNOWY_TAIGA': 'BOREAL_COAST_FLAT',
    'STEPPE': 'TEMPERATE_COAST_FLAT',
    'TAIGA': 'BOREAL_COAST_FLAT',
    'TAIGA_CLEARING': 'BOREAL_COAST_FLAT',
    'TALL_TIMBERLAND': 'BOREAL_COAST_FLAT',
    'TEMPERATE_GRASSLAND': 'TEMPERATE_COAST_FLAT',
    'TEMPERATE_MESA': 'TEMPERATE_COAST_FLAT',
    'TEMPERATE_OVERPASS': 'TEMPERATE_COAST_FLAT',
    'TEMPERATE_RAINFOREST': 'TEMPERATE_COAST_FLAT',
    'WHITE_WALLOWS': 'BOREAL_COAST_FLAT',
    'WOODED_BUTTES': 'TEMPERATE_COAST_FLAT',
    'YELLOW_MAPLE_GROVE': 'BOREAL_COAST_FLAT',
}

biomes_dir = Path("C:/Projects/ORIGEN2/biomes")

count_updated = 0
count_no_tags = 0
count_already_coast = 0
not_found = []

for biome_id, coast_tag in coast_assignments.items():
    # Find biome file by searching for 'id: BIOME_ID' in all yml files
    matching_files = []
    for yml_file in biomes_dir.rglob("*.yml"):
        with open(yml_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # Check for the id field matching exactly
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == f'id: {biome_id}':
                matching_files.append(yml_file)
                break

    if not matching_files:
        not_found.append(biome_id)
        continue

    biome_file = matching_files[0]

    with open(biome_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Rule 2: only add if file already has a tags section
    if 'tags' not in data or data['tags'] is None:
        count_no_tags += 1
        print(f"SKIP (no tags): {biome_id} in {biome_file.name}")
        continue

    # Rule 3: only add if no existing tag contains "COAST"
    existing_tags = data['tags'] if isinstance(data['tags'], list) else []
    if any('COAST' in str(t) for t in existing_tags):
        count_already_coast += 1
        print(f"SKIP (already has coast): {biome_id} in {biome_file.name}")
        continue

    # Rule 4: append the coast tag
    data['tags'].append(coast_tag)

    with open(biome_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    count_updated += 1
    print(f"UPDATED: {biome_id} -> added {coast_tag} ({biome_file.name})")

print()
print("=== Summary ===")
print(f"Updated:                {count_updated}")
print(f"Skipped (no tags):      {count_no_tags}")
print(f"Skipped (coast exists): {count_already_coast}")
if not_found:
    print(f"Not found ({len(not_found)}): {', '.join(not_found)}")
