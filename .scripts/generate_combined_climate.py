#!/usr/bin/env python3
"""
generate_combined_climate.py

Generates combined climate samplers that compute multiple dependent values in a single pass,
eliminating redundant calculations in the biome distribution pipeline.

The combined approach:
1. Computes shared dependencies (continents, spawnIsland) once
2. Derives elevation, temperature, precipitation from shared values
3. Encodes T×P×E into a single "climate index" for weighted list distribution

Encoding scheme:
- Temperature: 12 zones (0-11)
- Precipitation: 6 levels (0-5)
- Elevation: 4 variants (0-3)
- Climate Index = (tempIndex * 24) + (precipIndex * 4) + elevIndex
- Total combinations: 288

Output:
- math/samplers/combined_climate.yml - Combined sampler definitions
- biome-distribution/stages/climate/combined_climate.yml - Single-pass climate distribution
"""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple
from collections import OrderedDict


# =============================================================================
# Configuration
# =============================================================================

# Temperature zones (12 total, ordered cold to hot)
TEMPERATURE_ZONES = [
    'ice-cap',           # 0
    'tundra',            # 1
    'boreal-snowy',      # 2
    'boreal-cold',       # 3
    'boreal-warm',       # 4
    'boreal-hot',        # 5
    'temperate-cold',    # 6
    'temperate-warm',    # 7
    'temperate-hot',     # 8
    'tropical-savanna-wet',  # 9
    'tropical-monsoon',  # 10
    'tropical-rainforest',   # 11
]

# Temperature weights from the original distribution
TEMPERATURE_WEIGHTS = [1, 1, 1, 1, 1, 1, 1, 3, 2, 1, 1, 4]

# Precipitation levels (6 total, ordered dry to wet)
PRECIPITATION_LEVELS = [
    'desert',        # 0
    'desert-border', # 1
    'semi-arid',     # 2
    'mid',           # 3
    'mildly-wet',    # 4
    'very-wet',      # 5
]

# Precipitation weights from the original distribution
PRECIPITATION_WEIGHTS = [4, 1, 1, 1, 2, 3]

# Elevation variants (4 total, ordered low to high)
ELEVATION_VARIANTS = [
    'flat',      # 0
    'lowlands',  # 1
    'midlands',  # 2
    'highlands', # 3
]

# Elevation weights (equal distribution)
ELEVATION_WEIGHTS = [1, 1, 1, 1]


# =============================================================================
# Combined Sampler Generator
# =============================================================================

def generate_combined_sampler_yml() -> str:
    """Generate the combined climate sampler YAML content."""

    content = '''# =============================================================================
# Combined Climate Samplers
# =============================================================================
#
# These samplers compute multiple climate factors in a single pass, eliminating
# redundant calculations that occur when temperature, precipitation, and elevation
# are computed separately.
#
# Encoding scheme:
#   climateIndex = (tempIndex * 24) + (precipIndex * 4) + elevIndex
#   where:
#     tempIndex: 0-11 (12 temperature zones)
#     precipIndex: 0-5 (6 precipitation levels)
#     elevIndex: 0-3 (4 elevation variants)
#
# The climateIndex ranges from 0 to 287, normalized to [-1, 1] for weighted lists.
# =============================================================================

samplers:
  # ---------------------------------------------------------------------------
  # Base Samplers (computed once, shared by all derived values)
  # ---------------------------------------------------------------------------

  # Combined continent + spawnIsland calculation
  # This is the foundation for all other climate factors
  combinedContinent: &combinedContinent
    dimensions: 2
    type: EXPRESSION
    expression: |
      max(
        max(
          -continentNoise(x / scale / globalScale, z / scale / globalScale) * spread + offset,
          spawnIslandValue
        ),
        spotContinentalFactor * (1-(spotDist/spotRad)^2)
      )
    variables:
      globalScale: $customization.yml:global-scale
      scale: $customization.yml:continental-scale
      offset: $customization.yml:continental-offset
      spread: $customization.yml:continental-spread
      spotContinentalFactor: 0.3
    samplers:
      # Inline spawnIsland calculation
      spawnIslandValue:
        dimensions: 2
        type: DOMAIN_WARP
        amplitude: 150
        warp:
          type: FBM
          octaves: 2
          sampler:
            type: TRANSLATE
            x: 5000
            z: -5000
            sampler:
              type: OPEN_SIMPLEX_2
              frequency: 0.004
        sampler:
          type: EXPRESSION_NORMALIZER
          expression: |
            if(in < middleRadius/outerRadius,
              herp(in, innerRadius/outerRadius, 1, middleRadius/outerRadius, 0),
              parabolicMap(in, middleRadius/outerRadius, 0, 1, -1))
          variables:
            innerRadius: $customization.yml:spawn-island-radius-inner
            middleRadius: $customization.yml:spawn-island-radius-middle
            outerRadius: $customization.yml:spawn-island-radius-outer
          functions: $math/functions/interpolation.yml:functions
          sampler:
            type: PROBABILITY
            sampler:
              type: DISTANCE
              point:
                x: $customization.yml:spawn-island-origin-x
                z: $customization.yml:spawn-island-origin-z
              normalize: true
              radius: $customization.yml:spawn-island-radius-outer
      # Spot samplers
      spotDist: $math/samplers/spots.yml:samplers.spotDistance
      spotRad: $math/samplers/spots.yml:samplers.spotRadius
      # Continent noise
      continentNoise:
        dimensions: 2
        type: TRANSLATE
        x: 10000
        z: 10000
        sampler:
          type: RIDGED
          lacunarity: 3
          gain: 0.35
          octaves: 3
          sampler:
            type: OPEN_SIMPLEX_2
            salt: 1
            frequency: 1 / 5000

  # ---------------------------------------------------------------------------
  # Combined Climate Index
  # ---------------------------------------------------------------------------
  #
  # This sampler computes all three climate factors and encodes them into a
  # single value for weighted list distribution.
  #
  # The formula:
  #   climateIndex = (tempIndex * 24 + precipIndex * 4 + elevIndex) / 287 * 2 - 1
  #
  # This maps the 288 combinations to the range [-1, 1].
  # ---------------------------------------------------------------------------

  combinedClimate:
    dimensions: 2
    type: EXPRESSION
    expression: |
      // Compute shared values once
      c = continents(x, z);

      // Raw elevation (hills + mountains)
      rawElev = rawElevationNoise(x / elevScale / globalScale, z / elevScale / globalScale) * elevMult + elevOff;
      flat = flatnessNoise(x / flatScale / globalScale, z / flatScale / globalScale);
      flatFactor = herp(flat, flatThresh, flatAmount, flatThresh + flatBlend, 0);

      // Final elevation with continental modulation
      elev = rawElev * (1 - flatFactor) * herp(c, contZero, 0, contFull, 1);

      // Temperature with altitude lapse
      rawTemp = tempNoise(x / tempScale / globalScale, z / tempScale / globalScale) * tempSpread + tempOff;
      temp = rawTemp - lerp(elev, lapseStart, 0, 1, lapseRate);

      // Precipitation with continental modulation
      rawPrecip = precipNoise(x / precipScale / globalScale, z / precipScale / globalScale) * precipSpread + precipOff;
      precip = lerp(c, oceanThresh, 1, landThresh, rawPrecip);

      // Convert to indices (0-11, 0-5, 0-3)
      tempIdx = floor(clamp((temp + 1) / 2, 0, 0.9999) * 12);
      precipIdx = floor(clamp((precip + 1) / 2, 0, 0.9999) * 6);
      elevIdx = floor(clamp((elev + 1) / 2, 0, 0.9999) * 4);

      // Encode to single value [-1, 1]
      (tempIdx * 24 + precipIdx * 4 + elevIdx) / 287 * 2 - 1

    variables:
      globalScale: $customization.yml:global-scale
      # Elevation variables
      elevScale: $customization.yml:elevation-scale
      elevMult: $customization.yml:elevation-multiplier
      elevOff: $customization.yml:elevation-offset
      contZero: $customization.yml:elevation-continental-flat-threshold
      contFull: $customization.yml:elevation-continental-full-height-threshold
      # Flatness variables
      flatScale: $customization.yml:flatness-scale
      flatThresh: $customization.yml:flatness-percent
      flatBlend: $customization.yml:flatness-blend
      flatAmount: $customization.yml:flatness-factor
      # Temperature variables
      tempScale: $customization.yml:temperature-scale
      tempOff: (${customization.yml:temperature-max}+${customization.yml:temperature-min})/2
      tempSpread: (${customization.yml:temperature-max}-${customization.yml:temperature-min})/2
      lapseRate: $customization.yml:temperature-altitude-lapse-rate
      lapseStart: $customization.yml:temperature-altitude-lapse-start
      # Precipitation variables
      precipScale: $customization.yml:precipitation-scale
      precipOff: (${customization.yml:precipitation-max}+${customization.yml:precipitation-min})/2
      precipSpread: (${customization.yml:precipitation-max}-${customization.yml:precipitation-min})/2
      oceanThresh: $customization.yml:precipitation-ocean-threshold
      landThresh: $customization.yml:precipitation-land-threshold

    functions:
      "<<": $math/functions/interpolation.yml:functions
      clamp:
        arguments: [x, minVal, maxVal]
        expression: max(min(x, maxVal), minVal)

    samplers:
      continents: *combinedContinent

      # Elevation noise (hills + mountains combined)
      rawElevationNoise:
        dimensions: 2
        type: TRANSLATE
        x: 10000
        z: 10000
        sampler:
          type: EXPRESSION
          expression: |
            combine(
              hills(x, z) * hillMax,
              parabolicMap(mountainMask(x, z), mtnZero, 0, mtnFull, mountains(x, z)),
              mtnCap)
          variables:
            mtnZero: 0.3
            mtnFull: 0.6
            hillMax: 0.3
            mtnCap: 0.9
          functions:
            "<<": $math/functions/interpolation.yml:functions
            combine:
              arguments: [hills, mountains, cap]
              expression: hills + mountains * min(1 - hills, cap)
          samplers:
            mountainMask:
              dimensions: 2
              type: PROBABILITY
              sampler:
                type: OPEN_SIMPLEX_2
                salt: 0694
                frequency: 1 / 1500
            mountains:
              dimensions: 2
              type: EXPRESSION_NORMALIZER
              expression: ((-in+1)/2)^2
              sampler:
                type: PSEUDOEROSION
                erosion-frequency: 0.01
                lacunarity: 1.5
                branch-strength: 1
                octaves: 3
                strength: 0.15
                gain: 0.3
                sampler:
                  type: FBM
                  octaves: 3
                  sampler:
                    type: OPEN_SIMPLEX_2
                    frequency: 1 / 900
            hills:
              dimensions: 2
              type: EXPRESSION_NORMALIZER
              expression: ((in+1)/2)^2
              sampler:
                type: FBM
                octaves: 6
                sampler:
                  type: OPEN_SIMPLEX_2
                  frequency: 1 / 2000

      # Flatness noise
      flatnessNoise:
        dimensions: 2
        type: TRANSLATE
        x: 10000
        z: 10000
        sampler:
          type: PROBABILITY
          sampler:
            type: FBM
            gain: 0.3
            lacunarity: 2.3
            sampler:
              type: OPEN_SIMPLEX_2
              frequency: 1 / 1000

      # Temperature noise
      tempNoise:
        dimensions: 2
        type: TRANSLATE
        x: 10000
        z: 10000
        sampler:
          type: FBM
          gain: 0.4
          octaves: 2
          sampler:
            type: OPEN_SIMPLEX_2
            salt: 3
            frequency: 1 / 5000

      # Precipitation noise
      precipNoise:
        dimensions: 2
        type: TRANSLATE
        x: 10000
        z: 10000
        sampler:
          type: FBM
          octaves: 2
          sampler:
            type: OPEN_SIMPLEX_2
            salt: 4
            frequency: 1 / 7500
'''
    return content


def generate_climate_biome_mapping() -> Dict[Tuple[int, int, int], str]:
    """
    Generate the mapping from (tempIdx, precipIdx, elevIdx) to biome name.

    This encodes the logic from the three separate climate stages into a single lookup.
    The mapping is based on the actual stage files:
    - temperature.yml: 12 temperature zones with weights [1,1,1,1,1,1,1,3,2,1,1,4]
    - precipitation.yml: 6 precipitation levels with weights [4,1,1,1,2,3]
    - elevation.yml: 4 elevation variants with weights [1,1,1,1]

    Precipitation mapping (precip index 0-5 = desert to very-wet):
    - Index 0: desert (weight 4)
    - Index 1: desert-border (weight 1)
    - Index 2: semi-arid (weight 1)
    - Index 3: mid (weight 1)
    - Index 4: mildly-wet (weight 2)
    - Index 5: very-wet (weight 3)

    Elevation mapping (elev index 0-3 = flat to highlands):
    - Index 0: flat (weight 1)
    - Index 1: lowlands (weight 1)
    - Index 2: midlands (weight 1)
    - Index 3: highlands (weight 1)
    """
    biome_map = {}

    # Temperature zone to base biome name (after temperature stage)
    temp_base = {
        0: 'ice-cap',
        1: 'tundra',
        2: 'boreal-snowy',
        3: 'boreal-cold',
        4: 'boreal-warm',
        5: 'boreal-hot',
        6: 'temperate-cold',
        7: 'temperate-warm',
        8: 'temperate-hot',
        9: 'tropical-savanna-wet',
        10: 'tropical-monsoon',
        11: 'tropical-rainforest',
    }

    # Precipitation stage mappings: (temp_idx) -> [biomes for each precip level 0-5]
    # Based on precipitation.yml:to mappings
    # Indices: 0=desert(4), 1=desert-border(1), 2=semi-arid(1), 3=mid(1), 4=mildly-wet(2), 5=very-wet(3)
    precip_map = {
        # Ice-cap and tundra don't change with precipitation (no explicit mapping in precipitation.yml)
        0: ['ice-cap'] * 6,
        1: ['tundra'] * 6,
        # Boreal zones (from precipitation.yml lines 101-128)
        2: ['cold-desert', 'cold-steppe', 'boreal-snowy-dry', 'boreal-snowy', 'boreal-snowy', 'boreal-snowy'],
        3: ['cold-desert', 'cold-steppe', 'boreal-cold-dry', 'boreal-cold', 'boreal-cold', 'boreal-cold'],
        4: ['cold-desert', 'cold-steppe', 'boreal-warm-dry', 'boreal-warm-dry', 'boreal-warm', 'boreal-warm'],
        5: ['cold-desert', 'cold-steppe', 'boreal-hot-dry', 'boreal-warm', 'boreal-warm', 'boreal-hot'],
        # Temperate zones (from precipitation.yml lines 60-77)
        # Note: temperate zones use hot-desert for desert, temperate-steppe for desert-border
        6: ['hot-desert', 'temperate-steppe', 'temperate-warm-dry', 'temperate-cold', 'temperate-cold', 'temperate-cold'],
        7: ['hot-desert', 'temperate-steppe', 'temperate-warm-dry', 'temperate-warm', 'temperate-warm', 'temperate-warm'],
        8: ['hot-desert', 'temperate-steppe', 'temperate-hot-dry', 'temperate-hot', 'temperate-hot', 'temperate-hot'],
        # Tropical zones (from precipitation.yml lines 7-29)
        # tropical-savanna-wet: hot-steppe across dry conditions
        9: ['hot-steppe', 'hot-steppe', 'hot-steppe', 'tropical-savanna-wet', 'tropical-savanna-wet', 'tropical-savanna-wet'],
        # tropical-monsoon: hot-desert for very dry, hot-steppe for semi-arid
        10: ['hot-desert', 'hot-desert', 'hot-steppe', 'tropical-savanna-dry', 'tropical-monsoon', 'tropical-monsoon'],
        # tropical-rainforest (default-to): the full tropical spectrum
        11: ['hot-desert', 'hot-desert', 'hot-steppe', 'tropical-savanna-dry', 'tropical-monsoon', 'tropical-rainforest'],
    }

    # Elevation stage mappings: biome_base -> [biomes for each elev level 0-3]
    # Based on elevation.yml:to mappings
    # Format: base_biome -> [flat, lowlands, midlands, highlands]
    elev_map = {
        # Ice zones
        'ice-cap': ['ice-cap-flat', 'ice-cap', 'ice-cap', 'ice-cap-highlands'],
        'tundra': ['tundra-flat', 'tundra', 'tundra', 'tundra-highlands'],
        # Desert zones
        'hot-desert': ['hot-desert-flat', 'hot-desert', 'hot-desert', 'hot-desert-highlands'],
        'cold-desert': ['cold-desert-flat', 'cold-desert', 'cold-desert', 'cold-desert-highlands'],
        # Steppe zones
        'hot-steppe': ['hot-steppe-flat', 'hot-steppe', 'hot-steppe', 'hot-steppe-highlands'],
        'cold-steppe': ['cold-steppe-flat', 'cold-steppe', 'cold-steppe', 'cold-steppe-highlands'],
        'temperate-steppe': ['temperate-steppe-flat', 'temperate-steppe', 'temperate-steppe', 'temperate-steppe-highlands'],
        # Boreal zones
        'boreal-snowy': ['boreal-snowy-flat', 'boreal-snowy', 'boreal-snowy', 'boreal-snowy-highlands'],
        'boreal-snowy-dry': ['boreal-snowy-dry-flat', 'boreal-snowy-dry', 'boreal-snowy-dry', 'boreal-snowy-dry-highlands'],
        'boreal-cold': ['boreal-cold-flat', 'boreal-cold', 'boreal-cold', 'boreal-cold-highlands'],
        'boreal-cold-dry': ['boreal-cold-dry-flat', 'boreal-cold-dry', 'boreal-cold-dry', 'boreal-cold-dry-highlands'],
        'boreal-warm': ['boreal-warm-flat', 'boreal-warm', 'boreal-warm', 'boreal-warm-highlands'],
        'boreal-warm-dry': ['boreal-warm-dry-flat', 'boreal-warm-dry', 'boreal-warm-dry', 'boreal-warm-dry-highlands'],
        'boreal-hot': ['boreal-hot-flat', 'boreal-hot', 'boreal-hot', 'boreal-hot-highlands'],
        'boreal-hot-dry': ['boreal-hot-dry-flat', 'boreal-hot-dry', 'boreal-hot-dry', 'boreal-hot-dry-highlands'],
        # Temperate zones
        'temperate-cold': ['temperate-cold-flat', 'temperate-cold', 'temperate-cold', 'temperate-cold-highlands'],
        'temperate-warm': ['temperate-warm-flat', 'temperate-warm', 'temperate-warm', 'temperate-warm-highlands'],
        'temperate-warm-dry': ['temperate-warm-dry-flat', 'temperate-warm-dry', 'temperate-warm-dry', 'temperate-warm-dry-highlands'],
        'temperate-hot': ['temperate-hot-flat', 'temperate-hot', 'temperate-hot', 'temperate-hot-highlands'],
        'temperate-hot-dry': ['temperate-hot-dry-flat', 'temperate-hot-dry', 'temperate-hot-dry', 'temperate-hot-dry-highlands'],
        # Tropical zones
        'tropical-rainforest': ['tropical-rainforest-flat', 'tropical-rainforest', 'tropical-rainforest', 'tropical-rainforest-highlands'],
        'tropical-monsoon': ['tropical-monsoon-flat', 'tropical-monsoon', 'tropical-monsoon', 'tropical-monsoon-highlands'],
        'tropical-savanna-dry': ['tropical-savanna-dry-flat', 'tropical-savanna-dry', 'tropical-savanna-dry', 'tropical-savanna-dry-highlands'],
        'tropical-savanna-wet': ['tropical-savanna-wet-flat', 'tropical-savanna-wet', 'tropical-savanna-wet', 'tropical-savanna-wet-highlands'],
    }

    for t in range(12):
        for p in range(6):
            # Get biome after precipitation stage
            after_precip = precip_map[t][p]

            for e in range(4):
                # Get final biome after elevation stage
                if after_precip in elev_map:
                    final_biome = elev_map[after_precip][e]
                else:
                    # Fallback: add suffix
                    suffix = ['-flat', '', '', '-highlands'][e]
                    final_biome = after_precip + suffix if suffix else after_precip

                biome_map[(t, p, e)] = final_biome

    return biome_map


def generate_weighted_list_yml(biome_type: str = 'land') -> str:
    """
    Generate a weighted list for the combined climate distribution.

    The list has 288 entries corresponding to all T×P×E combinations.
    """
    biome_map = generate_climate_biome_mapping()

    # Calculate total weight (using original weights)
    # Weight for each combination = temp_weight * precip_weight * elev_weight
    total_weight = sum(TEMPERATURE_WEIGHTS) * sum(PRECIPITATION_WEIGHTS) * sum(ELEVATION_WEIGHTS)

    lines = [f"# Combined climate distribution for {biome_type}"]
    lines.append(f"# Total entries: 288 (12 temp × 6 precip × 4 elev)")
    lines.append(f"# Encoding: index = tempIdx * 24 + precipIdx * 4 + elevIdx")
    lines.append("")

    # Generate weighted list entries
    entries = []
    for t in range(12):
        for p in range(6):
            for e in range(4):
                idx = t * 24 + p * 4 + e
                biome = biome_map.get((t, p, e), 'unknown')
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                entries.append((idx, biome, weight))

    # Sort by index
    entries.sort(key=lambda x: x[0])

    for idx, biome, weight in entries:
        lines.append(f"      - {biome}: {weight}  # idx={idx}")

    return '\n'.join(lines)


def generate_combined_stage_yml() -> str:
    """Generate the combined climate stage YAML."""

    content = '''# =============================================================================
# Combined Climate Stage
# =============================================================================
#
# This stage replaces the three separate temperature, precipitation, and elevation
# stages with a single pass that computes all climate factors together.
#
# Benefits:
# - Eliminates redundant calculations of continents, elevation, etc.
# - Single sampler evaluation instead of three
# - Same biome distribution as the original three-stage approach
#
# Usage: Replace the three climate stage includes with this single include:
#   - << biome-distribution/stages/climate/combined_climate.yml:stages
# =============================================================================

stages:
  - type: REPLACE_LIST
    sampler: $math/samplers/combined_climate.yml:samplers.combinedClimate

    default-from: land
    default-to:
'''

    # Add the weighted list
    biome_map = generate_climate_biome_mapping()

    for t in range(12):
        for p in range(6):
            for e in range(4):
                idx = t * 24 + p * 4 + e
                biome = biome_map.get((t, p, e), 'unknown')
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                content += f"      - {biome}: {weight}\n"

    return content


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate combined climate samplers for optimized biome distribution'
    )
    parser.add_argument(
        '-b', '--base-dir',
        type=str,
        default='.',
        help='Base directory for the ORIGEN2 project'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print output without writing files'
    )

    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    print("=" * 70)
    print("Combined Climate Sampler Generator")
    print("=" * 70)

    # Generate combined sampler
    print("\nGenerating combined sampler definition...")
    sampler_yml = generate_combined_sampler_yml()

    sampler_path = base_dir / 'math' / 'samplers' / 'combined_climate.yml'
    if args.dry_run:
        print(f"\n[DRY RUN] Would write to: {sampler_path}")
        print("-" * 40)
        print(sampler_yml[:2000] + "\n... (truncated)")
    else:
        sampler_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sampler_path, 'w', encoding='utf-8') as f:
            f.write(sampler_yml)
        print(f"  Written to: {sampler_path}")

    # Generate combined stage
    print("\nGenerating combined stage definition...")
    stage_yml = generate_combined_stage_yml()

    stage_path = base_dir / 'biome-distribution' / 'stages' / 'climate' / 'combined_climate.yml'
    if args.dry_run:
        print(f"\n[DRY RUN] Would write to: {stage_path}")
        print("-" * 40)
        print(stage_yml[:2000] + "\n... (truncated)")
    else:
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stage_path, 'w', encoding='utf-8') as f:
            f.write(stage_yml)
        print(f"  Written to: {stage_path}")

    # Print usage instructions
    print("\n" + "=" * 70)
    print("USAGE INSTRUCTIONS")
    print("=" * 70)
    print("""
To use the combined climate distribution, update your preset file to replace:

  stages:
    - << biome-distribution/stages/climate/temperature.yml:stages
    - << biome-distribution/stages/climate/precipitation.yml:stages
    - << biome-distribution/stages/climate/elevation.yml:stages

With:

  stages:
    - << biome-distribution/stages/climate/combined_climate.yml:stages

This will compute temperature, precipitation, and elevation in a single pass,
eliminating redundant calculations of continents and other shared dependencies.
""")

    # Print statistics
    print("STATISTICS")
    print("-" * 40)
    print(f"Temperature zones: {len(TEMPERATURE_ZONES)}")
    print(f"Precipitation levels: {len(PRECIPITATION_LEVELS)}")
    print(f"Elevation variants: {len(ELEVATION_VARIANTS)}")
    print(f"Total combinations: {len(TEMPERATURE_ZONES) * len(PRECIPITATION_LEVELS) * len(ELEVATION_VARIANTS)}")

    biome_map = generate_climate_biome_mapping()
    unique_biomes = set(biome_map.values())
    print(f"Unique biomes in distribution: {len(unique_biomes)}")

    print("\nDone!")


if __name__ == "__main__":
    main()
