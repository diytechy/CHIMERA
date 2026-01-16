#!/usr/bin/env python3
"""
generate_combined_climate.py

Generates combined climate samplers by ANALYZING source sampler files and
automatically deriving optimized expressions that eliminate redundant calculations.

This script:
1. READS source sampler files (continents, spawnIsland, elevation, temperature, precipitation, spots)
2. ANALYZES dependency graphs to find shared/reused calculations
3. DERIVES combined expressions that compute shared values once
4. GENERATES optimized combined_climate.yml with mathematically simplified expressions

When any source file changes, re-running this script will:
- Re-analyze dependencies
- Re-derive expressions
- Re-generate optimized output

Output:
- math/samplers/combined_climate.yml - Optimized combined sampler definitions
- biome-distribution/stages/climate/combined_climate.yml - Single-pass climate distribution
"""
from ensure_module import ensure_modules
ensure_modules(["yaml", "re"])

import yaml
import sys
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, Set
from collections import OrderedDict, defaultdict
from dataclasses import dataclass, field


# =============================================================================
# Configuration
# =============================================================================

TEMPERATURE_WEIGHTS = [1, 1, 1, 1, 1, 1, 1, 3, 2, 1, 1, 4]
PRECIPITATION_WEIGHTS = [4, 1, 1, 1, 2, 3]
ELEVATION_WEIGHTS = [1, 1, 1, 1]

# Source sampler files to analyze
SOURCE_FILES = {
    'continents': 'math/samplers/continents.yml',
    'spawnIsland': 'math/samplers/spawnIsland.yml',
    'elevation': 'math/samplers/elevation.yml',
    'temperature': 'math/samplers/temperature.yml',
    'precipitation': 'math/samplers/precipitation.yml',
    'spots': 'math/samplers/spots.yml',
}

# Key samplers to analyze for the climate pipeline
CLIMATE_SAMPLERS = [
    ('continents', 'continents'),
    ('spawnIsland', 'spawnIsland'),
    ('elevation', 'elevation'),
    ('elevation', 'rawElevation'),
    ('elevation', 'flatness'),
    ('temperature', 'temperature'),
    ('temperature', 'rawTemperature'),
    ('precipitation', 'precipitation'),
    ('precipitation', 'rawPrecipitation'),
    ('spots', 'spotDistance'),
    ('spots', 'spotRadius'),
]


# =============================================================================
# Sampler Analysis Classes
# =============================================================================

@dataclass
class SamplerInfo:
    """Information about a sampler extracted from YAML."""
    name: str
    file_source: str
    sampler_type: str
    expression: Optional[str] = None
    variables: Dict[str, Any] = field(default_factory=dict)
    functions: Dict[str, Any] = field(default_factory=dict)
    nested_samplers: Dict[str, Any] = field(default_factory=dict)
    raw_config: Dict[str, Any] = field(default_factory=dict)

    # Dependencies discovered by analyzing expressions
    sampler_dependencies: Set[str] = field(default_factory=set)


class SamplerAnalyzer:
    """
    Analyzes sampler files to extract expressions, dependencies, and build
    a dependency graph for optimization.
    """

    def __init__(self, base_dir: Path = Path(".")):
        self.base_dir = base_dir
        self.file_cache: Dict[str, Dict] = {}
        self.samplers: Dict[str, SamplerInfo] = {}
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_deps: Dict[str, Set[str]] = defaultdict(set)

    def load_file(self, file_path: str) -> Optional[Dict]:
        """Load a YAML file, caching results."""
        if file_path in self.file_cache:
            return self.file_cache[file_path]

        full_path = self.base_dir / file_path
        if not full_path.exists():
            print(f"  Warning: File not found: {full_path}", file=sys.stderr)
            return None

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.file_cache[file_path] = data
                return data
        except Exception as e:
            print(f"  Error loading {file_path}: {e}", file=sys.stderr)
            return None

    def extract_sampler_info(self, name: str, config: Dict, file_source: str) -> SamplerInfo:
        """Extract information from a sampler configuration."""
        info = SamplerInfo(
            name=name,
            file_source=file_source,
            sampler_type=config.get('type', 'UNKNOWN'),
            raw_config=config,
        )

        # Extract expression if present
        if 'expression' in config:
            info.expression = config['expression']

        # Extract variables
        if 'variables' in config:
            info.variables = config['variables']

        # Extract functions
        if 'functions' in config:
            info.functions = config['functions']

        # Extract nested samplers
        if 'samplers' in config:
            info.nested_samplers = config['samplers']

        # For nested sampler types, look deeper
        if 'sampler' in config:
            nested = config['sampler']
            if isinstance(nested, dict) and 'expression' in nested:
                info.expression = nested.get('expression')
                info.variables.update(nested.get('variables', {}))

        return info

    def find_sampler_calls(self, expression: str) -> Set[str]:
        """Find sampler function calls in an expression."""
        if not expression:
            return set()

        # Pattern to find function calls like samplerName(x, z)
        # Matches: word followed by ( that isn't a known math function
        math_funcs = {'sin', 'cos', 'tan', 'abs', 'floor', 'ceil', 'round', 'sqrt',
                      'min', 'max', 'pow', 'exp', 'log', 'if', 'lerp', 'herp',
                      'parabolicMap', 'clamp', 'combine'}

        pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        matches = re.findall(pattern, expression)

        return {m for m in matches if m not in math_funcs}

    def analyze_dependencies(self, info: SamplerInfo):
        """Analyze a sampler's dependencies from its expression and nested samplers."""
        deps = set()

        # Find dependencies in expression
        if info.expression:
            deps.update(self.find_sampler_calls(info.expression))

        # Find dependencies in nested sampler references
        for nested_name, nested_config in info.nested_samplers.items():
            if isinstance(nested_config, str) and nested_config.startswith('$'):
                # External reference like $math/samplers/spots.yml:samplers.spotDistance
                deps.add(nested_name)
            elif isinstance(nested_config, dict):
                # Inline sampler - analyze recursively
                if 'expression' in nested_config:
                    deps.update(self.find_sampler_calls(nested_config['expression']))

        info.sampler_dependencies = deps

    def load_all_samplers(self):
        """Load and analyze all source sampler files."""
        print("Analyzing source sampler files...", file=sys.stderr)

        for source_name, file_path in SOURCE_FILES.items():
            print(f"  Loading: {file_path}", file=sys.stderr)
            data = self.load_file(file_path)

            if not data or 'samplers' not in data:
                continue

            for sampler_name, config in data['samplers'].items():
                if not isinstance(config, dict):
                    continue

                full_name = f"{source_name}.{sampler_name}"
                info = self.extract_sampler_info(sampler_name, config, file_path)
                self.samplers[full_name] = info
                self.samplers[sampler_name] = info  # Also store by simple name

                print(f"    Found: {sampler_name} (type: {info.sampler_type})", file=sys.stderr)

    def build_dependency_graph(self):
        """Build the dependency graph between samplers."""
        print("\nBuilding dependency graph...", file=sys.stderr)

        for name, info in self.samplers.items():
            self.analyze_dependencies(info)

            for dep in info.sampler_dependencies:
                self.dependency_graph[name].add(dep)
                self.reverse_deps[dep].add(name)

        # Print dependency summary
        print("\nDependency analysis:", file=sys.stderr)
        for sampler, deps in sorted(self.dependency_graph.items()):
            if deps and '.' not in sampler:  # Only show simple names
                print(f"  {sampler} -> {', '.join(sorted(deps))}", file=sys.stderr)

    def find_shared_dependencies(self) -> Dict[str, int]:
        """Find samplers that are used by multiple other samplers."""
        usage_count = defaultdict(int)

        for deps in self.dependency_graph.values():
            for dep in deps:
                usage_count[dep] += 1

        # Filter to those used more than once
        shared = {k: v for k, v in usage_count.items() if v > 1}

        if shared:
            print("\nShared dependencies (used multiple times):", file=sys.stderr)
            for name, count in sorted(shared.items(), key=lambda x: -x[1]):
                print(f"  {name}: used {count} times", file=sys.stderr)

        return shared

    def get_sampler_expression(self, name: str) -> Tuple[Optional[str], Dict, Dict]:
        """Get the expression, variables, and nested samplers for a sampler."""
        info = self.samplers.get(name)
        if not info:
            return None, {}, {}

        return info.expression, info.variables, info.nested_samplers

    def get_sampler_config(self, name: str) -> Optional[Dict]:
        """Get the raw config for a sampler."""
        info = self.samplers.get(name)
        return info.raw_config if info else None


# =============================================================================
# Combined Expression Generator
# =============================================================================

class CombinedExpressionGenerator:
    """
    Generates combined expressions by analyzing sampler dependencies and
    deriving optimized expressions that compute shared values once.
    """

    def __init__(self, analyzer: SamplerAnalyzer):
        self.analyzer = analyzer
        self.shared_deps = analyzer.find_shared_dependencies()

    def derive_continent_expression(self) -> Tuple[str, Dict, Dict]:
        """
        Derive the continent calculation expression from continents.yml.
        Returns (expression, variables, samplers_needed).
        """
        info = self.analyzer.samplers.get('continents')
        if not info or not info.expression:
            print("  Warning: Could not find continents expression", file=sys.stderr)
            return self._fallback_continent_expression()

        # Extract the expression - it references sampler, spawnIsland, spotDistance, spotRadius
        expr = info.expression.strip()
        variables = dict(info.variables)

        # The continents sampler references a 'sampler' which is the continent noise
        # We need to identify this and give it a proper name
        samplers_needed = {}

        # Look for the continent noise sampler in nested samplers
        if 'sampler' in info.nested_samplers:
            samplers_needed['continentNoise'] = info.nested_samplers['sampler']

        # Replace 'sampler(' with 'continentNoise(' in the expression
        expr = re.sub(r'\bsampler\s*\(', 'continentNoise(', expr)

        return expr, variables, samplers_needed

    def _fallback_continent_expression(self) -> Tuple[str, Dict, Dict]:
        """Fallback if we can't parse the source."""
        return (
            "-continentNoise(x / scale / globalScale, z / scale / globalScale) * spread + offset",
            {
                'globalScale': '$customization.yml:global-scale',
                'scale': '$customization.yml:continental-scale',
                'offset': '$customization.yml:continental-offset',
                'spread': '$customization.yml:continental-spread',
            },
            {}
        )

    def derive_elevation_expression(self) -> Tuple[str, Dict, Dict]:
        """
        Derive the elevation calculation from elevation.yml.
        """
        info = self.analyzer.samplers.get('elevation')
        if not info or not info.expression:
            return self._fallback_elevation_expression()

        expr = info.expression.strip()
        variables = dict(info.variables)

        return expr, variables, {}

    def _fallback_elevation_expression(self) -> Tuple[str, Dict, Dict]:
        return (
            "rawElevation(x, z) * (1-flatness(x, z)) * herp(continents(x, z), continentZero, 0, continentFull, 1)",
            {
                'continentZero': '$customization.yml:elevation-continental-flat-threshold',
                'continentFull': '$customization.yml:elevation-continental-full-height-threshold',
            },
            {}
        )

    def derive_temperature_expression(self) -> Tuple[str, Dict, Dict]:
        """
        Derive the temperature calculation from temperature.yml.
        """
        info = self.analyzer.samplers.get('temperature')
        if not info or not info.expression:
            return self._fallback_temperature_expression()

        expr = info.expression.strip()
        variables = dict(info.variables)

        return expr, variables, {}

    def _fallback_temperature_expression(self) -> Tuple[str, Dict, Dict]:
        return (
            "rawTemperature(x, z) - lerp(elevation(x, z), lapseStart, 0, 1, lapseRate)",
            {
                'lapseRate': '$customization.yml:temperature-altitude-lapse-rate',
                'lapseStart': '$customization.yml:temperature-altitude-lapse-start',
            },
            {}
        )

    def derive_precipitation_expression(self) -> Tuple[str, Dict, Dict]:
        """
        Derive the precipitation calculation from precipitation.yml.
        """
        info = self.analyzer.samplers.get('precipitation')
        if not info or not info.expression:
            return self._fallback_precipitation_expression()

        expr = info.expression.strip()
        variables = dict(info.variables)

        return expr, variables, {}

    def _fallback_precipitation_expression(self) -> Tuple[str, Dict, Dict]:
        return (
            "lerp(continents(x, z), oceanThreshold, 1, landThreshold, rawPrecipitation(x, z))",
            {
                'oceanThreshold': '$customization.yml:precipitation-ocean-threshold',
                'landThreshold': '$customization.yml:precipitation-land-threshold',
            },
            {}
        )

    def build_combined_expression(self) -> str:
        """
        Build the combined expression that computes climate index in one pass.
        This analyzes the source expressions and combines them to eliminate redundancy.
        """
        # Get expressions from source files
        cont_expr, cont_vars, _ = self.derive_continent_expression()
        elev_expr, elev_vars, _ = self.derive_elevation_expression()
        temp_expr, temp_vars, _ = self.derive_temperature_expression()
        precip_expr, precip_vars, _ = self.derive_precipitation_expression()

        # Build combined expression with shared values computed once
        combined = '''// ===== COMBINED CLIMATE EXPRESSION =====
// Auto-derived from source sampler files

// --- Shared: Continent value (used by elevation and precipitation) ---
// Derived from: continents.yml
'''
        combined += f"c = {cont_expr};\n\n"

        combined += '''// --- Elevation calculation ---
// Derived from: elevation.yml
'''
        # Replace continents(x, z) with 'c' since we computed it above
        elev_modified = re.sub(r'continents\s*\(\s*x\s*,\s*z\s*\)', 'c', elev_expr)
        combined += f"elev = {elev_modified};\n\n"

        combined += '''// --- Temperature calculation ---
// Derived from: temperature.yml
'''
        # Replace elevation(x, z) with 'elev'
        temp_modified = re.sub(r'elevation\s*\(\s*x\s*,\s*z\s*\)', 'elev', temp_expr)
        combined += f"temp = {temp_modified};\n\n"

        combined += '''// --- Precipitation calculation ---
// Derived from: precipitation.yml
'''
        # Replace continents(x, z) with 'c'
        precip_modified = re.sub(r'continents\s*\(\s*x\s*,\s*z\s*\)', 'c', precip_expr)
        combined += f"precip = {precip_modified};\n\n"

        combined += '''// --- Climate Index Encoding ---
// Convert continuous T/P/E to discrete indices and encode
tempIdx = floor(clamp((temp + 1) / 2, 0, 0.9999) * 12);
precipIdx = floor(clamp((precip + 1) / 2, 0, 0.9999) * 6);
elevIdx = floor(clamp(elev * 4, 0, 3.9999));

// Final encoded value in [-1, 1] range
(tempIdx * 24 + precipIdx * 4 + elevIdx) / 287 * 2 - 1'''

        return combined

    def collect_all_variables(self) -> Dict[str, Any]:
        """Collect all variables needed from the source expressions."""
        variables = OrderedDict()

        # Continent variables
        info = self.analyzer.samplers.get('continents')
        if info and info.variables:
            variables['# Continent variables (from continents.yml)'] = None
            for k, v in info.variables.items():
                variables[k] = v

        # Elevation variables
        info = self.analyzer.samplers.get('elevation')
        if info and info.variables:
            variables['# Elevation variables (from elevation.yml)'] = None
            for k, v in info.variables.items():
                if k not in variables:
                    variables[k] = v

        # Flatness variables
        info = self.analyzer.samplers.get('flatness')
        if info and info.variables:
            for k, v in info.variables.items():
                if k not in variables:
                    variables[k] = v

        # Temperature variables
        info = self.analyzer.samplers.get('temperature')
        if info and info.variables:
            variables['# Temperature variables (from temperature.yml)'] = None
            for k, v in info.variables.items():
                if k not in variables:
                    variables[k] = v

        # Precipitation variables
        info = self.analyzer.samplers.get('precipitation')
        if info and info.variables:
            variables['# Precipitation variables (from precipitation.yml)'] = None
            for k, v in info.variables.items():
                if k not in variables:
                    variables[k] = v

        return variables

    def collect_needed_samplers(self) -> Dict[str, Any]:
        """
        Collect the base noise samplers needed (ones that can't be inlined as expressions).
        These are the actual noise generators that must remain as samplers.
        """
        samplers = OrderedDict()

        # We need the base noise samplers - the ones that aren't expressions themselves
        # These are typically: continent noise, spawn island, spot distance/radius,
        # elevation noise, flatness noise, temperature noise, precipitation noise

        # Continent noise sampler
        cont_info = self.analyzer.samplers.get('continents')
        if cont_info and 'sampler' in cont_info.nested_samplers:
            samplers['# Continent noise (from continents.yml)'] = None
            samplers['continentNoise'] = cont_info.nested_samplers['sampler']

        # SpawnIsland sampler
        spawn_info = self.analyzer.samplers.get('spawnIsland')
        if spawn_info:
            samplers['# Spawn island (from spawnIsland.yml)'] = None
            samplers['spawnIsland'] = spawn_info.raw_config

        # Spot samplers - use references
        samplers['# Spot samplers (from spots.yml)'] = None
        samplers['spotDistance'] = '$math/samplers/spots.yml:samplers.spotDistance'
        samplers['spotRadius'] = '$math/samplers/spots.yml:samplers.spotRadius'

        # Raw elevation sampler - use reference to preserve the complex nested structure
        samplers['# Raw elevation (from elevation.yml)'] = None
        samplers['rawElevation'] = '$math/samplers/elevation.yml:samplers.rawElevation'

        # Flatness sampler
        flat_info = self.analyzer.samplers.get('flatness')
        if flat_info:
            samplers['# Flatness (from elevation.yml)'] = None
            samplers['flatness'] = '$math/samplers/elevation.yml:samplers.flatness'

        # River terrain erosion (from rivers.yml) - referenced by elevation
        samplers['# River terrain erosion (from rivers.yml)'] = None
        samplers['riverTerrainErosion'] = '$math/samplers/rivers.yml:samplers.riverTerrainErosion'

        # Raw temperature sampler
        samplers['# Temperature noise (from temperature.yml)'] = None
        samplers['rawTemperature'] = '$math/samplers/temperature.yml:samplers.rawTemperature'

        # Raw precipitation sampler
        samplers['# Precipitation noise (from precipitation.yml)'] = None
        samplers['rawPrecipitation'] = '$math/samplers/precipitation.yml:samplers.rawPrecipitation'

        return samplers


# =============================================================================
# YAML Generation
# =============================================================================

def format_yaml_value(value: Any, indent: int = 0) -> str:
    """Format a value as YAML with proper indentation."""
    prefix = '  ' * indent

    if value is None:
        return ''
    elif isinstance(value, str):
        if '\n' in value:
            lines = value.split('\n')
            return '|\n' + '\n'.join(prefix + '  ' + line for line in lines)
        elif value.startswith('$'):
            return value
        else:
            return value
    elif isinstance(value, bool):
        return 'true' if value else 'false'
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, list):
        result = '\n'
        for item in value:
            result += f"{prefix}- {format_yaml_value(item, indent + 1)}\n"
        return result.rstrip('\n')
    elif isinstance(value, dict):
        result = '\n'
        for k, v in value.items():
            if v is None:
                result += f"{prefix}{k}\n"
            else:
                formatted = format_yaml_value(v, indent + 1)
                if '\n' in formatted:
                    result += f"{prefix}{k}: {formatted}\n"
                else:
                    result += f"{prefix}{k}: {formatted}\n"
        return result.rstrip('\n')
    else:
        return str(value)


def generate_combined_sampler_yml(base_dir: Path = Path(".")) -> str:
    """
    Generate the combined climate sampler YAML by analyzing source files.
    """
    # Analyze source files
    analyzer = SamplerAnalyzer(base_dir)
    analyzer.load_all_samplers()
    analyzer.build_dependency_graph()

    # Generate combined expressions
    generator = CombinedExpressionGenerator(analyzer)
    combined_expr = generator.build_combined_expression()
    variables = generator.collect_all_variables()
    samplers = generator.collect_needed_samplers()

    # Build the YAML output
    output = '''# =============================================================================
# Combined Climate Samplers
# =============================================================================
#
# AUTO-GENERATED by generate_combined_climate.py
# DO NOT EDIT MANUALLY - regenerate by running the script
#
# This file was derived by analyzing:
'''
    for name, path in SOURCE_FILES.items():
        output += f'#   - {path}\n'

    output += '''#
# The expressions below were automatically combined to eliminate redundant
# calculations. Shared dependencies (like continents) are computed once.
#
# Encoding: climateIndex = (tempIdx * 24) + (precipIdx * 4) + elevIdx
# =============================================================================

samplers:
  combinedClimate:
    dimensions: 2
    type: EXPRESSION
    expression: |
'''

    # Add the combined expression with proper indentation
    for line in combined_expr.split('\n'):
        output += f'      {line}\n'

    # Add variables
    output += '\n    variables:\n'
    for key, value in variables.items():
        if key.startswith('#'):
            output += f'      {key}\n'
        elif value is not None:
            output += f'      {key}: {value}\n'

    # Add functions
    output += '''
    functions:
      "<<": $math/functions/interpolation.yml:functions
      clamp:
        arguments: [x, minVal, maxVal]
        expression: max(min(x, maxVal), minVal)

    samplers:
'''

    # Add samplers
    for key, value in samplers.items():
        if key.startswith('#'):
            output += f'      {key}\n'
        elif isinstance(value, str):
            output += f'      {key}: {value}\n'
        elif isinstance(value, dict):
            output += f'      {key}:\n'
            output += yaml.dump(value, default_flow_style=False, indent=2, sort_keys=False)
            # Re-indent the YAML dump
            lines = yaml.dump(value, default_flow_style=False, indent=2, sort_keys=False).split('\n')
            output = output.rsplit(f'      {key}:\n', 1)[0] + f'      {key}:\n'
            for line in lines:
                if line.strip():
                    output += f'        {line}\n'

    return output


# =============================================================================
# Biome Mapping (unchanged)
# =============================================================================

def generate_climate_biome_mapping() -> Dict[Tuple[int, int, int], str]:
    """Generate the mapping from (tempIdx, precipIdx, elevIdx) to biome name."""
    biome_map = {}

    precip_map = {
        0: ['ice-cap'] * 6,
        1: ['tundra'] * 6,
        2: ['cold-desert', 'cold-steppe', 'boreal-snowy-dry', 'boreal-snowy', 'boreal-snowy', 'boreal-snowy'],
        3: ['cold-desert', 'cold-steppe', 'boreal-cold-dry', 'boreal-cold', 'boreal-cold', 'boreal-cold'],
        4: ['cold-desert', 'cold-steppe', 'boreal-warm-dry', 'boreal-warm-dry', 'boreal-warm', 'boreal-warm'],
        5: ['cold-desert', 'cold-steppe', 'boreal-hot-dry', 'boreal-warm', 'boreal-warm', 'boreal-hot'],
        6: ['hot-desert', 'temperate-steppe', 'temperate-warm-dry', 'temperate-cold', 'temperate-cold', 'temperate-cold'],
        7: ['hot-desert', 'temperate-steppe', 'temperate-warm-dry', 'temperate-warm', 'temperate-warm', 'temperate-warm'],
        8: ['hot-desert', 'temperate-steppe', 'temperate-hot-dry', 'temperate-hot', 'temperate-hot', 'temperate-hot'],
        9: ['hot-steppe', 'hot-steppe', 'hot-steppe', 'tropical-savanna-wet', 'tropical-savanna-wet', 'tropical-savanna-wet'],
        10: ['hot-desert', 'hot-desert', 'hot-steppe', 'tropical-savanna-dry', 'tropical-monsoon', 'tropical-monsoon'],
        11: ['hot-desert', 'hot-desert', 'hot-steppe', 'tropical-savanna-dry', 'tropical-monsoon', 'tropical-rainforest'],
    }

    elev_map = {
        'ice-cap': ['ice-cap-flat', 'ice-cap', 'ice-cap', 'ice-cap-highlands'],
        'tundra': ['tundra-flat', 'tundra', 'tundra', 'tundra-highlands'],
        'hot-desert': ['hot-desert-flat', 'hot-desert', 'hot-desert', 'hot-desert-highlands'],
        'cold-desert': ['cold-desert-flat', 'cold-desert', 'cold-desert', 'cold-desert-highlands'],
        'hot-steppe': ['hot-steppe-flat', 'hot-steppe', 'hot-steppe', 'hot-steppe-highlands'],
        'cold-steppe': ['cold-steppe-flat', 'cold-steppe', 'cold-steppe', 'cold-steppe-highlands'],
        'temperate-steppe': ['temperate-steppe-flat', 'temperate-steppe', 'temperate-steppe', 'temperate-steppe-highlands'],
        'boreal-snowy': ['boreal-snowy-flat', 'boreal-snowy', 'boreal-snowy', 'boreal-snowy-highlands'],
        'boreal-snowy-dry': ['boreal-snowy-dry-flat', 'boreal-snowy-dry', 'boreal-snowy-dry', 'boreal-snowy-dry-highlands'],
        'boreal-cold': ['boreal-cold-flat', 'boreal-cold', 'boreal-cold', 'boreal-cold-highlands'],
        'boreal-cold-dry': ['boreal-cold-dry-flat', 'boreal-cold-dry', 'boreal-cold-dry', 'boreal-cold-dry-highlands'],
        'boreal-warm': ['boreal-warm-flat', 'boreal-warm', 'boreal-warm', 'boreal-warm-highlands'],
        'boreal-warm-dry': ['boreal-warm-dry-flat', 'boreal-warm-dry', 'boreal-warm-dry', 'boreal-warm-dry-highlands'],
        'boreal-hot': ['boreal-hot-flat', 'boreal-hot', 'boreal-hot', 'boreal-hot-highlands'],
        'boreal-hot-dry': ['boreal-hot-dry-flat', 'boreal-hot-dry', 'boreal-hot-dry', 'boreal-hot-dry-highlands'],
        'temperate-cold': ['temperate-cold-flat', 'temperate-cold', 'temperate-cold', 'temperate-cold-highlands'],
        'temperate-warm': ['temperate-warm-flat', 'temperate-warm', 'temperate-warm', 'temperate-warm-highlands'],
        'temperate-warm-dry': ['temperate-warm-dry-flat', 'temperate-warm-dry', 'temperate-warm-dry', 'temperate-warm-dry-highlands'],
        'temperate-hot': ['temperate-hot-flat', 'temperate-hot', 'temperate-hot', 'temperate-hot-highlands'],
        'temperate-hot-dry': ['temperate-hot-dry-flat', 'temperate-hot-dry', 'temperate-hot-dry', 'temperate-hot-dry-highlands'],
        'tropical-rainforest': ['tropical-rainforest-flat', 'tropical-rainforest', 'tropical-rainforest', 'tropical-rainforest-highlands'],
        'tropical-monsoon': ['tropical-monsoon-flat', 'tropical-monsoon', 'tropical-monsoon', 'tropical-monsoon-highlands'],
        'tropical-savanna-dry': ['tropical-savanna-dry-flat', 'tropical-savanna-dry', 'tropical-savanna-dry', 'tropical-savanna-dry-highlands'],
        'tropical-savanna-wet': ['tropical-savanna-wet-flat', 'tropical-savanna-wet', 'tropical-savanna-wet', 'tropical-savanna-wet-highlands'],
    }

    for t in range(12):
        for p in range(6):
            after_precip = precip_map[t][p]
            for e in range(4):
                if after_precip in elev_map:
                    final_biome = elev_map[after_precip][e]
                else:
                    suffix = ['-flat', '', '', '-highlands'][e]
                    final_biome = after_precip + suffix if suffix else after_precip
                biome_map[(t, p, e)] = final_biome

    return biome_map


# =============================================================================
# Biome Dimensional Mappings
# =============================================================================
# Different biome types use different climate dimensions:
# - land: T × P × E (full 288 combinations)
# - mesa, crater-lake, extinct-volcano: T × P (72 combinations)
# - shallow-ocean, ocean: T × E (48 combinations)
# - island-shallow-ocean, coast: T only (12 combinations)
# =============================================================================

# Temperature × Precipitation mapping for mesa/crater-lake/extinct-volcano
# Maps (tempIdx, precipIdx) to biome prefix
def get_tp_biome_prefix(t: int, p: int) -> str:
    """
    Get biome prefix for Temperature × Precipitation biomes.

    Precipitation indices:
      0=desert(4), 1=desert-border(1), 2=semi-arid(1), 3=mid(1), 4=mildly-wet(2), 5=very-wet(3)

    For dry conditions (p=0,1,2), desert variants are used.
    For wet conditions (p=3,4,5), climate-based variants are used.
    """
    # Temperature zone groupings
    is_polar = t in [0, 1]  # ice-cap, tundra
    is_boreal = t in [2, 3, 4, 5]  # boreal zones
    is_temperate = t in [6, 7, 8]  # temperate zones
    is_tropical = t in [9, 10, 11]  # tropical zones

    # Precipitation: dry (desert/steppe) vs normal
    is_desert = p in [0, 1]  # desert, desert-border
    is_semi_arid = p == 2  # semi-arid

    if is_polar:
        if is_desert or is_semi_arid:
            return 'cold-desert'
        return 'polar'
    elif is_boreal:
        if is_desert or is_semi_arid:
            return 'cold-desert'
        return 'boreal'
    elif is_temperate:
        if is_desert:
            return 'desert'
        elif is_semi_arid:
            return 'temperate'  # semi-arid temperate still uses temperate prefix
        return 'temperate'
    else:  # tropical
        if is_desert or is_semi_arid:
            return 'desert'
        return 'tropical'


# Temperature × Elevation mapping for ocean biomes
# Maps (tempIdx, elevIdx) to biome prefix and suffix
def get_te_ocean_biome(t: int, e: int, base: str) -> str:
    """
    Get biome name for Temperature × Elevation ocean biomes.

    Elevation indices for ocean:
      0=shallow, 1=shallow-midlands, 2=normal, 3=deep
    """
    # Temperature prefix
    if t in [0, 1]:  # polar
        temp_prefix = 'polar'
    elif t in [2, 3, 4, 5]:  # boreal
        temp_prefix = 'boreal'
    elif t in [6, 7, 8]:  # temperate
        temp_prefix = 'temperate'
    else:  # tropical
        temp_prefix = 'hot'

    # Elevation suffix for ocean
    if base == 'shallow-ocean':
        if e in [0, 1]:
            return f"{temp_prefix}-shallow-ocean" if e == 0 else f"{temp_prefix}-shallow-ocean-midlands"
        elif e == 2:
            return f"{temp_prefix}-ocean"
        else:
            return f"{temp_prefix}-deep-ocean"
    elif base == 'ocean':
        if e in [0, 1]:
            return f"{temp_prefix}-ocean"
        else:
            return f"{temp_prefix}-deep-ocean"
    elif base == 'deep-ocean':
        return f"{temp_prefix}-deep-ocean"

    return f"{temp_prefix}-{base}"


# Temperature-only mapping
TEMPERATURE_PREFIX_MAP = {
    0: 'polar',      # ice-cap
    1: 'polar',      # tundra
    2: 'boreal',     # boreal-snowy
    3: 'boreal',     # boreal-cold
    4: 'boreal',     # boreal-warm
    5: 'boreal',     # boreal-hot
    6: 'temperate',  # temperate-cold
    7: 'temperate',  # temperate-warm
    8: 'temperate',  # temperate-hot
    9: 'hot',        # tropical-savanna-wet
    10: 'hot',       # tropical-monsoon
    11: 'hot',       # tropical-rainforest
}


def generate_tp_mapping(parent_biome: str) -> List[Tuple[str, int]]:
    """
    Generate T×P weighted list for mesa/crater-lake/extinct-volcano.
    Returns 288 entries to match combinedClimate index alignment.
    """
    entries = []

    for t in range(12):
        for p in range(6):
            prefix = get_tp_biome_prefix(t, p)
            biome_name = f"{prefix}-{parent_biome}"

            for e in range(4):
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                entries.append((biome_name, weight))

    return entries


def generate_te_mapping(parent_biome: str) -> List[Tuple[str, int]]:
    """
    Generate T×E weighted list for ocean biomes.
    Returns 288 entries to match combinedClimate index alignment.
    """
    entries = []

    for t in range(12):
        for p in range(6):
            for e in range(4):
                biome_name = get_te_ocean_biome(t, e, parent_biome)
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                entries.append((biome_name, weight))

    return entries


def generate_t_only_mapping(parent_biome: str) -> List[Tuple[str, int]]:
    """
    Generate temperature-only weighted list.
    Returns 288 entries to match combinedClimate index alignment.
    """
    entries = []

    for t in range(12):
        prefix = TEMPERATURE_PREFIX_MAP[t]
        biome_name = f"{prefix}-{parent_biome}"

        for p in range(6):
            for e in range(4):
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                entries.append((biome_name, weight))

    return entries


# Biome type categorization
TP_BIOMES = ['mesa', 'crater-lake', 'extinct-volcano']  # Temperature × Precipitation
TE_BIOMES = ['shallow-ocean', 'ocean', 'deep-ocean']  # Temperature × Elevation
T_ONLY_BIOMES = [  # Temperature only
    'coast', 'island', 'island-coast', 'island-shallow-ocean',
    'vast-forest', 'vast-forest-coast', 'mushroom', 'mushroom-coast',
]


def generate_combined_stage_yml() -> str:
    """Generate the combined climate stage YAML with all biome type distributions."""
    content = '''# =============================================================================
# Combined Climate Stage
# =============================================================================
#
# AUTO-GENERATED by generate_combined_climate.py
#
# This single stage replaces the three separate temperature, precipitation, and
# elevation stages. The combinedClimate sampler computes all factors in one pass.
#
# Dimensional mappings:
# - land: T × P × E (full 288 combinations → 72 unique biomes)
# - mesa, crater-lake, extinct-volcano: T × P (desert-mesa, cold-desert-mesa, etc.)
# - shallow-ocean, ocean, deep-ocean: T × E (temperate-shallow-ocean-midlands, etc.)
# - coast, island, vast-forest, mushroom: T only
#
# Usage: Replace temperature/precipitation/elevation stages with:
#   - << biome-distribution/stages/climate/combined_climate.yml:stages
# =============================================================================

stages:
  - type: REPLACE_LIST
    sampler: $math/samplers/combined_climate.yml:samplers.combinedClimate

    default-from: land
    default-to:
'''

    # Add land distribution (full T×P×E)
    biome_map = generate_climate_biome_mapping()
    for t in range(12):
        for p in range(6):
            for e in range(4):
                biome = biome_map.get((t, p, e), 'unknown')
                weight = TEMPERATURE_WEIGHTS[t] * PRECIPITATION_WEIGHTS[p] * ELEVATION_WEIGHTS[e]
                content += f"      - {biome}: {weight}\n"

    content += "\n    to:\n"

    # T×P biomes (mesa, crater-lake, extinct-volcano)
    content += "      # --- T×P biomes (temperature × precipitation) ---\n"
    for biome in TP_BIOMES:
        content += f"      {biome}:\n"
        entries = generate_tp_mapping(biome)
        for biome_name, weight in entries:
            content += f"        - {biome_name}: {weight}\n"

    # T×E biomes (ocean types)
    content += "\n      # --- T×E biomes (temperature × elevation) ---\n"
    for biome in TE_BIOMES:
        content += f"      {biome}:\n"
        entries = generate_te_mapping(biome)
        for biome_name, weight in entries:
            content += f"        - {biome_name}: {weight}\n"

    # T-only biomes
    content += "\n      # --- T-only biomes (temperature only) ---\n"
    for biome in T_ONLY_BIOMES:
        content += f"      {biome}:\n"
        entries = generate_t_only_mapping(biome)
        for biome_name, weight in entries:
            content += f"        - {biome_name}: {weight}\n"

    return content


# =============================================================================
# Main
# =============================================================================

def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate combined climate samplers')
    parser.add_argument('-b', '--base-dir', type=str, default='.', help='Base directory')
    parser.add_argument('--dry-run', action='store_true', help='Print without writing')

    args = parser.parse_args()
    base_dir = Path(args.base_dir)

    print("=" * 70)
    print("Combined Climate Sampler Generator")
    print("=" * 70)

    # Generate combined sampler
    print("\nAnalyzing and generating combined sampler...\n")
    sampler_yml = generate_combined_sampler_yml(base_dir)

    sampler_path = base_dir / 'math' / 'samplers' / 'combined_climate.yml'
    if args.dry_run:
        print(f"\n[DRY RUN] Would write to: {sampler_path}")
        print("-" * 40)
        print(sampler_yml[:2500] + "\n... (truncated)")
    else:
        sampler_path.parent.mkdir(parents=True, exist_ok=True)
        with open(sampler_path, 'w', encoding='utf-8') as f:
            f.write(sampler_yml)
        print(f"\nWritten to: {sampler_path}")
        print(f"Lines: {len(sampler_yml.splitlines())}")

    # Generate combined stage
    print("\nGenerating combined stage...")
    stage_yml = generate_combined_stage_yml()

    stage_path = base_dir / 'biome-distribution' / 'stages' / 'climate' / 'combined_climate.yml'
    if args.dry_run:
        print(f"\n[DRY RUN] Would write to: {stage_path}")
    else:
        stage_path.parent.mkdir(parents=True, exist_ok=True)
        with open(stage_path, 'w', encoding='utf-8') as f:
            f.write(stage_yml)
        print(f"Written to: {stage_path}")

    print("\nDone!")


if __name__ == "__main__":
    main()
