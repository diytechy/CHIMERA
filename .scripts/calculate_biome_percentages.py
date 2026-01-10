#!/usr/bin/env python3
"""
calculate_biome_percentages.py

Calculates actual biome percentages by tracing through Terra preset pipelines.
Properly handles YAML anchors/aliases and cascading probability calculations.

Now also handles extrusion biomes (caves, underground biomes) which generate
content below the surface level. Extrusion biomes are tracked separately so
surface biomes still add to 100%.
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
from typing import Dict, List, Tuple, Any, Optional, Set

class BiomeDistribution:
    """Tracks probability distribution of biomes"""

    def __init__(self):
        self.probabilities: Dict[str, float] = {}

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
                        if to_list == 'SELF':
                            new_dist.add(from_biome, from_prob)
                        else:
                            new_dist.add(to_list, from_prob)
                    elif isinstance(to_list, list):
                        # Weighted list
                        to_weights = StageProcessor.parse_weighted_list(to_list)
                        total_weight = sum(to_weights.values())

                        if total_weight > 0:
                            for to_biome, weight in to_weights.items():
                                prob = from_prob * (weight / total_weight)
                                if to_biome == 'SELF':
                                    # SELF means keep the original biome
                                    new_dist.add(from_biome, prob)
                                else:
                                    new_dist.add(to_biome, prob)
                    break  # Only apply one transformation per biome

            # If no specific match, check default-from (also using tag matching)
            if not matched and default_from and BiomeReader.matches_biome_or_tag(default_from, from_biome):
                matched = True
                if total_default_weight > 0:
                    # Apply default transformation
                    for to_biome, weight in default_weights.items():
                        prob = from_prob * (weight / total_default_weight)
                        if to_biome == 'SELF':
                            new_dist.add(from_biome, prob)
                        else:
                            new_dist.add(to_biome, prob)

            if not matched:
                # No transformation, pass through
                # But never pass through literal "SELF"
                if from_biome != 'SELF':
                    new_dist.add(from_biome, from_prob)

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

            # Distribute the probability according to 'to' weights
            # The sampler creates spatial variation in which biome appears where,
            # but for statistical purposes, the weights determine average distribution
            if isinstance(to_spec, str):
                if to_spec == 'SELF':
                    new_dist.add(matched_biome, from_prob)
                else:
                    new_dist.add(to_spec, from_prob)
            elif isinstance(to_spec, list):
                to_weights = StageProcessor.parse_weighted_list(to_spec)
                total_weight = sum(to_weights.values())
                if total_weight > 0:
                    for to_biome, weight in to_weights.items():
                        prob = from_prob * (weight / total_weight)
                        if to_biome == 'SELF':
                            # SELF means keep the original biome
                            new_dist.add(matched_biome, prob)
                        else:
                            new_dist.add(to_biome, prob)
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
                        if to_biome == 'SELF':
                            # SELF means keep the original biome
                            new_dist.add(matched_biome, prob)
                        else:
                            new_dist.add(to_biome, prob)

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

    def to_csv_row(self, preset_names: List[str], include_extrusion: bool = True) -> List[str]:
        """Convert to CSV row format"""
        row = [
            self.biome_id,
            self.extends or '',
            self.color or '',
            'extrusion' if self.is_extrusion else 'surface',
            self.extrusion_source if self.is_extrusion else ''
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
                    dist.set(biome, weight / total_weight)

        except Exception as e:
            print(f"Warning: Could not parse source biomes: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

        return dist

    def get_stage_files(self) -> List[Path]:
        """Extract list of stage files from preset"""
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
                elif isinstance(stage, dict):
                    # Inline stage - we'll process it directly
                    stage_files.append(('INLINE', stage))

        except Exception as e:
            print(f"Warning: Could not parse stages: {e}", file=sys.stderr)

        return stage_files

    def load_stage_file(self, stage_path: Path) -> List[Dict]:
        """Load stages from a stage file"""
        try:
            with open(stage_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('stages', [])
        except Exception as e:
            print(f"Warning: Could not load {stage_path}: {e}", file=sys.stderr)
            return []

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

        for i, stage_ref in enumerate(stage_refs):
            if isinstance(stage_ref, tuple) and stage_ref[0] == 'INLINE':
                # Inline stage
                print(f"\nStage {i+1}: INLINE")
                _, stage_config = stage_ref
                distribution = StageProcessor.process_stage(stage_config, distribution)
            else:
                # File reference
                print(f"\nStage {i+1}: {stage_ref}")
                stages = self.load_stage_file(stage_ref)

                for stage_config in stages:
                    distribution = StageProcessor.process_stage(stage_config, distribution)

                # Debug: Show distribution after key stages
                if 'temperature.yml' in str(stage_ref) or 'set_biomes_in_climates.yml' in str(stage_ref):
                    print(f"  After {stage_ref.name}:")
                    print(f"    Total biomes: {len(distribution.probabilities)}")
                    print(f"    Top 5: {distribution.get_top_biomes(5)}")

        print(f"\nFinal distribution:")
        print(distribution)

        return distribution


def generate_csv_output(
    results: Dict[str, BiomeDistribution],
    extrusion_results: Dict[str, ExtrusionDistribution],
    output_path: Path
):
    """
    Generate BiomeTable.csv with percentages.

    The table now includes:
    - Source column: 'surface' for regular biomes, 'extrusion' for underground biomes
    - ExtrusionSource column: which extrusion file(s) the biome comes from
    - Percentages: surface biomes sum to 100%, extrusion biomes shown separately
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

        biome_metadata_map[display_id] = metadata

    # Get sorted list of preset names
    preset_names = sorted(results.keys())

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Header row - now includes Source and ExtrusionSource columns
        header = ['BiomeID', 'Extends', 'Color', 'Source', 'ExtrusionSource'] + preset_names
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


def main():
    """Main entry point"""
    preset_dir = Path("biome-distribution/presets")
    output_file = Path(".scripts/BiomeTable.csv")

    if not preset_dir.exists():
        print(f"Error: Preset directory not found: {preset_dir}", file=sys.stderr)
        sys.exit(1)

    print("Terra Biome Percentage Calculator")
    print("=" * 70)

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

    # Generate CSV output with extrusion data
    generate_csv_output(results, extrusion_results, output_file)

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


if __name__ == "__main__":
    main()
