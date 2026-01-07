#!/usr/bin/env python3
"""
calculate_biome_percentages.py

Calculates actual biome percentages by tracing through Terra preset pipelines.
Properly handles YAML anchors/aliases and cascading probability calculations.
"""

import yaml
import re
import sys
import csv
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any, Optional

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
        """Process a REPLACE_LIST stage"""
        new_dist = BiomeDistribution()

        # Get default-from and default-to
        default_from = stage.get('default-from')
        default_to = stage.get('default-to', [])

        # Parse default weights
        default_weights = StageProcessor.parse_weighted_list(default_to)
        total_default_weight = sum(default_weights.values())

        # Get transformation mapping
        to_section = stage.get('to', {})

        # Debug
        if len(to_section) > 5:  # Only for large stages like climate
            print(f"      DEBUG: Processing REPLACE_LIST with {len(to_section)} transformations", file=sys.stderr)
            print(f"      DEBUG: Current biomes: {list(distribution.probabilities.keys())[:10]}", file=sys.stderr)
            print(f"      DEBUG: Available transformations: {list(to_section.keys())[:10]}", file=sys.stderr)

        # Process each biome in current distribution
        for from_biome, from_prob in list(distribution.probabilities.items()):
            # Check if there's a specific transformation for this biome
            if from_biome in to_section:
                to_list = to_section[from_biome]

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

            elif from_biome == default_from and total_default_weight > 0:
                # Apply default transformation
                for to_biome, weight in default_weights.items():
                    prob = from_prob * (weight / total_default_weight)
                    new_dist.add(to_biome, prob)

            else:
                # No transformation, pass through
                # But never pass through literal "SELF"
                if from_biome != 'SELF':
                    new_dist.add(from_biome, from_prob)

        return new_dist

    @staticmethod
    def process_replace(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a simple REPLACE stage"""
        new_dist = distribution.copy()

        from_biome = stage.get('from')
        to_spec = stage.get('to')

        if from_biome and from_biome in new_dist.probabilities:
            from_prob = new_dist.get(from_biome)
            new_dist.remove(from_biome)

            # Handle to as string, list, or dict
            if isinstance(to_spec, str):
                if to_spec == 'SELF':
                    new_dist.add(from_biome, from_prob)
                else:
                    new_dist.add(to_spec, from_prob)
            elif isinstance(to_spec, list):
                to_weights = StageProcessor.parse_weighted_list(to_spec)
                total_weight = sum(to_weights.values())
                if total_weight > 0:
                    for to_biome, weight in to_weights.items():
                        prob = from_prob * (weight / total_weight)
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
        else:
            # EXPAND, SMOOTH, etc. don't affect probabilities
            return distribution


class BiomeMetadata:
    """Holds metadata for a biome"""

    def __init__(self, biome_id: str):
        self.biome_id = biome_id
        self.extends: Optional[str] = None
        self.color: Optional[str] = None
        self.percentages: Dict[str, float] = {}  # preset_name -> percentage

    def to_csv_row(self, preset_names: List[str]) -> List[str]:
        """Convert to CSV row format"""
        row = [
            self.biome_id,
            self.extends or '',
            self.color or ''
        ]
        # Add percentage columns for each preset
        for preset_name in preset_names:
            pct = self.percentages.get(preset_name, 0.0)
            row.append(f"{pct:.4%}")
        return row


class BiomeReader:
    """Reads biome files and extracts metadata"""

    _cache: Optional[Dict[str, Path]] = None
    _metadata_cache: Dict[str, BiomeMetadata] = {}

    @classmethod
    def build_cache(cls, biomes_dir: Path = Path("biomes")):
        """Build cache of all biome files"""
        if cls._cache is not None:
            return

        print(f"Building biome file cache from {biomes_dir}...", file=sys.stderr)
        cls._cache = {}

        for biome_file in biomes_dir.rglob("*.yml"):
            try:
                with open(biome_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and data.get('type') == 'BIOME':
                        biome_id = data.get('id')
                        if biome_id:
                            cls._cache[biome_id] = biome_file
            except:
                continue

        print(f"Cached {len(cls._cache)} biome files", file=sys.stderr)

    @classmethod
    def find_biome_file(cls, biome_id: str) -> Optional[Path]:
        """Find the YAML file for a given biome ID"""
        cls.build_cache()
        return cls._cache.get(biome_id)

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


def generate_csv_output(results: Dict[str, BiomeDistribution], output_path: Path):
    """Generate BiomeTable.csv with percentages"""
    print(f"\nGenerating CSV output: {output_path}")

    # Collect all unique biomes
    all_biomes = set()
    for distribution in results.values():
        all_biomes.update(distribution.probabilities.keys())

    print(f"Total biomes found: {len(all_biomes)}")

    # Read metadata for each biome
    biome_metadata_map = {}
    for biome_id in sorted(all_biomes):
        metadata = BiomeReader.read_biome_metadata(biome_id)

        # Add percentages from all presets
        for preset_name, distribution in results.items():
            metadata.percentages[preset_name] = distribution.get(biome_id)

        biome_metadata_map[biome_id] = metadata

    # Get sorted list of preset names
    preset_names = sorted(results.keys())

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Header row
        header = ['BiomeID', 'Extends', 'Color'] + preset_names
        writer.writerow(header)

        # Data rows
        for biome_id in sorted(biome_metadata_map.keys()):
            metadata = biome_metadata_map[biome_id]
            row = metadata.to_csv_row(preset_names)
            writer.writerow(row)

    print(f"CSV written successfully: {output_path}")


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

    for preset_file in preset_dir.glob("*.yml"):
        try:
            analyzer = PresetAnalyzer(preset_file)
            distribution = analyzer.calculate_percentages()
            results[analyzer.preset_name] = distribution
        except Exception as e:
            print(f"\nError processing {preset_file}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    # Output console summary
    print("\n\n" + "=" * 70)
    print("SUMMARY - Top 20 biomes per preset:")
    print("=" * 70)

    for preset_name, distribution in results.items():
        print(f"\n{preset_name}:")
        for biome, prob in distribution.get_top_biomes(20):
            print(f"  {biome:<40} {prob:>8.4%}")

    # Generate CSV output
    generate_csv_output(results, output_file)


if __name__ == "__main__":
    main()
