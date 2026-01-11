"""Validate generated colors file

Checks for:
- Well-formed hex values
- Unique colors (warn if duplicates)
- Same number of entries as the BiomeTable

Usage:
  python .scripts/validate_generated_colors.py --colors biomes/colors.generated.yml --biometable .scripts/BiomeTable.csv
"""
from __future__ import annotations
import argparse
import re

HEX_RE = re.compile(r"^0x[0-9a-fA-F]{6}$")


def read_colors(path: str) -> dict:
    d = {}
    with open(path, encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if ':' not in line:
                continue
            k, v = line.split(':', 1)
            d[k.strip()] = v.strip()
    return d


def count_biomes(path: str) -> int:
    c = 0
    with open(path, encoding='utf-8') as fh:
        hdr = fh.readline()
        for _ in fh:
            c += 1
    return c


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--colors', default='biomes/colors.generated.yml')
    p.add_argument('--biometable', default='.scripts/BiomeTable.csv')
    args = p.parse_args()

    colors = read_colors(args.colors)
    # basic checks
    bad = [k for k, v in colors.items() if not HEX_RE.match(v)]
    if bad:
        print('Malformed hex for:', bad[:10])
        raise SystemExit(2)

    # uniqueness
    inv = {}
    duplicates = {}
    for k, v in colors.items():
        inv.setdefault(v, []).append(k)
    for v, keys in inv.items():
        if len(keys) > 1:
            duplicates[v] = keys
    if duplicates:
        print('Found duplicates (color -> biomes):')
        for v, keys in list(duplicates.items())[:10]:
            print(v, keys[:10])
    else:
        print('No duplicate colors found.')

    n_colors = len(colors)
    n_biomes = count_biomes(args.biometable)
    print(f'{n_colors} colors, {n_biomes} biomes in table')
    if n_colors != n_biomes:
        print('Warning: counts differ')

if __name__ == '__main__':
    main()
