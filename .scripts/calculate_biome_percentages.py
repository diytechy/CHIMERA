#!/usr/bin/env python3
"""
calculate_biome_percentages.py

Calculates actual biome percentages by tracing through Terra preset pipelines.
Properly handles YAML anchors/aliases and cascading probability calculations.

Now also handles extrusion biomes (caves, underground biomes) which generate
content below the surface level. Extrusion biomes are tracked separately so
surface biomes still add to 100%.

Includes schema validation for Terra stage types to catch configuration errors.
"""
from ensure_module import ensure_modules

# Example: ensure 'requests' is installed
requests = ensure_modules(["yaml", "re", "csv"])


import yaml
import re
import sys
import csv
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional, Set


# =============================================================================
# Terra Schema Validation
# =============================================================================

class TerraSchemaValidator:
    """
    Validates Terra configuration files against known schema.

    Based on Terra 7.0 source code:
    - Stage types from biome-provider-pipeline addon
    - Sampler types from noise addon
    """

    # Valid pipeline stage types and their required fields
    STAGE_TYPES = {
        'REPLACE': {
            'required': ['from', 'to'],
            'optional': ['sampler', 'range'],
        },
        'REPLACE_LIST': {
            'required': ['default-from', 'default-to', 'to'],
            'optional': ['sampler', 'range'],
        },
        'BORDER': {
            'required': ['from', 'replace', 'to'],
            'optional': ['sampler'],
        },
        'BORDER_LIST': {
            'required': ['from', 'default-replace', 'default-to', 'replace'],
            'optional': ['sampler'],
        },
        'SMOOTH': {
            'required': [],
            'optional': ['sampler'],
        },
        'FRACTAL_EXPAND': {
            'required': [],
            'optional': ['sampler'],
        },
    }

    # Valid sampler types
    SAMPLER_TYPES = {
        'CELLULAR', 'CONSTANT', 'DOMAIN_WARP', 'EXPRESSION',
        'GAUSSIAN', 'IMAGE', 'KERNEL', 'LINEAR', 'NORMALIZER',
        'OPEN_SIMPLEX_2', 'OPEN_SIMPLEX_2S', 'PERLIN', 'PROBABILITY',
        'SIMPLEX', 'VALUE', 'VALUE_CUBIC', 'WHITE_NOISE',
        'DISTANCE', 'LINEAR_HEIGHTMAP', 'TRANSLATE', 'CLAMP',
        'ADD', 'SUB', 'MUL', 'DIV', 'MAX', 'MIN',
    }

    # Valid provider types
    PROVIDER_TYPES = {
        'PIPELINE', 'EXTRUSION', 'SINGLE', 'SAMPLER', 'IMAGE',
    }

    def __init__(self):
        self.errors: List[Tuple[str, str, str]] = []  # (file, location, message)
        self.warnings: List[Tuple[str, str, str]] = []
        # Track which stage files failed to load and which presets were affected
        self.failed_stage_files: Dict[str, List[str]] = defaultdict(list)  # file -> [presets]
        self.skipped_stages_by_preset: Dict[str, List[str]] = defaultdict(list)  # preset -> [files]

    def record_failed_stage_load(self, stage_file: str, preset_name: str):
        """Record that a stage file failed to load for a preset."""
        self.failed_stage_files[stage_file].append(preset_name)
        self.skipped_stages_by_preset[preset_name].append(stage_file)

    def validate_stage(self, stage: Dict, file_path: str, stage_index: int) -> bool:
        """Validate a single pipeline stage configuration."""
        if not isinstance(stage, dict):
            return True  # Skip non-dict stages (e.g., string references)

        stage_type = stage.get('type')
        location = f"stage[{stage_index}]"

        if not stage_type:
            self.errors.append((file_path, location, "Stage missing 'type' field"))
            return False

        if stage_type not in self.STAGE_TYPES:
            # Check for common typos
            similar = self._find_similar(stage_type, self.STAGE_TYPES.keys())
            msg = f"Invalid stage type '{stage_type}'"
            if similar:
                msg += f". Did you mean '{similar}'?"
            self.errors.append((file_path, location, msg))
            return False

        # Check required fields
        schema = self.STAGE_TYPES[stage_type]
        for field in schema['required']:
            if field not in stage:
                self.errors.append((
                    file_path, location,
                    f"Stage type '{stage_type}' missing required field '{field}'"
                ))

        # Validate nested sampler if present
        if 'sampler' in stage:
            self.validate_sampler(stage['sampler'], file_path, f"{location}.sampler")

        return True

    def validate_sampler(self, sampler: Any, file_path: str, location: str) -> bool:
        """Validate a sampler configuration."""
        if not isinstance(sampler, dict):
            return True

        sampler_type = sampler.get('type')
        if not sampler_type:
            # Sampler might be a reference or have implicit type
            return True

        if sampler_type not in self.SAMPLER_TYPES:
            similar = self._find_similar(sampler_type, self.SAMPLER_TYPES)
            msg = f"Unknown sampler type '{sampler_type}'"
            if similar:
                msg += f". Did you mean '{similar}'?"
            self.warnings.append((file_path, location, msg))

        # Recursively validate nested samplers
        for key in ['sampler', 'samplers', 'lookup']:
            if key in sampler:
                nested = sampler[key]
                if isinstance(nested, dict):
                    if 'type' in nested:
                        self.validate_sampler(nested, file_path, f"{location}.{key}")
                    else:
                        # Named samplers dict
                        for name, s in nested.items():
                            self.validate_sampler(s, file_path, f"{location}.{key}.{name}")

        return True

    def validate_anchors_and_aliases(self, file_path: Path) -> List[str]:
        """
        Pre-parse validation of YAML anchors and aliases.

        Checks:
        1. No anchor is defined more than once
        2. All aliases reference anchors that were defined earlier

        Returns list of error messages.
        """
        errors = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return [f"Could not read file: {e}"]

        lines = content.split('\n')

        # Track anchors: name -> (line_number, column)
        anchors_defined: Dict[str, Tuple[int, int]] = {}
        # Track aliases: name -> [(line_number, column), ...]
        aliases_used: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

        # Regex patterns for anchors and aliases
        # Anchor: &name (not preceded by *)
        anchor_pattern = re.compile(r'(?<!\*)&([a-zA-Z_][a-zA-Z0-9_]*)')
        # Alias: *name
        alias_pattern = re.compile(r'\*([a-zA-Z_][a-zA-Z0-9_]*)')

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            line_content = line.split('#')[0] if '#' in line else line

            # Find anchors
            for match in anchor_pattern.finditer(line_content):
                anchor_name = match.group(1)
                col = match.start() + 1

                if anchor_name in anchors_defined:
                    first_line, first_col = anchors_defined[anchor_name]
                    errors.append(
                        f"Line {line_num}: Duplicate anchor '&{anchor_name}' "
                        f"(first defined at line {first_line}). "
                        f"Use alias '*{anchor_name}' to reference it instead."
                    )
                else:
                    anchors_defined[anchor_name] = (line_num, col)

            # Find aliases
            for match in alias_pattern.finditer(line_content):
                alias_name = match.group(1)
                col = match.start() + 1
                aliases_used[alias_name].append((line_num, col))

        # Check for undefined aliases
        for alias_name, usages in aliases_used.items():
            if alias_name not in anchors_defined:
                for line_num, col in usages:
                    errors.append(
                        f"Line {line_num}: Alias '*{alias_name}' references undefined anchor. "
                        f"Define anchor '&{alias_name}' before using it."
                    )
            else:
                # Check that alias is used after anchor is defined
                anchor_line = anchors_defined[alias_name][0]
                for line_num, col in usages:
                    if line_num < anchor_line:
                        errors.append(
                            f"Line {line_num}: Alias '*{alias_name}' used before anchor is defined "
                            f"(anchor defined at line {anchor_line})."
                        )

        return errors

    def validate_yaml_file(self, file_path: Path) -> Tuple[Optional[Dict], List[str]]:
        """
        Load and validate a YAML file.
        Returns (parsed_data, errors) where errors is a list of error messages.
        """
        errors = []

        # Pre-parse validation for anchors and aliases
        anchor_errors = self.validate_anchors_and_aliases(file_path)
        if anchor_errors:
            errors.extend(anchor_errors)
            # Don't try to parse if we found anchor/alias issues
            return None, errors

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data, errors
        except yaml.YAMLError as e:
            # Extract meaningful error info
            error_str = str(e)
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                # Check for common issues and provide helpful messages
                if 'duplicate anchor' in error_str.lower():
                    # Extract anchor name from error
                    import re as regex
                    anchor_match = regex.search(r"anchor ['\"]?(\w+)['\"]?", error_str)
                    anchor_name = anchor_match.group(1) if anchor_match else "unknown"
                    error_msg = (
                        f"YAML error at line {mark.line + 1}: Duplicate anchor '&{anchor_name}'. "
                        f"Use alias '*{anchor_name}' to reference existing anchor instead of redefining it."
                    )
                else:
                    error_msg = f"YAML error at line {mark.line + 1}, column {mark.column + 1}: {e.problem}"
            else:
                error_msg = f"YAML error: {error_str.split(chr(10))[0]}"
            errors.append(error_msg)
            return None, errors
        except Exception as e:
            errors.append(f"Error reading file: {e}")
            return None, errors

    def validate_stage_file(self, file_path: Path) -> bool:
        """Validate a stage definition file."""
        data, yaml_errors = self.validate_yaml_file(file_path)

        for err in yaml_errors:
            self.errors.append((str(file_path), "file", err))

        if data is None:
            return False

        stages = data.get('stages', [])
        if not isinstance(stages, list):
            return True

        for i, stage in enumerate(stages):
            self.validate_stage(stage, str(file_path), i)

        return True

    def _find_similar(self, value: str, candidates: Any) -> Optional[str]:
        """Find a similar string from candidates (for typo suggestions)."""
        value_lower = value.lower().replace('-', '_')
        for candidate in candidates:
            candidate_lower = candidate.lower().replace('-', '_')
            # Check for common transformations
            if value_lower == candidate_lower:
                return candidate
            # Check Levenshtein distance of 1-2
            if self._levenshtein_distance(value_lower, candidate_lower) <= 2:
                return candidate
        return None

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return TerraSchemaValidator._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def get_report(self) -> str:
        """Generate a validation report."""
        lines = []

        if self.errors:
            lines.append("\n" + "=" * 70)
            lines.append("SCHEMA VALIDATION ERRORS:")
            lines.append("=" * 70)
            for file_path, location, message in self.errors:
                lines.append(f"  ERROR in {file_path}")
                lines.append(f"    Location: {location}")
                lines.append(f"    Message: {message}")
                lines.append("")

        if self.warnings:
            lines.append("\n" + "-" * 70)
            lines.append("SCHEMA VALIDATION WARNINGS:")
            lines.append("-" * 70)
            for file_path, location, message in self.warnings:
                lines.append(f"  WARNING in {file_path}")
                lines.append(f"    Location: {location}")
                lines.append(f"    Message: {message}")
                lines.append("")

        # Report skipped stage files and their impact
        if self.skipped_stages_by_preset:
            lines.append("\n" + "=" * 70)
            lines.append("SKIPPED STAGE FILES (biome calculations may be incomplete):")
            lines.append("=" * 70)
            for preset_name in sorted(self.skipped_stages_by_preset.keys()):
                skipped_files = self.skipped_stages_by_preset[preset_name]
                lines.append(f"\n  Preset '{preset_name}' skipped {len(skipped_files)} stage file(s):")
                for stage_file in skipped_files:
                    lines.append(f"    - {stage_file}")
            lines.append("")
            lines.append("  These presets may have missing or incorrect biome percentages.")
            lines.append("  Fix the errors above and re-run to get accurate calculations.")
            lines.append("")

        if not self.errors and not self.warnings and not self.skipped_stages_by_preset:
            lines.append("\nSchema validation passed - no errors or warnings found.")

        return "\n".join(lines)

    def has_errors(self) -> bool:
        """Check if any validation errors were found."""
        return len(self.errors) > 0


# Global validator instance
_validator: Optional[TerraSchemaValidator] = None

def get_validator() -> TerraSchemaValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = TerraSchemaValidator()
    return _validator


# =============================================================================
# Climate Context Tracking
# =============================================================================

@dataclass
class ClimateContext:
    """
    Tracks climate attributes for a biome.

    Attributes:
        origin_type: "Land" or "Ocean" based on source biome
        temperature: Normalized temperature value (0=coldest, 1=hottest), None if not climate-affected
        precipitation: Normalized precipitation value (0=driest, 1=wettest), None if not climate-affected
        elevation: Normalized elevation value (0=lowest, 1=highest), None if not climate-affected
    """
    origin_type: Optional[str] = None
    temperature: Optional[float] = None
    precipitation: Optional[float] = None
    elevation: Optional[float] = None

    def copy(self) -> 'ClimateContext':
        return ClimateContext(
            origin_type=self.origin_type,
            temperature=self.temperature,
            precipitation=self.precipitation,
            elevation=self.elevation
        )

    @staticmethod
    def weighted_combine(contexts: List[Tuple['ClimateContext', float]]) -> 'ClimateContext':
        """
        Combine multiple climate contexts with weights.
        Returns a new context with weighted average values.
        """
        if not contexts:
            return ClimateContext()

        total_weight = sum(w for _, w in contexts)
        if total_weight <= 0:
            return ClimateContext()

        # Determine origin type (use majority)
        origin_counts: Dict[str, float] = defaultdict(float)
        for ctx, weight in contexts:
            if ctx.origin_type:
                origin_counts[ctx.origin_type] += weight

        origin_type = max(origin_counts.keys(), key=lambda k: origin_counts[k]) if origin_counts else None

        # Calculate weighted averages for numeric fields
        def weighted_avg(field_name: str) -> Optional[float]:
            values = [(getattr(ctx, field_name), w) for ctx, w in contexts if getattr(ctx, field_name) is not None]
            if not values:
                return None
            total = sum(v * w for v, w in values)
            weight_sum = sum(w for _, w in values)
            return total / weight_sum if weight_sum > 0 else None

        return ClimateContext(
            origin_type=origin_type,
            temperature=weighted_avg('temperature'),
            precipitation=weighted_avg('precipitation'),
            elevation=weighted_avg('elevation')
        )


class ClimateTracker:
    """
    Tracks climate context for biomes as they flow through the pipeline.

    The climate values are derived from the position in weighted lists:
    - Temperature: ice-cap (0) to tropical-rainforest (1)
    - Precipitation: desert (0) to veryWet (1)
    - Elevation: flat/deep (0) to highlands (1)
    """

    # Temperature bands from temperature.yml (coldest to hottest)
    TEMPERATURE_BANDS = [
        'ice-cap', 'tundra', 'boreal-snowy', 'boreal-cold', 'boreal-warm', 'boreal-hot',
        'temperate-cold', 'temperate-warm', 'temperate-hot',
        'tropical-savanna-wet', 'tropical-monsoon', 'tropical-rainforest'
    ]

    # Precipitation bands from precipitation.yml (driest to wettest)
    PRECIPITATION_BANDS = ['desert', 'desertBorder', 'semiArid', 'mid', 'mildlyWet', 'veryWet']

    # Elevation bands from elevation.yml (lowest to highest)
    ELEVATION_BANDS = ['flat', 'lowlands', 'midlands', 'highlands']
    OCEAN_ELEVATION_BANDS = ['deep', 'regular', 'shallow']

    def __init__(self):
        # Maps biome_id -> ClimateContext
        self.contexts: Dict[str, ClimateContext] = {}
        # Maps biome_id -> list of (parent_biome, weight) for tracking lineage
        self.lineage: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def set_origin(self, biome: str, origin_type: str):
        """Set the origin type (Land/Ocean) for a source biome."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].origin_type = origin_type

    def get_context(self, biome: str) -> ClimateContext:
        """Get the climate context for a biome."""
        return self.contexts.get(biome, ClimateContext())

    def set_context(self, biome: str, context: ClimateContext):
        """Set the climate context for a biome."""
        self.contexts[biome] = context

    def propagate_context(self, from_biome: str, to_biome: str, weight: float = 1.0):
        """Propagate climate context from one biome to another."""
        if from_biome in self.contexts:
            self.lineage[to_biome].append((from_biome, weight))

    def apply_temperature(self, biome: str, band_index: int):
        """Apply temperature band to a biome."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        # Normalize to 0-1 range
        self.contexts[biome].temperature = band_index / max(1, len(self.TEMPERATURE_BANDS) - 1)

    def apply_precipitation(self, biome: str, band_index: int):
        """Apply precipitation band to a biome."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].precipitation = band_index / max(1, len(self.PRECIPITATION_BANDS) - 1)

    def apply_elevation(self, biome: str, band_index: int, is_ocean: bool = False):
        """Apply elevation band to a biome."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        bands = self.OCEAN_ELEVATION_BANDS if is_ocean else self.ELEVATION_BANDS
        self.contexts[biome].elevation = band_index / max(1, len(bands) - 1)

    def finalize_contexts(self):
        """
        Finalize all contexts by computing weighted combinations from lineage.
        Call this after all pipeline processing is complete.
        """
        # Process biomes that have lineage information
        for biome, parents in self.lineage.items():
            if not parents:
                continue

            parent_contexts = []
            for parent_biome, weight in parents:
                if parent_biome in self.contexts:
                    parent_contexts.append((self.contexts[parent_biome], weight))

            if parent_contexts:
                # Combine parent contexts, preserving any directly-set values
                combined = ClimateContext.weighted_combine(parent_contexts)

                # Merge with existing context (directly-set values take precedence)
                existing = self.contexts.get(biome, ClimateContext())
                if existing.origin_type is None:
                    existing.origin_type = combined.origin_type
                if existing.temperature is None:
                    existing.temperature = combined.temperature
                if existing.precipitation is None:
                    existing.precipitation = combined.precipitation
                if existing.elevation is None:
                    existing.elevation = combined.elevation

                self.contexts[biome] = existing

    def copy(self) -> 'ClimateTracker':
        """Create a copy of this tracker."""
        new_tracker = ClimateTracker()
        new_tracker.contexts = {k: v.copy() for k, v in self.contexts.items()}
        new_tracker.lineage = {k: list(v) for k, v in self.lineage.items()}
        return new_tracker

    @staticmethod
    def infer_climate_from_name(biome_id: str) -> ClimateContext:
        """
        Infer climate attributes from biome naming patterns.

        Terra biomes follow naming conventions that indicate climate:
        - Temperature: polar/ice < boreal/cold < temperate < tropical/hot
        - Precipitation: desert/arid < steppe < dry < wet/monsoon/rainforest
        - Elevation: flat < lowlands < midlands < highlands / deep < regular < shallow
        - Origin: ocean/deep-ocean/shallow-ocean = Ocean, others = Land
        """
        name_lower = biome_id.lower().replace('_', '-')

        # Determine origin type (Land vs Ocean)
        origin_type = None
        ocean_patterns = [
            'ocean', 'deep-ocean', 'shallow-ocean', 'sea', 'reef', 'kelp',
            'depths',  # DEEP_DEPTHS, etc.
            'abyssal',  # ABYSSAL_ALLEYS, etc.
            'trench',   # Ocean trenches
        ]
        for pattern in ocean_patterns:
            if pattern in name_lower:
                origin_type = 'Ocean'
                break
        if origin_type is None:
            origin_type = 'Land'

        # Infer temperature (0 = coldest, 1 = hottest)
        temperature = None
        temp_patterns = [
            # (pattern, normalized_value)
            ('ice-cap', 0.0), ('polar', 0.05), ('frozen', 0.05),
            ('tundra', 0.1), ('ice', 0.1), ('icy', 0.1), ('snowy', 0.15),
            ('boreal', 0.3), ('cold', 0.35), ('taiga', 0.3),
            ('temperate', 0.5),
            ('warm', 0.6), ('mediterranean', 0.65),
            ('hot', 0.75), ('tropical', 0.85), ('jungle', 0.85),
            ('savanna', 0.8), ('monsoon', 0.85), ('rainforest', 0.9),
            ('desert', 0.7), ('arid', 0.7),  # Deserts can be hot or cold
        ]
        for pattern, value in temp_patterns:
            if pattern in name_lower:
                temperature = value
                break

        # Special case: cold desert
        if 'cold' in name_lower and 'desert' in name_lower:
            temperature = 0.25

        # Infer precipitation (0 = driest, 1 = wettest)
        # More specific patterns must come before general ones (rainforest before forest)
        precipitation = None
        precip_patterns = [
            ('desert', 0.0), ('arid', 0.1),
            ('steppe', 0.2), ('semi-arid', 0.2), ('dry', 0.25),
            ('savanna', 0.4), ('grassland', 0.5),
            ('woodland', 0.55),
            ('rainforest', 0.95),  # Must come before 'forest'
            ('forest', 0.6),
            ('wet', 0.75), ('monsoon', 0.8),
            ('swamp', 0.9), ('marsh', 0.85), ('bog', 0.85),
            ('jungle', 0.85),
        ]
        for pattern, value in precip_patterns:
            if pattern in name_lower:
                precipitation = value
                break

        # Infer elevation (0 = lowest, 1 = highest)
        elevation = None
        elev_patterns = [
            ('deep', 0.0), ('trench', 0.0),
            ('shallow', 0.25), ('flat', 0.3), ('lowlands', 0.35),
            ('midlands', 0.5), ('plains', 0.45),
            ('highlands', 0.75), ('hills', 0.7), ('mountain', 0.85),
            ('peak', 0.95), ('alpine', 0.9),
        ]
        for pattern, value in elev_patterns:
            if pattern in name_lower:
                elevation = value
                break

        return ClimateContext(
            origin_type=origin_type,
            temperature=temperature,
            precipitation=precipitation,
            elevation=elevation
        )

    def infer_all_contexts(self, biome_ids: Set[str]):
        """
        Infer climate contexts for all given biomes from their names.
        Only sets values that haven't been explicitly set.
        """
        for biome_id in biome_ids:
            inferred = self.infer_climate_from_name(biome_id)
            existing = self.contexts.get(biome_id, ClimateContext())

            # Only use inferred values where existing is None
            if existing.origin_type is None:
                existing.origin_type = inferred.origin_type
            if existing.temperature is None:
                existing.temperature = inferred.temperature
            if existing.precipitation is None:
                existing.precipitation = inferred.precipitation
            if existing.elevation is None:
                existing.elevation = inferred.elevation

            self.contexts[biome_id] = existing


class BiomeDistribution:
    """Tracks probability distribution of biomes with climate context and origin tracking"""

    # Source biomes that are considered "Ocean" origin
    OCEAN_SOURCES = {'ocean', 'deep-ocean', 'shallow-ocean'}
    # Source biomes that are considered "Land" origin
    LAND_SOURCES = {'land', 'coast', 'mesa', 'crater-lake', 'extinct-volcano', 'island', 'vast-forest'}

    def __init__(self):
        self.probabilities: Dict[str, float] = {}
        self.climate: ClimateTracker = ClimateTracker()
        # Track origin weights: biome_id -> {"Land": weight, "Ocean": weight}
        self.origin_weights: Dict[str, Dict[str, float]] = defaultdict(lambda: {"Land": 0.0, "Ocean": 0.0})

    def set(self, biome: str, prob: float):
        """Set probability for a biome"""
        self.probabilities[biome] = prob

    def get(self, biome: str) -> float:
        """Get probability for a biome"""
        return self.probabilities.get(biome, 0.0)

    def remove(self, biome: str):
        """Remove a biome from distribution"""
        if biome in self.probabilities:
            del self.probabilities[biome]

    def add(self, biome: str, prob: float):
        """Add probability to a biome (accumulate)"""
        self.probabilities[biome] = self.get(biome) + prob

    def set_origin(self, biome: str, origin: str, weight: float = 1.0):
        """Set origin weight for a biome"""
        if origin in ("Land", "Ocean"):
            self.origin_weights[biome][origin] += weight

    def add_origin_from(self, to_biome: str, from_biome: str, weight: float):
        """Propagate origin from one biome to another with given weight"""
        if from_biome in self.origin_weights:
            for origin, orig_weight in self.origin_weights[from_biome].items():
                if orig_weight > 0:
                    # Propagate proportionally
                    self.origin_weights[to_biome][origin] += weight * orig_weight

    def get_origin(self, biome: str) -> Optional[str]:
        """Get the majority origin for a biome based on accumulated weights"""
        if biome not in self.origin_weights:
            return None
        weights = self.origin_weights[biome]
        land_weight = weights.get("Land", 0.0)
        ocean_weight = weights.get("Ocean", 0.0)
        if land_weight == 0 and ocean_weight == 0:
            return None
        return "Land" if land_weight >= ocean_weight else "Ocean"

    def normalize(self):
        """Normalize probabilities to sum to 1.0"""
        total = sum(self.probabilities.values())
        if total > 0:
            for biome in self.probabilities:
                self.probabilities[biome] /= total

    def copy(self):
        """Create a copy of this distribution"""
        new_dist = BiomeDistribution()
        new_dist.probabilities = self.probabilities.copy()
        new_dist.climate = self.climate.copy()
        # Deep copy origin weights
        for biome, weights in self.origin_weights.items():
            new_dist.origin_weights[biome] = weights.copy()
        return new_dist

    def get_top_biomes(self, n: int = 20) -> List[Tuple[str, float]]:
        """Get top N biomes by probability"""
        return sorted(self.probabilities.items(), key=lambda x: x[1], reverse=True)[:n]

    def __str__(self):
        top_10 = self.get_top_biomes(10)
        return "\n".join([f"  {biome}: {prob:.4%}" for biome, prob in top_10])


class StageProcessor:
    """Processes Terra pipeline stages"""

    @staticmethod
    def parse_weighted_list(yaml_list: List) -> Dict[str, int]:
        """Parse a weighted biome list from YAML"""
        weights = {}

        for item in yaml_list:
            if isinstance(item, dict):
                for biome, weight in item.items():
                    if isinstance(weight, (int, float)):
                        weights[biome] = int(weight)
                    else:
                        # Weight might be an anchor/alias
                        weights[biome] = 1

        return weights

    @staticmethod
    def process_replace_list(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a REPLACE_LIST stage

        Tag matching: Both 'default-from' and the keys in 'to' section can be tags.
        A biome matches if its ID equals the identifier OR it has the identifier as a tag.
        """
        new_dist = BiomeDistribution()

        # Get default-from and default-to
        default_from = stage.get('default-from')
        default_to = stage.get('default-to', [])

        # Parse default weights
        default_weights = StageProcessor.parse_weighted_list(default_to)
        total_default_weight = sum(default_weights.values())

        # Get transformation mapping
        to_section = stage.get('to', {})

        # Helper to add biome with origin propagation
        def add_with_origin(to_biome: str, from_biome: str, prob: float):
            if to_biome == 'SELF':
                new_dist.add(from_biome, prob)
                new_dist.add_origin_from(from_biome, from_biome, prob)
            else:
                new_dist.add(to_biome, prob)
                new_dist.add_origin_from(to_biome, from_biome, prob)

        # Copy origin weights from source distribution for reference
        for biome, weights in distribution.origin_weights.items():
            for origin, weight in weights.items():
                if weight > 0:
                    new_dist.origin_weights[biome][origin] = weight

        # Process each biome in current distribution
        for from_biome, from_prob in list(distribution.probabilities.items()):
            matched = False

            # Check if there's a specific transformation for this biome
            # Check both direct ID match AND tag matches for each key in to_section
            for to_key, to_list in to_section.items():
                if BiomeReader.matches_biome_or_tag(to_key, from_biome):
                    matched = True
                    # Handle shorthand (single biome) vs list
                    if isinstance(to_list, str):
                        # Shorthand: direct replacement
                        add_with_origin(to_list, from_biome, from_prob)
                    elif isinstance(to_list, list):
                        # Weighted list
                        to_weights = StageProcessor.parse_weighted_list(to_list)
                        total_weight = sum(to_weights.values())

                        if total_weight > 0:
                            for to_biome, weight in to_weights.items():
                                prob = from_prob * (weight / total_weight)
                                add_with_origin(to_biome, from_biome, prob)
                    break  # Only apply one transformation per biome

            # If no specific match, check default-from (also using tag matching)
            if not matched and default_from and BiomeReader.matches_biome_or_tag(default_from, from_biome):
                matched = True
                if total_default_weight > 0:
                    # Apply default transformation
                    for to_biome, weight in default_weights.items():
                        prob = from_prob * (weight / total_default_weight)
                        add_with_origin(to_biome, from_biome, prob)

            if not matched:
                # No transformation, pass through
                # But never pass through literal "SELF"
                if from_biome != 'SELF':
                    new_dist.add(from_biome, from_prob)
                    # Preserve origin for pass-through biomes
                    new_dist.add_origin_from(from_biome, from_biome, from_prob)

        return new_dist

    @staticmethod
    def process_replace(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a simple REPLACE stage

        Based on Terra source code (ReplaceStage.java):
        - The 'from' field matches biomes by tag/ID
        - ALL matching biomes are replaced (100%, not partial)
        - The 'sampler' determines WHICH biome from 'to' is selected at each location
        - The 'to' weights determine proportional distribution (modified by sampler spatial pattern)

        Tag matching: If 'from' is a tag (e.g., LAND_CAVES), all biomes with that tag
        in the distribution are replaced.
        """
        new_dist = distribution.copy()

        from_identifier = stage.get('from')
        to_spec = stage.get('to')

        if not from_identifier:
            return new_dist

        # Find all biomes in the distribution that match the 'from' identifier
        # This includes direct ID matches AND biomes with the identifier as a tag
        matching_biomes = []
        for biome_id in list(new_dist.probabilities.keys()):
            if BiomeReader.matches_biome_or_tag(from_identifier, biome_id):
                matching_biomes.append(biome_id)

        # Process each matching biome
        for matched_biome in matching_biomes:
            from_prob = new_dist.get(matched_biome)
            if from_prob <= 0:
                continue

            # Remove the matched biome from distribution
            new_dist.remove(matched_biome)

            # Helper to add biome with origin propagation
            def add_with_origin(to_biome: str, prob: float):
                if to_biome == 'SELF':
                    new_dist.add(matched_biome, prob)
                    new_dist.add_origin_from(matched_biome, matched_biome, prob)
                else:
                    new_dist.add(to_biome, prob)
                    new_dist.add_origin_from(to_biome, matched_biome, prob)

            # Distribute the probability according to 'to' weights
            # The sampler creates spatial variation in which biome appears where,
            # but for statistical purposes, the weights determine average distribution
            if isinstance(to_spec, str):
                add_with_origin(to_spec, from_prob)
            elif isinstance(to_spec, list):
                to_weights = StageProcessor.parse_weighted_list(to_spec)
                total_weight = sum(to_weights.values())
                if total_weight > 0:
                    for to_biome, weight in to_weights.items():
                        prob = from_prob * (weight / total_weight)
                        add_with_origin(to_biome, prob)
            elif isinstance(to_spec, dict):
                # Dict format
                to_weights = {}
                for k, v in to_spec.items():
                    if isinstance(v, (int, float)):
                        to_weights[k] = v
                total_weight = sum(to_weights.values())
                if total_weight > 0:
                    for to_biome, weight in to_weights.items():
                        prob = from_prob * (weight / total_weight)
                        add_with_origin(to_biome, prob)

        return new_dist

    @staticmethod
    def process_border(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a BORDER stage

        BORDER stages find borders between two biomes and create a third biome at the boundary.
        For probability calculation, we approximate this by:
        - Taking a percentage of the 'replace' biome's probability
        - Converting it to the 'to' biome(s)
        - The percentage is proportional to the 'from' biome's probability (more 'from' = more borders)

        Tag matching: Both 'from' and 'replace' can be tags that match multiple biomes.
        The 'to' field can be a single biome or a weighted list.
        """
        new_dist = distribution.copy()

        from_identifier = stage.get('from')
        replace_identifier = stage.get('replace')
        to_spec = stage.get('to')

        if not from_identifier or not replace_identifier or not to_spec:
            return distribution

        # Parse the 'to' specification - can be string or weighted list
        if isinstance(to_spec, str):
            to_weights = {to_spec: 1}
        elif isinstance(to_spec, list):
            to_weights = StageProcessor.parse_weighted_list(to_spec)
        elif isinstance(to_spec, dict):
            to_weights = {k: v for k, v in to_spec.items() if isinstance(v, (int, float))}
        else:
            return distribution

        total_to_weight = sum(to_weights.values())
        if total_to_weight <= 0:
            return distribution

        # Find all biomes that match the 'from' identifier (for calculating border probability)
        from_total_prob = 0.0
        for biome_id in new_dist.probabilities.keys():
            if BiomeReader.matches_biome_or_tag(from_identifier, biome_id):
                from_total_prob += new_dist.get(biome_id)

        if from_total_prob <= 0:
            # No 'from' biomes exist, no borders possible
            return new_dist

        # Find all biomes that match the 'replace' identifier
        replace_biomes = []
        for biome_id in list(new_dist.probabilities.keys()):
            if BiomeReader.matches_biome_or_tag(replace_identifier, biome_id):
                replace_biomes.append(biome_id)

        if not replace_biomes:
            # No 'replace' biomes exist, no borders possible
            return new_dist

        # Process each matching replace biome
        for replace_biome in replace_biomes:
            replace_prob = new_dist.get(replace_biome)
            if replace_prob <= 0:
                continue

            # Border fraction: estimate how much of replace_biome gets converted to to_biome
            # This is proportional to both the from_biome and replace_biome probabilities
            # We use a conservative estimate: convert up to 20% of the replace biome
            border_factor = min(0.20, from_total_prob * 0.4)  # Max 20% conversion
            border_prob = replace_prob * border_factor

            # Transfer probability from replace_biome to to_biome(s)
            new_dist.probabilities[replace_biome] = replace_prob - border_prob

            # Distribute border_prob according to to_weights
            for to_biome, weight in to_weights.items():
                prob = border_prob * (weight / total_to_weight)
                if to_biome == 'SELF':
                    new_dist.add(replace_biome, prob)
                else:
                    new_dist.add(to_biome, prob)

        return new_dist

    @staticmethod
    def process_stage(stage_config: Any, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process any stage type"""
        if not isinstance(stage_config, dict):
            return distribution

        stage_type = stage_config.get('type')

        if stage_type == 'REPLACE_LIST':
            return StageProcessor.process_replace_list(stage_config, distribution)
        elif stage_type == 'REPLACE':
            return StageProcessor.process_replace(stage_config, distribution)
        elif stage_type == 'BORDER':
            return StageProcessor.process_border(stage_config, distribution)
        else:
            # EXPAND, SMOOTH, etc. don't affect probabilities
            return distribution


class ExtrusionDistribution:
    """
    Tracks extrusion biome distributions.

    Extrusions are underground biome replacements that happen at specific Y-ranges.
    They don't replace surface biome percentages - instead they occupy additional
    underground space, derived from the surface biomes above them.
    """

    def __init__(self):
        # Maps biome_id -> (parent_biome_or_ALL, weight_fraction, source_file)
        self.extrusion_biomes: Dict[str, List[Tuple[str, float, str]]] = defaultdict(list)

    def add_extrusion_biome(self, biome_id: str, parent: str, weight_fraction: float, source_file: str):
        """
        Add an extrusion biome.

        Args:
            biome_id: The cave/underground biome being added
            parent: The parent biome (or 'ALL' if applies to all)
            weight_fraction: The fraction of the parent space this biome occupies
            source_file: The extrusion file this came from
        """
        self.extrusion_biomes[biome_id].append((parent, weight_fraction, source_file))

    def get_extrusion_biomes(self) -> Set[str]:
        """Get all biomes that come from extrusions"""
        return set(self.extrusion_biomes.keys())

    def calculate_percentage(self, biome_id: str, surface_distribution: BiomeDistribution) -> float:
        """
        Calculate the effective percentage for an extrusion biome.

        For 'ALL' parent: percentage = weight_fraction (applies uniformly)
        For specific parent/tag: percentage = sum(matching_biome_pcts) * weight_fraction

        Tag matching: If parent is a tag (e.g., LAND_CAVES), we sum the probabilities
        of all surface biomes that have that tag.
        """
        if biome_id not in self.extrusion_biomes:
            return 0.0

        total_pct = 0.0
        for parent_identifier, weight_fraction, _ in self.extrusion_biomes[biome_id]:
            if parent_identifier == 'ALL':
                # Applies to all surface biomes - use the weight fraction directly
                # This represents the fraction of underground space
                total_pct += weight_fraction
            else:
                # Find all biomes in the surface distribution that match the parent identifier
                # This includes direct ID matches AND biomes with the identifier as a tag
                matching_pct = 0.0
                for surface_biome in surface_distribution.probabilities.keys():
                    if BiomeReader.matches_biome_or_tag(parent_identifier, surface_biome):
                        matching_pct += surface_distribution.get(surface_biome)

                total_pct += matching_pct * weight_fraction

        return total_pct

    def get_source_info(self, biome_id: str) -> str:
        """Get the source file(s) for an extrusion biome"""
        if biome_id not in self.extrusion_biomes:
            return ""
        sources = set(src for _, _, src in self.extrusion_biomes[biome_id])
        return ", ".join(sorted(sources))


class ExtrusionProcessor:
    """Processes extrusion definitions from preset files"""

    @staticmethod
    def parse_extrusion_file(extrusion_path: Path) -> List[Dict]:
        """Load extrusions from a file"""
        try:
            with open(extrusion_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('extrusions', [])
        except Exception as e:
            print(f"Warning: Could not load extrusion file {extrusion_path}: {e}", file=sys.stderr)
            return []

    @staticmethod
    def process_extrusion(extrusion_config: Dict, source_file: str) -> List[Tuple[str, str, float]]:
        """
        Process a single extrusion config.

        Returns list of (biome_id, parent, weight_fraction) tuples.
        """
        results = []

        extrusion_type = extrusion_config.get('type')
        if extrusion_type != 'REPLACE':
            return results

        from_biome = extrusion_config.get('from', '')
        to_spec = extrusion_config.get('to')

        if not to_spec:
            return results

        # Parse the 'to' specification to get weights
        if isinstance(to_spec, str):
            # Single biome replacement
            if to_spec != 'SELF':
                results.append((to_spec, from_biome, 1.0))
        elif isinstance(to_spec, list):
            # Weighted list
            weights = StageProcessor.parse_weighted_list(to_spec)
            total_weight = sum(weights.values())

            if total_weight > 0:
                for biome_id, weight in weights.items():
                    if biome_id != 'SELF':
                        weight_fraction = weight / total_weight
                        results.append((biome_id, from_biome, weight_fraction))
        elif isinstance(to_spec, dict):
            # Dict format
            weights = {}
            for k, v in to_spec.items():
                if isinstance(v, (int, float)):
                    weights[k] = v
            total_weight = sum(weights.values())

            if total_weight > 0:
                for biome_id, weight in weights.items():
                    if biome_id != 'SELF':
                        weight_fraction = weight / total_weight
                        results.append((biome_id, from_biome, weight_fraction))

        return results


class BiomeMetadata:
    """Holds metadata for a biome"""

    def __init__(self, biome_id: str):
        self.biome_id = biome_id
        self.extends: Optional[str] = None
        self.color: Optional[str] = None
        self.percentages: Dict[str, float] = {}  # preset_name -> percentage
        self.extrusion_percentages: Dict[str, float] = {}  # preset_name -> extrusion percentage
        self.is_extrusion: bool = False  # True if this biome only comes from extrusions
        self.extrusion_source: str = ""  # Which extrusion file(s) this comes from
        # Climate attributes (from default preset)
        self.biome_type: Optional[str] = None  # "Land" or "Ocean" (inferred from name)
        self.origin: Optional[str] = None  # "Land" or "Ocean" (derived from pipeline lineage)
        self.temperature: Optional[float] = None  # 0-1 (coldest to hottest)
        self.precipitation: Optional[float] = None  # 0-1 (driest to wettest)
        self.elevation: Optional[float] = None  # 0-1 (lowest to highest)

    def set_climate(self, context: ClimateContext):
        """Set climate attributes from a ClimateContext"""
        self.biome_type = context.origin_type
        self.temperature = context.temperature
        self.precipitation = context.precipitation
        self.elevation = context.elevation

    def set_origin(self, origin: Optional[str]):
        """Set the pipeline-derived origin (Land/Ocean)"""
        self.origin = origin

    @staticmethod
    def format_climate_value(value: Optional[float]) -> str:
        """Format a climate value for CSV output"""
        if value is None:
            return ""
        return f"{value:.4f}"

    def to_csv_row(self, preset_names: List[str], include_extrusion: bool = True) -> List[str]:
        """Convert to CSV row format"""
        row = [
            self.biome_id,
            'extrusion' if self.is_extrusion else 'surface',
            self.origin or "",  # Origin column (derived from pipeline)
            self.biome_type or "",  # Type column (inferred from name)
            self.format_climate_value(self.temperature),  # Temperature column
            self.format_climate_value(self.precipitation),  # Precipitation column
            self.format_climate_value(self.elevation),  # Elevation column
        ]
        # Add percentage columns for each preset
        for preset_name in preset_names:
            if self.is_extrusion:
                # For extrusion-only biomes, show extrusion percentage
                pct = self.extrusion_percentages.get(preset_name, 0.0)
            else:
                # For surface biomes, show surface percentage
                pct = self.percentages.get(preset_name, 0.0)
            row.append(f"{pct:.4%}")
        return row


class BiomeReader:
    """Reads biome files and extracts metadata including tags"""

    _cache: Optional[Dict[str, Path]] = None
    _metadata_cache: Dict[str, BiomeMetadata] = {}
    _valid_biomes: Optional[Set[str]] = None
    _biome_tags: Dict[str, List[str]] = {}  # biome_id -> list of tags
    _tag_index: Dict[str, Set[str]] = {}  # tag -> set of biome_ids with that tag

    @classmethod
    def build_cache(cls, biomes_dir: Path = Path("biomes")):
        """Build cache of all biome files including tags"""
        if cls._cache is not None:
            return

        print(f"Building biome file cache from {biomes_dir}...", file=sys.stderr)
        cls._cache = {}
        cls._valid_biomes = set()
        cls._biome_tags = {}
        cls._tag_index = defaultdict(set)

        for biome_file in biomes_dir.rglob("*.yml"):
            try:
                with open(biome_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and data.get('type') == 'BIOME':
                        biome_id = data.get('id')
                        is_abstract = data.get('abstract', False)
                        if biome_id:
                            cls._cache[biome_id] = biome_file
                            # Only non-abstract biomes are valid for world generation
                            if not is_abstract:
                                cls._valid_biomes.add(biome_id)

                            # Extract tags
                            tags = data.get('tags', [])
                            if isinstance(tags, list):
                                cls._biome_tags[biome_id] = tags
                                # Build reverse index: tag -> biomes
                                for tag in tags:
                                    cls._tag_index[tag].add(biome_id)
            except:
                continue

        # Count unique tags
        unique_tags = set(cls._tag_index.keys())
        biomes_with_tags = sum(1 for tags in cls._biome_tags.values() if tags)

        print(f"Cached {len(cls._cache)} biome files ({len(cls._valid_biomes)} valid, {len(cls._cache) - len(cls._valid_biomes)} abstract)", file=sys.stderr)
        print(f"Found {len(unique_tags)} unique tags across {biomes_with_tags} biomes", file=sys.stderr)

    @classmethod
    def find_biome_file(cls, biome_id: str) -> Optional[Path]:
        """Find the YAML file for a given biome ID"""
        cls.build_cache()
        return cls._cache.get(biome_id)

    @classmethod
    def get_all_valid_biomes(cls) -> Set[str]:
        """Get all valid (non-abstract) biome IDs"""
        cls.build_cache()
        return cls._valid_biomes.copy()

    @classmethod
    def get_biome_tags(cls, biome_id: str) -> List[str]:
        """Get tags for a specific biome"""
        cls.build_cache()
        return cls._biome_tags.get(biome_id, [])

    @classmethod
    def get_biomes_with_tag(cls, tag: str) -> Set[str]:
        """Get all biomes that have a specific tag"""
        cls.build_cache()
        return cls._tag_index.get(tag, set()).copy()

    @classmethod
    def matches_biome_or_tag(cls, identifier: str, biome_id: str) -> bool:
        """
        Check if a biome matches an identifier (either by ID or tag).

        Args:
            identifier: The ID or tag to match against (e.g., 'LAND_CAVES', 'JUNGLE', 'ALL')
            biome_id: The biome ID to check

        Returns:
            True if biome_id equals identifier OR biome_id has identifier as a tag
            Special case: 'ALL' matches every biome
        """
        cls.build_cache()

        # Special case: ALL matches everything
        if identifier == 'ALL':
            return True

        # Direct ID match
        if identifier == biome_id:
            return True

        # Tag match - check if the biome has this tag
        biome_tags = cls._biome_tags.get(biome_id, [])
        return identifier in biome_tags

    @classmethod
    def get_matching_biomes(cls, identifier: str) -> Set[str]:
        """
        Get all biomes that match an identifier (by ID or tag).

        Args:
            identifier: The ID or tag to match (e.g., 'LAND_CAVES', 'ALL')

        Returns:
            Set of biome IDs that match
        """
        cls.build_cache()

        # Special case: ALL matches all valid biomes
        if identifier == 'ALL':
            return cls._valid_biomes.copy()

        matching = set()

        # Direct ID match
        if identifier in cls._valid_biomes:
            matching.add(identifier)

        # Tag match - get all biomes with this tag
        matching.update(cls._tag_index.get(identifier, set()))

        return matching

    @classmethod
    def read_biome_metadata(cls, biome_id: str) -> BiomeMetadata:
        """Read metadata for a biome"""
        # Check metadata cache first
        if biome_id in cls._metadata_cache:
            return cls._metadata_cache[biome_id]

        metadata = BiomeMetadata(biome_id)

        biome_file = cls.find_biome_file(biome_id)
        if not biome_file:
            cls._metadata_cache[biome_id] = metadata
            return metadata

        try:
            with open(biome_file, 'r') as f:
                data = yaml.safe_load(f)
                metadata.extends = data.get('extends')
                metadata.color = data.get('color')
        except Exception as e:
            print(f"Warning: Could not read metadata for {biome_id}: {e}", file=sys.stderr)

        cls._metadata_cache[biome_id] = metadata
        return metadata


class PresetAnalyzer:
    """Analyzes a Terra preset and calculates biome percentages"""

    def __init__(self, preset_path: Path):
        self.preset_path = preset_path
        self.preset_name = preset_path.stem

        # Load preset YAML
        with open(preset_path, 'r') as f:
            self.preset_data = yaml.safe_load(f)

    def get_source_distribution(self) -> BiomeDistribution:
        """Extract initial biome distribution from preset source"""
        dist = BiomeDistribution()

        try:
            biomes_config = self.preset_data.get('biomes', {})
            provider = biomes_config.get('provider', {})
            pipeline = provider.get('pipeline', {})
            source = pipeline.get('source', {})

            # Source might be a string reference or inline config
            if isinstance(source, str):
                print(f"  Source is a reference: {source} (skipping)", file=sys.stderr)
                return dist

            biomes = source.get('biomes', {})

            # Biomes might also be a string reference
            if isinstance(biomes, str):
                print(f"  Biomes is a reference: {biomes} (skipping)", file=sys.stderr)
                return dist

            if not isinstance(biomes, dict):
                print(f"  Unexpected biomes format: {type(biomes)}", file=sys.stderr)
                return dist

            # Parse source biomes and weights
            total_weight = sum(biomes.values())
            if total_weight > 0:
                for biome, weight in biomes.items():
                    prob = weight / total_weight
                    dist.set(biome, prob)

                    # Set origin based on source biome type
                    biome_lower = biome.lower()
                    if biome_lower in BiomeDistribution.OCEAN_SOURCES:
                        dist.set_origin(biome, "Ocean", prob)
                    elif biome_lower in BiomeDistribution.LAND_SOURCES:
                        dist.set_origin(biome, "Land", prob)
                    else:
                        # Default to Land for unknown sources
                        dist.set_origin(biome, "Land", prob)

        except Exception as e:
            print(f"Warning: Could not parse source biomes: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

        return dist

    def get_stage_files(self) -> List[Path]:
        """Extract list of stage files from preset. Also detect PRELIM markers placed in preset files (including comments) and
        insert an inline marker at the corresponding position so the preliminary check runs at the expected point."""
        stage_files = []

        try:
            biomes_config = self.preset_data.get('biomes', {})
            provider = biomes_config.get('provider', {})
            pipeline = provider.get('pipeline', {})
            stages = pipeline.get('stages', [])

            for stage in stages:
                if isinstance(stage, str):
                    # Include reference: << file.yml:stages
                    match = re.match(r'<<\s+([^:]+\.yml):stages', stage)
                    if match:
                        stage_file = Path(match.group(1))
                        stage_files.append(stage_file)
                    # Support plaintext marker in stages list to trigger a preliminary check
                    elif '***PRELIM_CHK_HERE***' in stage:
                        stage_files.append(('INLINE', stage))
                elif isinstance(stage, dict):
                    # Inline stage - we'll process it directly
                    stage_files.append(('INLINE', stage))

            # Detect PRELIM markers that may be present as comments or free text in the preset YAML file
            try:
                preset_lines = []
                with open(self.preset_path, 'r', encoding='utf-8') as pf:
                    preset_lines = pf.readlines()

                # Collect line numbers of stage << references and marker occurrences
                stage_line_indices = []  # list of line indices where << *.yml:stages appears
                for i, line in enumerate(preset_lines):
                    if '<<' in line and ':stages' in line:
                        stage_line_indices.append(i)

                marker_indices = [i for i, line in enumerate(preset_lines) if '***PRELIM_CHK_HERE***' in line]

                # For each marker, determine insertion index in stage_files based on how many stage refs precede it
                for marker_line in marker_indices:
                    insert_pos = sum(1 for idx in stage_line_indices if idx <= marker_line)
                    # Only insert if not already represented (avoid duplicates)
                    # We insert a plain inline marker tuple at the computed position
                    if ('INLINE', '***PRELIM_CHK_HERE***') not in stage_files:
                        stage_files.insert(insert_pos, ('INLINE', '***PRELIM_CHK_HERE***'))
            except Exception:
                # Non-fatal; ignore any errors reading preset file
                pass

        except Exception as e:
            print(f"Warning: Could not parse stages: {e}", file=sys.stderr)

        return stage_files

    def load_stage_file(self, stage_path: Path, record_failure: bool = True) -> List[Dict]:
        """Load stages from a stage file with schema validation"""
        validator = get_validator()

        # Use validator to load and check YAML
        data, yaml_errors = validator.validate_yaml_file(stage_path)

        if yaml_errors:
            for err in yaml_errors:
                validator.errors.append((str(stage_path), "file", err))
            print(f"Warning: Could not load {stage_path}: {yaml_errors[0]}", file=sys.stderr)
            # Record that this stage file failed for this preset
            if record_failure:
                validator.record_failed_stage_load(str(stage_path), self.preset_name)
            return []

        if data is None:
            # Record failure if we couldn't load the file
            if record_failure:
                validator.record_failed_stage_load(str(stage_path), self.preset_name)
            return []

        stages = data.get('stages', [])
        if not isinstance(stages, list):
            return []

        # Validate each stage
        for i, stage in enumerate(stages):
            validator.validate_stage(stage, str(stage_path), i)

        return stages

    def get_extrusion_refs(self) -> List[Tuple[str, Path]]:
        """Extract list of extrusion file references from preset"""
        extrusion_refs = []

        try:
            biomes_config = self.preset_data.get('biomes', {})
            extrusions = biomes_config.get('extrusions', [])

            for extrusion in extrusions:
                if isinstance(extrusion, str):
                    # Include reference: << file.yml:extrusions
                    match = re.match(r'<<\s+([^:]+\.yml):extrusions', extrusion)
                    if match:
                        extrusion_file = Path(match.group(1))
                        extrusion_refs.append((extrusion_file.stem, extrusion_file))

        except Exception as e:
            print(f"Warning: Could not parse extrusions: {e}", file=sys.stderr)

        return extrusion_refs

    def calculate_extrusions(self) -> ExtrusionDistribution:
        """Extract and process extrusion definitions"""
        extrusion_dist = ExtrusionDistribution()

        extrusion_refs = self.get_extrusion_refs()
        if not extrusion_refs:
            return extrusion_dist

        print(f"  Processing {len(extrusion_refs)} extrusion files...")

        for source_name, extrusion_path in extrusion_refs:
            print(f"    - {extrusion_path}")
            extrusions = ExtrusionProcessor.parse_extrusion_file(extrusion_path)

            for extrusion_config in extrusions:
                results = ExtrusionProcessor.process_extrusion(extrusion_config, source_name)
                for biome_id, parent, weight_fraction in results:
                    extrusion_dist.add_extrusion_biome(biome_id, parent, weight_fraction, source_name)

        # Log what we found
        extrusion_biomes = extrusion_dist.get_extrusion_biomes()
        if extrusion_biomes:
            print(f"  Found {len(extrusion_biomes)} extrusion biomes: {sorted(extrusion_biomes)}")

        return extrusion_dist

    def calculate_percentages(self) -> BiomeDistribution:
        """Calculate final biome percentages for this preset"""
        print(f"\nProcessing preset: {self.preset_name}")

        # Get initial distribution
        distribution = self.get_source_distribution()
        print(f"Initial distribution:")
        print(distribution)

        # Get and process stages
        stage_refs = self.get_stage_files()
        detected_biomes = set(distribution.probabilities.keys())

        for i, stage_ref in enumerate(stage_refs):
            if isinstance(stage_ref, tuple) and stage_ref[0] == 'INLINE':
                # Inline stage
                print(f"\nStage {i+1}: INLINE")
                _, stage_config = stage_ref
                
                # Check for preliminary check marker
                if isinstance(stage_config, str) and '***PRELIM_CHK_HERE***' in stage_config:
                    self._check_and_create_placeholder_biomes(detected_biomes)
                    continue
                elif isinstance(stage_config, dict) and stage_config.get('type') == '***PRELIM_CHK_HERE***':
                    self._check_and_create_placeholder_biomes(detected_biomes)
                    continue
                    
                distribution = StageProcessor.process_stage(stage_config, distribution)
                detected_biomes.update(distribution.probabilities.keys())
            else:
                # File reference
                print(f"\nStage {i+1}: {stage_ref}")
                
                # Check if stage file contains preliminary check marker
                if self._has_prelim_check_marker(stage_ref):
                    self._check_and_create_placeholder_biomes(detected_biomes)
                    continue
                    
                stages = self.load_stage_file(stage_ref)

                for stage_config in stages:
                    distribution = StageProcessor.process_stage(stage_config, distribution)
                    detected_biomes.update(distribution.probabilities.keys())

                # Debug: Show distribution after key stages
                if 'temperature.yml' in str(stage_ref) or 'set_biomes_in_climates.yml' in str(stage_ref):
                    print(f"  After {stage_ref.name}:")
                    print(f"    Total biomes: {len(distribution.probabilities)}")
                    print(f"    Top 5: {distribution.get_top_biomes(5)}")

        print(f"\nFinal distribution:")
        print(distribution)

        return distribution

    def _has_prelim_check_marker(self, stage_path: Path) -> bool:
        """Check if stage file contains the preliminary check marker anywhere in the file"""
        try:
            with open(stage_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if '***PRELIM_CHK_HERE***' in line:
                        return True
            return False
        except:
            return False

    def _check_and_create_placeholder_biomes(self, detected_biomes: set):
        """Check detected biomes exist and create placeholders if needed"""
        print(f"\n  Preliminary check: Validating {len(detected_biomes)} detected biomes...")
        
        # Create CSV of preliminary biomes
        csv_path = Path(".scripts") / f"preliminary_biomes_{self.preset_name}.csv"
        csv_path.parent.mkdir(exist_ok=True)
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(['BiomeID', 'Status'])
            for biome_id in sorted(detected_biomes):
                if biome_id == 'SELF':
                    continue
                status = 'EXISTS' if BiomeReader.find_biome_file(biome_id) else 'MISSING'
                writer.writerow([biome_id, status])
        
        print(f"  Created preliminary biomes CSV: {csv_path}")
        
        biomes_dir = Path("biomes")
        placeholder_dir = biomes_dir / "abstract" / "placeholders"
        
        missing_biomes = []
        for biome_id in detected_biomes:
            if biome_id == 'SELF':
                continue
                
            biome_file = BiomeReader.find_biome_file(biome_id)
            if not biome_file:
                missing_biomes.append(biome_id)
        
        if missing_biomes:
            print(f"  Creating {len(missing_biomes)} placeholder biomes...")
            placeholder_dir.mkdir(parents=True, exist_ok=True)
            
            for biome_id in missing_biomes:
                placeholder_path = placeholder_dir / f"{biome_id}.yml"
                
                # Create basic YAML content
                content = f"id: {biome_id}\ntype: BIOME\nabstract: true\n"
                
                # Add tags based on biome ID content
                tags = []
                biome_lower = biome_id.lower()
                if 'island' in biome_lower:
                    tags.append('island')
                if 'coast' in biome_lower:
                    tags.append('coast')
                if 'ocean' in biome_lower:
                    tags.append('ocean')
                
                if tags:
                    content += f"tags:\n"
                    for tag in tags:
                        content += f"  - {tag}\n"
                
                with open(placeholder_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                print(f"    Created: {placeholder_path}")

            # Refresh biome cache so the newly-created placeholder files are discovered
            try:
                BiomeReader._cache = None
                BiomeReader._metadata_cache = {}
                BiomeReader._valid_biomes = None
                BiomeReader._biome_tags = {}
                BiomeReader._tag_index = {}
                BiomeReader.build_cache()
            except Exception:
                pass
def generate_csv_output(
    results: Dict[str, BiomeDistribution],
    extrusion_results: Dict[str, ExtrusionDistribution],
    output_path: Path,
    default_preset: str = "origen2"
):
    """
    Generate BiomeTable.csv with percentages and climate data.

    The table now includes:
    - Source column: 'surface' for regular biomes, 'extrusion' for underground biomes
    - Type column: 'Land' or 'Ocean' based on biome origin
    - Temperature column: normalized temperature value (0=coldest, 1=hottest)
    - Precipitation column: normalized precipitation value (0=driest, 1=wettest)
    - Elevation column: normalized elevation value (0=lowest, 1=highest)
    - Percentages: surface biomes sum to 100%, extrusion biomes shown separately

    Climate data is derived from the default preset specified in pack.yml.
    """
    print(f"\nGenerating CSV output: {output_path}")

    # Get all valid biomes from file system (non-abstract biomes)
    valid_biomes = BiomeReader.get_all_valid_biomes()
    print(f"Valid biomes found in files: {len(valid_biomes)}")

    # Collect all biomes referenced in distributions (surface)
    surface_biomes = set()
    for distribution in results.values():
        surface_biomes.update(distribution.probabilities.keys())

    print(f"Biomes found in surface distributions: {len(surface_biomes)}")

    # Collect all biomes referenced in extrusions
    extrusion_biomes_set = set()
    for extrusion_dist in extrusion_results.values():
        extrusion_biomes_set.update(extrusion_dist.get_extrusion_biomes())

    print(f"Biomes found in extrusions: {len(extrusion_biomes_set)}")

    # Determine which biomes are extrusion-only (not in surface distributions)
    extrusion_only_biomes = extrusion_biomes_set - surface_biomes
    print(f"Extrusion-only biomes: {len(extrusion_only_biomes)}")
    if extrusion_only_biomes:
        print(f"  {sorted(extrusion_only_biomes)}")

    # Combine all sets - we want all valid biomes plus any referenced
    all_biomes = valid_biomes | surface_biomes | extrusion_biomes_set

    print(f"Total biomes to include in table: {len(all_biomes)}")

    # Identify unresolved intermediate biomes
    # An intermediate biome is one that appears in distributions but is NOT a valid biome
    unresolved_biomes = set()
    for biome_id in surface_biomes:
        # A biome is intermediate/unresolved if:
        # 1. It's not in the valid biomes set (no valid biome file exists)
        # 2. It's not 'SELF' (which is a special keyword, not a biome)
        if biome_id not in valid_biomes and biome_id != 'SELF':
            unresolved_biomes.add(biome_id)
            print(f"  Warning: Unresolved intermediate biome: {biome_id}", file=sys.stderr)

    # Read metadata for each biome
    biome_metadata_map = {}
    for biome_id in sorted(all_biomes):
        # For unresolved biomes, rename them to make it clear they're not final biomes
        display_id = biome_id
        if biome_id in unresolved_biomes:
            # Convert intermediate names like "_desert" to "UNLINKED_desert"
            if biome_id.startswith('_'):
                display_id = f"UNLINKED{biome_id}"  # Keeps the underscore: UNLINKED_desert
            else:
                display_id = f"UNLINKED_{biome_id}"

        metadata = BiomeReader.read_biome_metadata(biome_id)
        metadata.biome_id = display_id  # Use the display ID in output

        # Mark if this is an extrusion-only biome
        if biome_id in extrusion_only_biomes:
            metadata.is_extrusion = True
            # Get the extrusion source from any preset that has it
            for preset_name, extrusion_dist in extrusion_results.items():
                source_info = extrusion_dist.get_source_info(biome_id)
                if source_info:
                    metadata.extrusion_source = source_info
                    break

        # Add percentages from all presets
        for preset_name, distribution in results.items():
            # Surface percentage
            metadata.percentages[preset_name] = distribution.get(biome_id)

            # Extrusion percentage (calculated from parent biomes)
            if preset_name in extrusion_results:
                extrusion_dist = extrusion_results[preset_name]
                extrusion_pct = extrusion_dist.calculate_percentage(biome_id, distribution)
                metadata.extrusion_percentages[preset_name] = extrusion_pct

        # Get origin from default preset (pipeline-derived)
        if default_preset in results:
            origin = results[default_preset].get_origin(biome_id)
            metadata.set_origin(origin)

        biome_metadata_map[display_id] = metadata

    # Get sorted list of preset names
    preset_names = sorted(results.keys())

    # Get climate data from the default preset
    print(f"Using default preset '{default_preset}' for climate data")
    default_distribution = results.get(default_preset)
    if default_distribution:
        # Infer climate for all biomes from their names
        default_distribution.climate.infer_all_contexts(all_biomes)

        # Apply climate data to metadata
        for biome_id, metadata in biome_metadata_map.items():
            # Get the original biome ID (strip UNLINKED prefix if present)
            original_id = biome_id
            if biome_id.startswith('UNLINKED_'):
                original_id = biome_id[9:]  # Remove 'UNLINKED_' prefix
            elif biome_id.startswith('UNLINKED'):
                original_id = biome_id[8:]  # Remove 'UNLINKED' prefix (keeps underscore)

            context = default_distribution.climate.get_context(original_id)
            metadata.set_climate(context)
    else:
        print(f"  Warning: Default preset '{default_preset}' not found, climate data unavailable")

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Header row with origin and climate columns
        header = ['BiomeID', 'Source', 'Origin', 'Type', 'Temperature', 'Precipitation', 'Elevation'] + preset_names
        writer.writerow(header)

        # Data rows
        for biome_id in sorted(biome_metadata_map.keys()):
            metadata = biome_metadata_map[biome_id]
            row = metadata.to_csv_row(preset_names)
            writer.writerow(row)

    print(f"CSV written successfully: {output_path}")
    print(f"  Valid biomes: {len(valid_biomes)}")
    print(f"  Surface biomes: {len(surface_biomes)}")
    print(f"  Extrusion-only biomes: {len(extrusion_only_biomes)}")
    print(f"  Unresolved intermediates: {len(unresolved_biomes)}")


def get_default_preset_from_pack() -> str:
    """
    Read pack.yml to find the default preset name.
    Returns the preset name (e.g., 'origen2') or 'origen2' as fallback.
    """
    pack_path = Path("pack.yml")
    if not pack_path.exists():
        print("  Warning: pack.yml not found, using 'origen2' as default preset", file=sys.stderr)
        return "origen2"

    try:
        with open(pack_path, 'r') as f:
            pack_data = yaml.safe_load(f)

        biomes_ref = pack_data.get('biomes')
        if isinstance(biomes_ref, str):
            # Parse reference like "$biome-distribution/presets/origen2.yml:biomes"
            match = re.match(r'\$biome-distribution/presets/([^.]+)\.yml:biomes', biomes_ref)
            if match:
                return match.group(1)

        print("  Warning: Could not parse biomes reference in pack.yml, using 'origen2'", file=sys.stderr)
        return "origen2"
    except Exception as e:
        print(f"  Warning: Error reading pack.yml: {e}, using 'origen2'", file=sys.stderr)
        return "origen2"


def main():
    """Main entry point"""
    preset_dir = Path("biome-distribution/presets")
    output_file = Path(".scripts/BiomeTable.csv")

    if not preset_dir.exists():
        print(f"Error: Preset directory not found: {preset_dir}", file=sys.stderr)
        sys.exit(1)

    print("Terra Biome Percentage Calculator")
    print("=" * 70)

    # Get default preset from pack.yml
    default_preset = get_default_preset_from_pack()
    print(f"Default preset (from pack.yml): {default_preset}")

    # Analyze each preset
    results = {}
    extrusion_results = {}

    for preset_file in preset_dir.glob("*.yml"):
        try:
            analyzer = PresetAnalyzer(preset_file)
            distribution = analyzer.calculate_percentages()
            results[analyzer.preset_name] = distribution

            # Also extract extrusion data
            extrusion_dist = analyzer.calculate_extrusions()
            extrusion_results[analyzer.preset_name] = extrusion_dist
        except Exception as e:
            print(f"\nError processing {preset_file}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    # Output console summary
    print("\n\n" + "=" * 70)
    print("SUMMARY - Top 20 biomes per preset:")
    print("=" * 70)

    # Get valid biomes for marking unresolved ones
    valid_biomes = BiomeReader.get_all_valid_biomes()

    for preset_name, distribution in results.items():
        print(f"\n{preset_name}:")
        for biome, prob in distribution.get_top_biomes(20):
            marker = " [UNRESOLVED]" if biome not in valid_biomes and biome != 'SELF' else ""
            print(f"  {biome:<40} {prob:>8.4%}{marker}")

    # Output extrusion summary
    print("\n\n" + "=" * 70)
    print("EXTRUSION BIOMES (underground/caves):")
    print("=" * 70)
    print("These biomes generate below the surface via extrusion definitions.")
    print("Percentages represent the fraction of underground space they occupy.")
    print()

    for preset_name in sorted(extrusion_results.keys()):
        extrusion_dist = extrusion_results[preset_name]
        surface_dist = results.get(preset_name)

        if not extrusion_dist.extrusion_biomes:
            continue

        print(f"\n{preset_name}:")
        for biome_id in sorted(extrusion_dist.extrusion_biomes.keys()):
            pct = extrusion_dist.calculate_percentage(biome_id, surface_dist)
            sources = extrusion_dist.get_source_info(biome_id)
            print(f"  {biome_id:<40} {pct:>8.4%}  (from: {sources})")

    # Generate CSV output with extrusion data and climate info
    generate_csv_output(results, extrusion_results, output_file, default_preset)

    # Final summary of unresolved biomes
    print("\n" + "=" * 70)
    print("UNRESOLVED INTERMEDIATE BIOMES:")
    print("=" * 70)
    print("These biomes appear in the distribution but are not final biomes.")
    print("They should be fully resolved through REPLACE stages or removed.")
    print()

    distribution_biomes = set()
    for distribution in results.values():
        distribution_biomes.update(distribution.probabilities.keys())

    unresolved_found = False
    for biome_id in sorted(distribution_biomes):
        # Check if biome is not valid and not the special 'SELF' keyword
        if biome_id not in valid_biomes and biome_id != 'SELF':
            unresolved_found = True
            # Show which presets have this biome
            preset_info = []
            for preset_name, distribution in results.items():
                prob = distribution.get(biome_id)
                if prob > 0:
                    preset_info.append(f"{preset_name}: {prob:.4%}")
            print(f"  {biome_id}: {', '.join(preset_info)}")

    if not unresolved_found:
        print("  None - all biomes properly resolved!")

    # Output schema validation report
    validator = get_validator()
    print(validator.get_report())

    # Return exit code based on validation errors
    if validator.has_errors():
        print("\nValidation completed with errors. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
