#!/usr/bin/env python3
"""Debug why ALPINE_ASCENDANCY doesn't appear in origen2"""
from ensure_module import ensure_modules
ensure_modules(["yaml"])

import yaml
from pathlib import Path
from calculate_biome_percentages import PresetAnalyzer, StageProcessor

def trace_biome_chain(preset_name):
    """Trace the climate chain for a preset"""
    print(f"\n{'='*70}")
    print(f"Tracing {preset_name} preset")
    print(f"{'='*70}")

    preset_path = Path(f"biome-distribution/presets/{preset_name}.yml")
    analyzer = PresetAnalyzer(preset_path)

    # Get initial distribution
    distribution = analyzer.get_source_distribution()
    print(f"\nInitial distribution:")
    for biome, prob in sorted(distribution.probabilities.items()):
        print(f"  {biome}: {prob:.2%}")

    # Process stages and track ice-cap/tundra/boreal
    stage_refs = analyzer.get_stage_files()

    for i, stage_ref in enumerate(stage_refs):
        stage_name = str(stage_ref) if isinstance(stage_ref, Path) else "INLINE"

        # Check BEFORE temperature stage
        if 'temperature.yml' in stage_name:
            print(f"\nBEFORE TEMPERATURE stage:")
            print(f"  All biomes:")
            for biome, prob in sorted(distribution.probabilities.items(), key=lambda x: -x[1]):
                if prob > 0.001:
                    print(f"    {biome}: {prob:.4%}")

        # Load and process stages
        if isinstance(stage_ref, tuple):
            _, stage_config = stage_ref
            distribution = StageProcessor.process_stage(stage_config, distribution)
        else:
            stages = analyzer.load_stage_file(stage_ref)
            for stage_config in stages:
                distribution = StageProcessor.process_stage(stage_config, distribution)

        # Check for climate intermediates after key stages
        if 'temperature.yml' in stage_name:
            print(f"\nAfter TEMPERATURE stage:")
            climate_biomes = {b: p for b, p in distribution.probabilities.items()
                            if 'ice-cap' in b or 'tundra' in b or 'boreal' in b}
            if climate_biomes:
                for biome, prob in sorted(climate_biomes.items(), key=lambda x: -x[1])[:10]:
                    print(f"  {biome}: {prob:.4%}")
            else:
                print("  NO ice-cap/tundra/boreal biomes found!")

            # Show top 10 overall
            print(f"\n  Top 10 all biomes:")
            for biome, prob in sorted(distribution.probabilities.items(), key=lambda x: -x[1])[:10]:
                print(f"    {biome}: {prob:.4%}")

        elif 'elevation.yml' in stage_name:
            print(f"\nAfter ELEVATION stage:")
            highland_biomes = {b: p for b, p in distribution.probabilities.items()
                             if 'highland' in b}
            if highland_biomes:
                for biome, prob in sorted(highland_biomes.items(), key=lambda x: -x[1])[:10]:
                    print(f"  {biome}: {prob:.4%}")
            else:
                print("  NO highland biomes found!")

        elif 'set_biomes_in_climates.yml' in stage_name:
            print(f"\nAfter SET_BIOMES_IN_CLIMATES stage:")
            alpine = distribution.get('ALPINE_ASCENDANCY')
            print(f"  ALPINE_ASCENDANCY: {alpine:.4%}")

            # Show what replaced the highlands
            print(f"\n  All final biomes with >0.1%:")
            for biome, prob in sorted(distribution.probabilities.items(), key=lambda x: -x[1]):
                if prob > 0.001:
                    print(f"    {biome}: {prob:.4%}")

if __name__ == "__main__":
    trace_biome_chain("default")
    trace_biome_chain("origen2")
