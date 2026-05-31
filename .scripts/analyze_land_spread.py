#!/usr/bin/env python3
"""Analyze benchmark_CHIMERA.csv: classify biomes and report land-surface spread.

Land-surface = biomes assigned by the landmass/mesa/largeland distribution,
EXCLUDING oceans, coasts, beaches, shallows, spots (sinkholes/volcanoes/crater
lakes/springs), trenches/pits/rifts/vents/overhangs, travertine, mushroom
islands, and pure subsurface (0 surface) biomes.
"""
import csv
import re
import sys

CSV = r"C:\Projects\BiomeTool\benchmark_CHIMERA.csv"

# Substring/suffix patterns that mark a NON-land-surface (special) biome.
EXCLUDE_PATTERNS = [
    # oceans / water
    "OCEAN", "SEAGRASS", "KELP", "CORAL", "ABYSSAL", "STONEGATE_SEAS",
    "MARINE_MONOLITHS", "ARCTIC_ARCHES", "ICEBERG", "WINTRY_SEAS", "WINTRY_WATERS",
    "ARCHIPELAGO", "SEA_ARCHES",
    # depth / trench / pit / rift / vents / overhangs / slopes
    "TRENCH", "_PIT", "TAR_PITS", "RIFT", "VENTS", "OVERHANGS", "SLOPES",
    "DEEP_DEPTHS", "DEEP_DARK", "SHALLOW",
    # coast / beach
    "COAST", "BEACH", "SHALLOWS",
    # spots
    "SINKHOLE", "EXTINCT_VOLCANO", "CRATER_LAKE", "PRISMATIC_SPRING",
    "ERUPTED_VOLCANO", "SEARING_TORS",
    # mushroom islands
    "MUSHROOM",
    # travertine special
    "TRAVERTINE",
    # sea caves
    "SEA_CAVES",
    # oasis (spot-like)
    "OASIS",
    # glaciers/archipelago border specials handled by ocean
    "GLACIAL_OVERHANGS",
]


def is_excluded(name: str) -> bool:
    for p in EXCLUDE_PATTERNS:
        if p in name:
            return True
    return False


def main():
    rows = []
    with open(CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows.append(r)

    land = []
    excluded = []
    subsurface = []
    for r in rows:
        name = r["Biome"]
        surf = float(r["Surface %"])
        if surf <= 0.0:
            subsurface.append((name, surf))
            continue
        if is_excluded(name):
            excluded.append((name, surf))
            continue
        land.append((name, surf))

    land.sort(key=lambda x: x[1])
    total = sum(s for _, s in land)
    n = len(land)
    mn = land[0][1]
    mx = land[-1][1]
    print(f"Land-surface biomes: {n}   total surface% = {total:.2f}")
    print(f"min = {mn:.4f} ({land[0][0]})   max = {mx:.4f} ({land[-1][0]})")
    print(f"max/min ratio = {mx/mn:.1f}x   mean = {total/n:.4f}")
    print()
    print("=== 20 RAREST land-surface biomes ===")
    for name, s in land[:20]:
        print(f"  {s:7.4f}  {name}")
    print()
    print("=== 20 MOST COMMON land-surface biomes ===")
    for name, s in reversed(land[-20:]):
        print(f"  {s:7.4f}  {name}")

    # How many within 5x of the median?
    med = land[n // 2][1]
    print()
    print(f"median = {med:.4f}")
    lo, hi = med / 5, med * 5
    out_lo = [x for x in land if x[1] < lo]
    out_hi = [x for x in land if x[1] > hi]
    print(f"5x-of-median band = [{lo:.4f}, {hi:.4f}]")
    print(f"  below band: {len(out_lo)}   above band: {len(out_hi)}")

    if "--list-all" in sys.argv:
        print("\n=== ALL land-surface, sorted ===")
        for name, s in land:
            print(f"  {s:7.4f}  {name}")


if __name__ == "__main__":
    main()
