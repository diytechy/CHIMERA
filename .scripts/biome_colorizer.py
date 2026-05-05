"""Biome colorizer

Reads .artifacts/BiomeTable.csv and generates biomes/colors.generated.yml using
an approximate Munsell-like H/C/V mapping with deterministic jitter.

Usage:
  python .scripts/biome_colorizer.py --input .artifacts/BiomeTable.csv --output biomes/colors.generated.yml --seed 42 --overwrite

Dependencies: only standard library (csv, yaml not required; we'll write simple YAML text)
"""
from __future__ import annotations
import csv
import sys
import argparse
import math
import colorsys
from collections import defaultdict
import hashlib

# Constants (can be tuned)
SNOWY_VALUE_BOUNDARY = 75.0  # percent
VALLEY_VALUE_BOUNDARY = 25.0  # percent
STONY_CHROMA_CUTOFF = 33.0  # percent

# Hue ranges are defined on a 0-100 circular scale (like Munsell hue percentage),
# we map 0..100 -> 0..360 degrees when converting to an RGB HSV color.
REGIONS = {
    'climate': {'h_min': 15.0, 'h_max': 55.0},  # A
    'coastal': {'h_min': 55.0, 'h_max': 62.5},  # B
    'river': {'h_min': 62.5, 'h_max': 70.0},  # C
    'ocean': {'h_min': 70.0, 'h_max': 80.0},  # D
    'crater': {'h_min': 80.0, 'h_max': 85.0},  # E
    'special': {'h_min': 85.0, 'h_max': 95.0},  # F
    'volcano': {'h_min': 95.0, 'h_max': 100.0, 'h_min_wrap': 0.0, 'h_max_wrap': 5.0},  # G (wraps through 0)
    'mesa': {'h_min': 5.0, 'h_max': 15.0},  # H
    'icy_canyon': {'h_min': 55.0, 'h_max': 80.0},  # I
    # central stony and low chroma regions will be handled by chroma cutoff
}


def parse_biome_table(path: str) -> list[dict]:
    rows = []
    with open(path, newline='', encoding='utf-8') as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append(r)
    return rows


def deterministic_random(biome_id: str, seed: int = 0) -> float:
    key = f"{seed}:{biome_id}".encode('utf-8')
    h = hashlib.sha256(key).digest()
    # use first 8 bytes as uint64
    val = int.from_bytes(h[:8], 'big')
    return (val % 10_000_000) / 10_000_000


def clamp(v, a, b):
    return max(a, min(b, v))


def hcv_to_rgb_hex(h_percent: float, c_percent: float, v_percent: float) -> str:
    # Map H 0..100 -> 0..360 degrees
    h_deg = (h_percent % 100.0) * 3.6
    # Convert chroma% to saturation (0..1). This is an approximation: treat C% as S
    s = clamp(c_percent / 100.0, 0.0, 1.0)
    v = clamp(v_percent / 100.0, 0.0, 1.0)
    # colorsys uses H in 0..1
    r, g, b = colorsys.hsv_to_rgb(h_deg / 360.0, s, v)
    ri = int(round(r * 255))
    gi = int(round(g * 255))
    bi = int(round(b * 255))
    return f"0x{ri:02x}{gi:02x}{bi:02x}"


def hcv_to_rgb_float(h_percent: float, c_percent: float, v_percent: float) -> tuple[float, float, float]:
    """Return RGB as floats 0..1 for distance calculations."""
    h_deg = (h_percent % 100.0) * 3.6
    s = clamp(c_percent / 100.0, 0.0, 1.0)
    v = clamp(v_percent / 100.0, 0.0, 1.0)
    return colorsys.hsv_to_rgb(h_deg / 360.0, s, v)


def rgb_distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)


def assign_region(biome: dict) -> str:
    name = biome.get('BiomeID', '').upper()
    btype = biome.get('Type', '').lower()
    source = biome.get('Source', '').lower()
    temp = biome.get('Temperature', '')
    elev = biome.get('Elevation', '')
    precip = biome.get('Precipitation', '')

    if 'mushroom' in name:
        return 'special'
    if 'volcano' in name or 'lava' in name or 'erupt' in name:
        return 'volcano'
    if 'mesa' in name:
        return 'mesa'
    if 'crater' in name:
        return 'crater'
    if 'coast' in name:
        return 'coastal'
    if 'river' in name:
        return 'river'
    if 'ocean' in name or source == 'ocean':
        return 'ocean'
    if btype == 'extrusion':
        return 'cave_or_extrusion'
    # default to climate
    return 'climate'


def map_to_hcv(biome: dict, region: str, seed: int = 0, spread: float = 1.0) -> tuple[float, float, float]:
    # Extract numeric attributes if available
    def to_float(v):
        try:
            return float(v)
        except Exception:
            return None

    temp = to_float(biome.get('Temperature', ''))
    precip = to_float(biome.get('Precipitation', ''))
    elev = to_float(biome.get('Elevation', ''))
    name = biome.get('BiomeID', '')

    rnd = deterministic_random(biome.get('BiomeID', ''), seed)

    if region == 'climate':
        # Snowy check
        if 'SNOW' in name.upper() or (temp is not None and temp < 0.16):
            # A1 snowy value band
            h = (REGIONS['climate']['h_min'] + REGIONS['climate']['h_max']) / 2.0
            c = 10.0 + rnd * 20.0  # low chroma for snow (slightly colored)
            v = SNOWY_VALUE_BOUNDARY + rnd * (100.0 - SNOWY_VALUE_BOUNDARY)
            return h, c, v
        # A2 standard climate: Hue scales with precipitation
        if precip is None:
            precip = 0.5
        h = REGIONS['climate']['h_min'] + (REGIONS['climate']['h_max'] - REGIONS['climate']['h_min']) * clamp(precip, 0.0, 1.0)
        # Chroma decreases with lower temp
        if temp is None:
            temp = 0.5
        # Map temp 0..1 -> chroma range [STONY_CHROMA_CUTOFF..100]
        c = STONY_CHROMA_CUTOFF + (100.0 - STONY_CHROMA_CUTOFF) * clamp(temp, 0.0, 1.0)
        # Value increases with elevation 0..1 -> 25..75
        if elev is None:
            elev_val = 0.5
        else:
            elev_val = clamp(elev, 0.0, 1.0)
        v = VALLEY_VALUE_BOUNDARY + (SNOWY_VALUE_BOUNDARY - VALLEY_VALUE_BOUNDARY) * elev_val
        # Add slight deterministic jitter scaled by spread
        h += (rnd - 0.5) * 4.0 * spread
        c += (rnd - 0.5) * 6.0 * spread
        v += (rnd - 0.5) * 6.0 * spread
        return clamp(h, REGIONS['climate']['h_min'], REGIONS['climate']['h_max']), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    if region == 'coastal' or region == 'river' or region == 'ocean':
        reg = REGIONS['coastal'] if region == 'coastal' else REGIONS['river'] if region == 'river' else REGIONS['ocean']
        # Hue increases with depth/elevation: if elevation is low (ocean), hue higher.
        if elev is None:
            elev = 0.0
        depth_factor = 1.0 - clamp(elev, 0.0, 1.0)
        h = reg['h_min'] + (reg['h_max'] - reg['h_min']) * depth_factor
        # Chroma maps temperature from mid(0.5)->hot(1.0) to 33%..100%
        t = temp if temp is not None else 0.5
        c = STONY_CHROMA_CUTOFF + (100.0 - STONY_CHROMA_CUTOFF) * clamp((t - 0.5) / 0.5, 0.0, 1.0)
        # Value maps temperature from medium (50%) to freeze (100%) according to prompt
        v = 50.0 + (100.0 - 50.0) * clamp((t - 0.5) / 0.5, 0.0, 1.0)
        h += (rnd - 0.5) * 3.0 * spread
        c += (rnd - 0.5) * 5.0 * spread
        v += (rnd - 0.5) * 5.0 * spread
        return clamp(h, reg['h_min'], reg['h_max']), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    if region == 'crater' or region == 'special' or region == 'volcano' or region == 'mesa':
        key = 'volcano' if region == 'volcano' else region
        reg = REGIONS.get(key, REGIONS.get('special'))
        # Use temp/chroma mapping and elevation->value
        t = temp if temp is not None else 0.5
        c = STONY_CHROMA_CUTOFF + (100.0 - STONY_CHROMA_CUTOFF) * clamp(t, 0.0, 1.0)
        if elev is None:
            elev_val = 0.5
        else:
            elev_val = clamp(elev, 0.0, 1.0)
        v = VALLEY_VALUE_BOUNDARY + (100.0 - VALLEY_VALUE_BOUNDARY) * elev_val
        # Hue: pick center of region (handle volcano wrap)
        if key == 'volcano':
            # choose between 95..100 & 0..5 -> wrap
            h = 97.5 if rnd < 0.5 else 2.5
        else:
            h = (reg['h_min'] + reg['h_max']) / 2.0
        h += (rnd - 0.5) * 6.0 * spread
        c += (rnd - 0.5) * 6.0 * spread
        v += (rnd - 0.5) * 6.0 * spread
        return clamp(h, reg['h_min'], reg['h_max']), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    if region == 'cave_or_extrusion':
        # A3: caves/extrusions low value
        # Hue align with elevation (if provided)
        if elev is None:
            elev = 0.0
        h = REGIONS['climate']['h_min'] + (REGIONS['climate']['h_max'] - REGIONS['climate']['h_min']) * clamp(elev, 0.0, 1.0)
        c = STONY_CHROMA_CUTOFF + (50 * clamp(elev, 0.0, 1.0))
        v = clamp((VALLEY_VALUE_BOUNDARY * clamp(1.0 - elev, 0.0, 1.0)) * (0.5 + rnd * 0.5), 0.0, VALLEY_VALUE_BOUNDARY)
        h += (rnd - 0.5) * 10.0 * spread
        c += (rnd - 0.5) * 10.0 * spread
        return clamp(h, 0.0, 100.0), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    # fallback
    return 50.0, 50.0, 50.0


def _region_bounds_for_sampling(region: str, proto_hcv: tuple[float,float,float]) -> tuple[tuple[float,float], tuple[float,float], tuple[float,float]]:
    """Return ((hmin,hmax),(cmin,cmax),(vmin,vmax)) for sampling candidates in a region.
    Uses reasonable constraints derived from prompt and the proto point."""
    h_proto, c_proto, v_proto = proto_hcv
    if region == 'climate':
        return (REGIONS['climate']['h_min'], REGIONS['climate']['h_max']), (STONY_CHROMA_CUTOFF, 100.0), (VALLEY_VALUE_BOUNDARY, SNOWY_VALUE_BOUNDARY)
    if region == 'coastal':
        return (REGIONS['coastal']['h_min'], REGIONS['coastal']['h_max']), (STONY_CHROMA_CUTOFF, 100.0), (50.0, 100.0)
    if region == 'river':
        return (REGIONS['river']['h_min'], REGIONS['river']['h_max']), (STONY_CHROMA_CUTOFF, 100.0), (50.0, 100.0)
    if region == 'ocean':
        return (REGIONS['ocean']['h_min'], REGIONS['ocean']['h_max']), (STONY_CHROMA_CUTOFF, 100.0), (50.0, 100.0)
    if region == 'crater' or region == 'special' or region == 'mesa' or region == 'volcano':
        reg = REGIONS.get('crater') if region == 'crater' else REGIONS.get('special')
        if region == 'volcano':
            # wrap handled when sampling by allowing 0..5 or 95..100
            return (95.0, 105.0), (STONY_CHROMA_CUTOFF, 100.0), (VALLEY_VALUE_BOUNDARY, 100.0)
        return (reg['h_min'], reg['h_max']), (STONY_CHROMA_CUTOFF, 100.0), (VALLEY_VALUE_BOUNDARY, 100.0)
    if region == 'cave_or_extrusion':
        return (REGIONS['climate']['h_min'], REGIONS['climate']['h_max']), (STONY_CHROMA_CUTOFF, 80.0), (0.0, VALLEY_VALUE_BOUNDARY)
    # fallback
    return (0.0, 100.0), (0.0, 100.0), (0.0, 100.0)


def sample_region_candidates(region: str, n_candidates: int, seed: int, proto_points: list[tuple[float,float,float]]) -> list[tuple[float,float,float]]:
    """Generate deterministic candidates within the union of per-biome bounds. proto_points is list of prototypical HCVs for biomes in region."""
    cand = []
    # We'll sample by selecting a proto at random then jittering within its bounds
    for i in range(n_candidates):
        pidx = int((deterministic_random(f"{seed}:{region}:{i}") * len(proto_points)))
        pidx = pidx % len(proto_points)
        proto = proto_points[pidx]
        h_bounds, c_bounds, v_bounds = _region_bounds_for_sampling(region, proto)
        rnd1 = deterministic_random(f"{seed}:cand:h:{i}")
        rnd2 = deterministic_random(f"{seed}:cand:c:{i}")
        rnd3 = deterministic_random(f"{seed}:cand:v:{i}")
        # For volcano wrap handling, map >100 back into 0..100 via modulo
        h = h_bounds[0] + (h_bounds[1] - h_bounds[0]) * rnd1
        c = c_bounds[0] + (c_bounds[1] - c_bounds[0]) * rnd2
        v = v_bounds[0] + (v_bounds[1] - v_bounds[0]) * rnd3
        # Normalize hue into 0..100
        h = h % 100.0
        cand.append((h, c, v))
    return cand


def farthest_point_selection(candidates: list[tuple[float,float,float]], k: int, seed: int) -> list[tuple[float,float,float]]:
    """Select k points from candidates maximizing min pairwise RGB distance using greedy farthest-first traversal."""
    if k <= 0:
        return []
    # Precompute RGB floats
    cand_rgb = [hcv_to_rgb_float(h,c,v) for (h,c,v) in candidates]
    chosen = []
    chosen_idx = []
    # Choose initial index deterministically (use seed-based choice)
    idx0 = int(deterministic_random(f"{seed}:init") * len(candidates)) % len(candidates)
    chosen_idx.append(idx0)
    chosen.append(candidates[idx0])
    while len(chosen) < k:
        best_idx = None
        best_dist = -1.0
        for i, rgb in enumerate(cand_rgb):
            if i in chosen_idx:
                continue
            # distance to nearest chosen
            dmin = min(rgb_distance(rgb, hcv_to_rgb_float(*candidates[j])) for j in chosen_idx)
            if dmin > best_dist:
                best_dist = dmin
                best_idx = i
        if best_idx is None:
            break
        chosen_idx.append(best_idx)
        chosen.append(candidates[best_idx])
    return chosen


def optimize_mapping(mapping: dict, seed: int = 0, samples_per_biome: int = 16) -> dict:
    """Return a new mapping with colors adjusted to maximize spacing per region."""
    # Group biomes by region
    by_region = {}
    for bid, v in mapping.items():
        reg = v['region']
        by_region.setdefault(reg, []).append((bid, v))

    newmap = mapping.copy()
    for reg, items in by_region.items():
        n = len(items)
        if n <= 1:
            continue
        proto_points = [item[1]['hcv'] for item in items]
        candidates = sample_region_candidates(reg, max(100, samples_per_biome * n), seed, proto_points)
        chosen = farthest_point_selection(candidates, n, seed)
        # Assign chosen points to biomes by nearest to original proto hcv
        assigned = {}
        remaining = chosen.copy()
        for bid, info in sorted(items, key=lambda x: x[0]):
            # find nearest remaining chosen point to original hcv
            distances = [rgb_distance(hcv_to_rgb_float(*info['hcv']), hcv_to_rgb_float(*c)) for c in remaining]
            idx = int(min(range(len(distances)), key=lambda i: distances[i]))
            pick = remaining.pop(idx)
            assigned[bid] = pick
        # Update mapping
        for bid, pick in assigned.items():
            h,c,v = pick
            hexcol = hcv_to_rgb_hex(h,c,v)
            newmap[bid] = {'hex': hexcol, 'hcv': (h,c,v), 'region': reg}
    return newmap


def generate_colors(rows: list[dict], seed: int = 0, spread: float = 1.0) -> dict:
    mapping = {}
    # First assign regions and hcv
    for r in rows:
        bid = r.get('BiomeID')
        region = assign_region(r)
        h, c, v = map_to_hcv(r, region, seed=seed, spread=spread)
        hexcol = hcv_to_rgb_hex(h, c, v)
        mapping[bid] = {'hex': hexcol, 'hcv': (h, c, v), 'region': region}
    return mapping


def write_yaml(mapping: dict, out_path: str):
    # Write simple flattened YAML with comment
    lines = []
    lines.append('# Generated by .scripts/biome_colorizer.py\n')
    # Preserve sections by region ordering for readability
    for biome in sorted(mapping.keys()):
        lines.append(f"{biome}: {mapping[biome]['hex']}")
    text = '\n'.join(lines) + '\n'
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write(text)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', default='.artifacts/BiomeTable.csv')
    p.add_argument('--output', default='biomes/colors.generated.yml')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--overwrite', action='store_true')
    p.add_argument('--spread', type=float, default=1.0, help='Multiplier to increase deterministic jitter for color spreading')
    p.add_argument('--optimize', action='store_true', help='Run max-min spacing optimization per region to reduce color collisions')
    p.add_argument('--samples-per-biome', type=int, default=16, help='Number of candidate samples per biome to generate when optimizing')
    args = p.parse_args()

    rows = parse_biome_table(args.input)
    mapping = generate_colors(rows, seed=args.seed, spread=args.spread)
    if args.optimize:
        print('Optimizing colors with max-min sampling...')
        mapping = optimize_mapping(mapping, seed=args.seed, samples_per_biome=args.samples_per_biome)
    write_yaml(mapping, args.output)
    print(f'Wrote {len(mapping)} biome colors to {args.output}')


if __name__ == '__main__':
    main()
