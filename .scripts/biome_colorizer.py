"""Biome colorizer

Reads .scripts/BiomeTable.csv and generates biomes/colors.generated.yml using
an approximate Munsell-like H/C/V mapping with deterministic jitter.

Usage:
  python .scripts/biome_colorizer.py --input .scripts/BiomeTable.csv --output biomes/colors.generated.yml --seed 42 --overwrite

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


def map_to_hcv(biome: dict, region: str, seed: int = 0) -> tuple[float, float, float]:
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
        # Add slight deterministic jitter
        h += (rnd - 0.5) * 4.0
        c += (rnd - 0.5) * 6.0
        v += (rnd - 0.5) * 6.0
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
        h += (rnd - 0.5) * 3.0
        c += (rnd - 0.5) * 5.0
        v += (rnd - 0.5) * 5.0
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
        h += (rnd - 0.5) * 6.0
        c += (rnd - 0.5) * 6.0
        v += (rnd - 0.5) * 6.0
        return clamp(h, reg['h_min'], reg['h_max']), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    if region == 'cave_or_extrusion':
        # A3: caves/extrusions low value
        # Hue align with elevation (if provided)
        if elev is None:
            elev = 0.0
        h = REGIONS['climate']['h_min'] + (REGIONS['climate']['h_max'] - REGIONS['climate']['h_min']) * clamp(elev, 0.0, 1.0)
        c = STONY_CHROMA_CUTOFF + (50 * clamp(elev, 0.0, 1.0))
        v = clamp((VALLEY_VALUE_BOUNDARY * clamp(1.0 - elev, 0.0, 1.0)) * (0.5 + rnd * 0.5), 0.0, VALLEY_VALUE_BOUNDARY)
        h += (rnd - 0.5) * 10.0
        c += (rnd - 0.5) * 10.0
        return clamp(h, 0.0, 100.0), clamp(c, 0.0, 100.0), clamp(v, 0.0, 100.0)

    # fallback
    return 50.0, 50.0, 50.0


def generate_colors(rows: list[dict], seed: int = 0) -> dict:
    mapping = {}
    # First assign regions and hcv
    for r in rows:
        bid = r.get('BiomeID')
        region = assign_region(r)
        h, c, v = map_to_hcv(r, region, seed=seed)
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
    p.add_argument('--input', default='.scripts/BiomeTable.csv')
    p.add_argument('--output', default='biomes/colors.generated.yml')
    p.add_argument('--seed', type=int, default=0)
    p.add_argument('--overwrite', action='store_true')
    args = p.parse_args()

    rows = parse_biome_table(args.input)
    mapping = generate_colors(rows, seed=args.seed)
    write_yaml(mapping, args.output)
    print(f'Wrote {len(mapping)} biome colors to {args.output}')


if __name__ == '__main__':
    main()
