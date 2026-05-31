#!/usr/bin/env python3
"""
calibrate_border.py
===================

Sweep ``BORDER_SCALE_FACTOR`` × ``BORDER_MAX_FRACTION`` for Terra's BORDER /
BORDER_LIST stage model, score each tuple's predicted biome percentages against
``benchmark_CHIMERA.csv`` (a real in-world sample), and print the best-fit
tuples.

Scoring metrics
---------------
- **Global weighted L1**: Σ |pred − truth| · truth across all benchmark biomes
  (rivers excluded — the benchmark sample was generated without rivers, so
  river-named biomes carry no calibration signal here).
- **Border-biome L1**: same, restricted to coast/beach/shore-named biomes
  produced by BORDER stages other than the river stages.

Usage
-----
    python .scripts/calibrate_border.py
    python .scripts/calibrate_border.py --write-constants

``--write-constants`` patches the winning (scale, max_frac) tuple from the
border-biome metric back into ``calculate_biome_percentages.py``.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent))

import calculate_biome_percentages as cbp
from calculate_biome_percentages import PresetAnalyzer, CLIMATE_PRESET_NAME


BENCHMARK_CSV = Path("benchmark_CHIMERA.csv")
CALCULATOR_PY = Path(__file__).parent / "calculate_biome_percentages.py"

# Sweep grid — refined around the empirical minimum (~0.10 from initial sweep).
SCALE_GRID    = [0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.17, 0.20]
MAX_FRAC_GRID = [0.05, 0.10, 0.15]

# Biomes named with these patterns are TRUE BORDER-stage outputs (from
# add_island_shelf.yml and friends — Terra BORDER / BORDER_LIST stage type
# only).  REPLACE_LIST-driven biomes like BEACH / SNOWDRIFT_COASTS are
# excluded from the border metric because they're insensitive to the
# BORDER_SCALE_FACTOR (their probabilities come from REPLACE_LIST sampler
# math, not the geometric border model).
BORDER_NAME_PATTERNS = re.compile(
    r'(SHALLOW|SHELF|TRENCH)', re.IGNORECASE)

# Biomes named with these patterns are EXCLUDED from all scoring because the
# benchmark sample was generated with rivers disabled (the river sampler is
# being reworked separately, so river predictions can't be calibrated yet).
EXCLUDE_NAME_PATTERNS = re.compile(r'(RIVER|STREAM)', re.IGNORECASE)


def load_benchmark(path: Path) -> Dict[str, float]:
    """Load benchmark biome → Surface % (as 0–100 floats)."""
    truth: Dict[str, float] = {}
    with open(path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            biome = row['Biome']
            try:
                truth[biome] = float(row['Surface %'])
            except (ValueError, KeyError):
                continue
    return truth


def run_calculator(scale: float, max_frac: float) -> Dict[str, float]:
    """
    Run the CHIMERA pipeline under the given border constants.  Returns biome
    id → predicted Surface % (0–100).
    """
    cbp.BORDER_SCALE_FACTOR = scale
    cbp.BORDER_MAX_FRACTION = max_frac

    preset_path = Path("biome-distribution/presets") / f"{CLIMATE_PRESET_NAME}.yml"
    analyzer = PresetAnalyzer(preset_path)
    dist = analyzer.calculate_percentages()
    return {b: p * 100.0 for b, p in dist.probabilities.items()}


def score(pred: Dict[str, float], truth: Dict[str, float],
          biomes_filter=None, exclude=None) -> float:
    """
    Truth-weighted L1: Σ |pred − truth| · truth.

    - ``biomes_filter`` (set): if given, only sum over biomes in this set.
    - ``exclude`` (set): biome names to skip entirely (always applied).
    """
    total = 0.0
    for biome, t in truth.items():
        if exclude is not None and biome in exclude:
            continue
        if biomes_filter is not None and biome not in biomes_filter:
            continue
        p = pred.get(biome, 0.0)
        total += abs(p - t) * t
    return total


def write_constants(scale: float, max_frac: float) -> None:
    """Patch BORDER_SCALE_FACTOR and BORDER_MAX_FRACTION in the calculator."""
    text = CALCULATOR_PY.read_text(encoding='utf-8')
    text = re.sub(r'^BORDER_SCALE_FACTOR\s*=\s*[\d.]+',
                  f'BORDER_SCALE_FACTOR = {scale}', text, count=1, flags=re.MULTILINE)
    text = re.sub(r'^BORDER_MAX_FRACTION\s*=\s*[\d.]+',
                  f'BORDER_MAX_FRACTION = {max_frac}', text, count=1, flags=re.MULTILINE)
    CALCULATOR_PY.write_text(text, encoding='utf-8')
    print(f"Patched {CALCULATOR_PY.name}: "
          f"SCALE={scale}  MAX_FRAC={max_frac}", file=sys.stderr)


def main() -> int:
    if not BENCHMARK_CSV.exists():
        print(f"Error: {BENCHMARK_CSV} not found", file=sys.stderr)
        return 1
    truth = load_benchmark(BENCHMARK_CSV)
    river_biomes  = {b for b in truth if EXCLUDE_NAME_PATTERNS.search(b)}
    border_biomes = {b for b in truth if BORDER_NAME_PATTERNS.search(b)
                                       and b not in river_biomes}
    print(f"Benchmark: {len(truth)} biomes  ({len(border_biomes)} coast/beach, "
          f"{len(river_biomes)} river excluded)", file=sys.stderr)

    # Silence the analyzer's chatty per-stage prints.
    class _NullIO:
        def write(self, _): pass
        def flush(self): pass
    real_stdout = sys.stdout

    results: List[Tuple[float, float, float, float]] = []  # (scale, max_frac, global_L1, border_L1)
    for scale in SCALE_GRID:
        for max_frac in MAX_FRAC_GRID:
            sys.stdout = _NullIO()
            try:
                pred = run_calculator(scale, max_frac)
            finally:
                sys.stdout = real_stdout
            g = score(pred, truth, exclude=river_biomes)
            b = score(pred, truth, biomes_filter=border_biomes,
                      exclude=river_biomes)
            results.append((scale, max_frac, g, b))
            print(f"  scale={scale:.2f}  max={max_frac:.2f}  "
                  f"global_L1={g:.4f}  border_L1={b:.4f}", file=sys.stderr)

    print("\n=== Top 5 by GLOBAL truth-weighted L1 ===", file=sys.stderr)
    for s, m, g, b in sorted(results, key=lambda r: r[2])[:5]:
        print(f"  scale={s:.2f}  max={m:.2f}  global={g:.4f}  border={b:.4f}",
              file=sys.stderr)

    print("\n=== Top 5 by BORDER truth-weighted L1 ===", file=sys.stderr)
    best_border = sorted(results, key=lambda r: r[3])
    for s, m, g, b in best_border[:5]:
        print(f"  scale={s:.2f}  max={m:.2f}  global={g:.4f}  border={b:.4f}",
              file=sys.stderr)

    if '--write-constants' in sys.argv:
        winner = best_border[0]
        write_constants(winner[0], winner[1])

    return 0


if __name__ == '__main__':
    sys.exit(main())
