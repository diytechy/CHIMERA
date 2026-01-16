#!/usr/bin/env python3
"""
generate_combined_climate.py

Generates combined climate samplers that compute multiple dependent values in a single pass,
eliminating redundant calculations in the biome distribution pipeline.

This script DYNAMICALLY reads and resolves the source sampler files:
- math/samplers/continents.yml
- math/samplers/spawnIsland.yml
- math/samplers/elevation.yml
- math/samplers/temperature.yml
- math/samplers/precipitation.yml

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
from ensure_module import ensure_modules
ensure_modules(["yaml", "re"])

import yaml
import sys
import copy
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from collections import OrderedDict

# Import the SamplerResolver from resolve_samplers.py
from resolve_samplers import SamplerResolver


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

# Source sampler files to read
SOURCE_SAMPLERS = {
    'continents': 'math/samplers/continents.yml',
    'spawnIsland': 'math/samplers/spawnIsland.yml',
    'elevation': 'math/samplers/elevation.yml',
    'temperature': 'math/samplers/temperature.yml',
    'precipitation': 'math/samplers/precipitation.yml',
    'spots': 'math/samplers/spots.yml',
}


# =============================================================================
# YAML Output Helpers
# =============================================================================

class YamlDumper(yaml.SafeDumper):
    """Custom YAML dumper with better formatting."""
    pass

def str_representer(dumper, data):
    """Handle multi-line strings with literal block style."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

def dict_representer(dumper, data):
    """Preserve dict ordering."""
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())

YamlDumper.add_representer(str, str_representer)
YamlDumper.add_representer(dict, dict_representer)
YamlDumper.add_representer(OrderedDict, dict_representer)


# =============================================================================
# Combined Climate Generator
# =============================================================================

class CombinedClimateGenerator:
    """
    Generates combined climate samplers by reading and resolving source sampler files.
    """

    def __init__(self, base_dir: Path = Path(".")):
        self.base_dir = base_dir
        self.resolver = SamplerResolver(base_dir, should_evaluate_constants=False)
        self.resolved_samplers: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_source_samplers(self) -> bool:
        """
        Load and resolve all source sampler files.
        Returns True if successful, False otherwise.
        """
        print("Loading source samplers...", file=sys.stderr)

        for name, file_path in SOURCE_SAMPLERS.items():
            print(f"  Loading: {file_path}", file=sys.stderr)
            samplers = self.resolver.process_sampler_file(Path(file_path))

            if not samplers:
                self.warnings.append(f"No samplers found in {file_path}")
            else:
                for sampler_name, config in samplers.items():
                    full_name = f"{name}.{sampler_name}"
                    self.resolved_samplers[full_name] = config
                    print(f"    Resolved: {sampler_name}", file=sys.stderr)

        # Also store by simple name for key samplers
        self._store_key_samplers()

        if self.resolver.errors:
            self.errors.extend(self.resolver.errors)

        return len(self.errors) == 0

    def _store_key_samplers(self):
        """Store commonly referenced samplers by simple name."""
        key_mappings = {
            'continents': 'continents.continents',
            'spawnIsland': 'spawnIsland.spawnIsland',
            'elevation': 'elevation.elevation',
            'rawElevation': 'elevation.rawElevation',
            'flatness': 'elevation.flatness',
            'temperature': 'temperature.temperature',
            'rawTemperature': 'temperature.rawTemperature',
            'precipitation': 'precipitation.precipitation',
            'rawPrecipitation': 'precipitation.rawPrecipitation',
            'spotDistance': 'spots.spotDistance',
            'spotRadius': 'spots.spotRadius',
        }

        for simple_name, full_name in key_mappings.items():
            if full_name in self.resolved_samplers:
                self.resolved_samplers[simple_name] = self.resolved_samplers[full_name]

    def _extract_sampler_inline(self, sampler_name: str) -> Optional[Dict[str, Any]]:
        """
        Extract a sampler definition, inlining any nested sampler references.
        Returns a deep copy to avoid mutation.
        """
        if sampler_name not in self.resolved_samplers:
            self.warnings.append(f"Sampler '{sampler_name}' not found")
            return None

        return copy.deepcopy(self.resolved_samplers[sampler_name])

    def _build_combined_continent(self) -> Dict[str, Any]:
        """
        Build the combined continent sampler that includes spawnIsland inline.
        """
        # Get the continents sampler
        continents = self._extract_sampler_inline('continents')
        if not continents:
            # Fallback to hardcoded if not found
            return self._fallback_combined_continent()

        # Get spawnIsland sampler
        spawn_island = self._extract_sampler_inline('spawnIsland')

        # Get spot samplers
        spot_distance = self._extract_sampler_inline('spotDistance')
        spot_radius = self._extract_sampler_inline('spotRadius')

        # Build combined sampler that computes max(continents, spawnIsland, spotContribution)
        combined = {
            'dimensions': 2,
            'type': 'EXPRESSION',
            'expression': '''max(
  max(
    continentsBase(x, z),
    spawnIslandValue(x, z)
  ),
  spotContinentalFactor * max(0, 1-(spotDist(x, z)/spotRad(x, z))^2)
)''',
            'variables': {
                'spotContinentalFactor': 0.3,
            },
            'samplers': {
                'continentsBase': continents,
            }
        }

        # Add spawnIsland if found
        if spawn_island:
            combined['samplers']['spawnIslandValue'] = spawn_island
        else:
            # Fallback constant
            combined['samplers']['spawnIslandValue'] = {
                'dimensions': 2,
                'type': 'CONSTANT',
                'value': -1,
            }

        # Add spot samplers if found
        if spot_distance:
            combined['samplers']['spotDist'] = spot_distance
        else:
            combined['samplers']['spotDist'] = {'dimensions': 2, 'type': 'CONSTANT', 'value': 1000}

        if spot_radius:
            combined['samplers']['spotRad'] = spot_radius
        else:
            combined['samplers']['spotRad'] = {'dimensions': 2, 'type': 'CONSTANT', 'value': 1}

        return combined

    def _fallback_combined_continent(self) -> Dict[str, Any]:
        """Fallback hardcoded combined continent if resolution fails."""
        return {
            'dimensions': 2,
            'type': 'EXPRESSION',
            'expression': '-continentNoise(x / scale / globalScale, z / scale / globalScale) * spread + offset',
            'variables': {
                'globalScale': '$customization.yml:global-scale',
                'scale': '$customization.yml:continental-scale',
                'offset': '$customization.yml:continental-offset',
                'spread': '$customization.yml:continental-spread',
            },
            'samplers': {
                'continentNoise': {
                    'dimensions': 2,
                    'type': 'TRANSLATE',
                    'x': 10000,
                    'z': 10000,
                    'sampler': {
                        'type': 'RIDGED',
                        'lacunarity': 3,
                        'gain': 0.35,
                        'octaves': 3,
                        'sampler': {
                            'type': 'OPEN_SIMPLEX_2',
                            'salt': 1,
                            'frequency': '1 / 5000',
                        }
                    }
                }
            }
        }

    def _build_combined_climate_expression(self) -> Dict[str, Any]:
        """
        Build the combined climate index sampler that computes T×P×E in one pass.
        """
        # Get resolved samplers
        raw_elevation = self._extract_sampler_inline('rawElevation')
        flatness = self._extract_sampler_inline('flatness')
        raw_temperature = self._extract_sampler_inline('rawTemperature')
        raw_precipitation = self._extract_sampler_inline('rawPrecipitation')

        combined = {
            'dimensions': 2,
            'type': 'EXPRESSION',
            'expression': '''// Compute continent value (shared dependency)
c = combinedContinent(x, z);

// Compute elevation with continental modulation
rawElev = rawElevation(x, z);
flat = flatness(x, z);
elev = rawElev * (1 - flat) * herp(c, contZero, 0, contFull, 1);

// Compute temperature with altitude lapse
rawTemp = rawTemperature(x, z);
temp = rawTemp - lerp(elev, lapseStart, 0, 1, lapseRate);

// Compute precipitation with continental modulation
rawPrecip = rawPrecipitation(x, z);
precip = lerp(c, oceanThresh, 1, landThresh, rawPrecip);

// Convert to indices (0-11, 0-5, 0-3)
tempIdx = floor(clamp((temp + 1) / 2, 0, 0.9999) * 12);
precipIdx = floor(clamp((precip + 1) / 2, 0, 0.9999) * 6);
elevIdx = floor(clamp(elev / elevScale, 0, 0.9999) * 4);

// Encode to single value [-1, 1]
(tempIdx * 24 + precipIdx * 4 + elevIdx) / 287 * 2 - 1''',
            'variables': {
                # Elevation thresholds
                'contZero': '$customization.yml:elevation-continental-flat-threshold',
                'contFull': '$customization.yml:elevation-continental-full-height-threshold',
                'elevScale': 1.0,  # Normalized elevation scale
                # Temperature variables
                'lapseRate': '$customization.yml:temperature-altitude-lapse-rate',
                'lapseStart': '$customization.yml:temperature-altitude-lapse-start',
                # Precipitation variables
                'oceanThresh': '$customization.yml:precipitation-ocean-threshold',
                'landThresh': '$customization.yml:precipitation-land-threshold',
            },
            'functions': {
                '<<': '$math/functions/interpolation.yml:functions',
                'clamp': {
                    'arguments': ['x', 'minVal', 'maxVal'],
                    'expression': 'max(min(x, maxVal), minVal)',
                },
            },
            'samplers': {
                'combinedContinent': self._build_combined_continent(),
            }
        }

        # Add resolved samplers or fallbacks
        if raw_elevation:
            combined['samplers']['rawElevation'] = raw_elevation
        else:
            combined['samplers']['rawElevation'] = {
                'dimensions': 2,
                'type': 'EXPRESSION',
                'expression': 'noise(x / scale / globalScale, z / scale / globalScale) * multiplier + offset',
                'variables': {
                    'globalScale': '$customization.yml:global-scale',
                    'scale': '$customization.yml:elevation-scale',
                    'multiplier': '$customization.yml:elevation-multiplier',
                    'offset': '$customization.yml:elevation-offset',
                },
                'samplers': {
                    'noise': '$math/samplers/elevation.yml:samplers.rawElevation.samplers.noise'
                }
            }

        if flatness:
            combined['samplers']['flatness'] = flatness
        else:
            combined['samplers']['flatness'] = '$math/samplers/elevation.yml:samplers.flatness'

        if raw_temperature:
            combined['samplers']['rawTemperature'] = raw_temperature
        else:
            combined['samplers']['rawTemperature'] = '$math/samplers/temperature.yml:samplers.rawTemperature'

        if raw_precipitation:
            combined['samplers']['rawPrecipitation'] = raw_precipitation
        else:
            combined['samplers']['rawPrecipitation'] = '$math/samplers/precipitation.yml:samplers.rawPrecipitation'

        return combined

    def generate_combined_sampler_yml(self) -> str:
        """
        Generate the combined climate sampler YAML by reading and resolving source files.
        """
        # Load source samplers
        self.load_source_samplers()

        # Build the header
        header = '''# =============================================================================
# Combined Climate Samplers
# =============================================================================
#
# AUTO-GENERATED by generate_combined_climate.py
# DO NOT EDIT MANUALLY - changes will be overwritten
#
# These samplers compute multiple climate factors in a single pass, eliminating
# redundant calculations that occur when temperature, precipitation, and elevation
# are computed separately.
#
# Source files resolved:
'''
        for name, path in SOURCE_SAMPLERS.items():
            header += f'#   - {path}\n'

        header += '''#
# Encoding scheme:
#   climateIndex = (tempIndex * 24) + (precipIndex * 4) + elevIndex
#   where:
#     tempIndex: 0-11 (12 temperature zones)
#     precipIndex: 0-5 (6 precipitation levels)
#     elevIndex: 0-3 (4 elevation variants)
#
# The climateIndex ranges from 0 to 287, normalized to [-1, 1] for weighted lists.
# =============================================================================

'''

        # Build samplers structure
        samplers_section = {
            'samplers': {
                'combinedContinent': self._build_combined_continent(),
                'combinedClimate': self._build_combined_climate_expression(),
            }
        }

        # Convert to YAML
        yaml_content = yaml.dump(
            samplers_section,
            Dumper=YamlDumper,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )

        return header + yaml_content


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
# AUTO-GENERATED by generate_combined_climate.py
# DO NOT EDIT MANUALLY - changes will be overwritten
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

    # Create generator
    generator = CombinedClimateGenerator(base_dir)

    # Generate combined sampler
    print("\nGenerating combined sampler definition...")
    sampler_yml = generator.generate_combined_sampler_yml()

    # Print any warnings/errors from resolution
    if generator.warnings:
        print("\nWarnings:", file=sys.stderr)
        for w in generator.warnings:
            print(f"  - {w}", file=sys.stderr)

    if generator.errors:
        print("\nErrors:", file=sys.stderr)
        for e in generator.errors:
            print(f"  - {e}", file=sys.stderr)

    sampler_path = base_dir / 'math' / 'samplers' / 'combined_climate.yml'
    if args.dry_run:
        print(f"\n[DRY RUN] Would write to: {sampler_path}")
        print("-" * 40)
        print(sampler_yml[:3000] + "\n... (truncated)")
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
    print(f"Resolved samplers: {len(generator.resolved_samplers)}")

    biome_map = generate_climate_biome_mapping()
    unique_biomes = set(biome_map.values())
    print(f"Unique biomes in distribution: {len(unique_biomes)}")

    print("\nDone!")


if __name__ == "__main__":
    main()
