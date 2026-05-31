#!/usr/bin/env python3
"""Compare two benchmark CSVs (before/after) on land-surface biomes.

Usage: python compare_rounds.py <before.csv> <after.csv>
Reuses the land-surface classification from analyze_land_spread.
"""
import csv
import sys
from analyze_land_spread import is_excluded


def load(path):
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["Biome"]] = float(r["Surface %"])
    return out


def land_stats(d):
    land = [(n, v) for n, v in d.items() if v > 0 and not is_excluded(n)]
    land.sort(key=lambda x: x[1])
    tot = sum(v for _, v in land)
    n = len(land)
    return land, tot, n


def main():
    before = load(sys.argv[1])
    after = load(sys.argv[2])
    lb, tb, nb = land_stats(before)
    la, ta, na = land_stats(after)
    db = dict(lb); da = dict(la)

    print(f"BEFORE: {nb} land biomes, total {tb:.2f}%, min {lb[0][1]:.4f} ({lb[0][0]}), "
          f"max {lb[-1][1]:.4f} ({lb[-1][0]}), ratio {lb[-1][1]/lb[0][1]:.1f}x")
    print(f"AFTER : {na} land biomes, total {ta:.2f}%, min {la[0][1]:.4f} ({la[0][0]}), "
          f"max {la[-1][1]:.4f} ({la[-1][0]}), ratio {la[-1][1]/la[0][1]:.1f}x")

    med_a = la[na // 2][1]
    lo, hi = med_a / 5, med_a * 5
    below = [x for x in la if x[1] < lo]
    above = [x for x in la if x[1] > hi]
    print(f"AFTER median {med_a:.4f}; 5x band [{lo:.4f},{hi:.4f}]: "
          f"{len(below)} below, {len(above)} above")

    print("\n=== AFTER: 15 rarest land biomes ===")
    for n, v in la[:15]:
        d = v - db.get(n, 0)
        print(f"  {v:7.4f}  ({d:+.4f})  {n}")
    print("\n=== AFTER: 15 most-common land biomes ===")
    for n, v in reversed(la[-15:]):
        d = v - db.get(n, 0)
        print(f"  {v:7.4f}  ({d:+.4f})  {n}")

    print("\n=== 20 biggest movers (|after-before|) ===")
    allnames = set(db) | set(da)
    movers = sorted(((n, da.get(n, 0) - db.get(n, 0)) for n in allnames),
                    key=lambda x: -abs(x[1]))
    for n, d in movers[:20]:
        if is_excluded(n):
            tag = "[excl]"
        else:
            tag = ""
        print(f"  {d:+7.4f}  before={db.get(n,0):7.4f} after={da.get(n,0):7.4f}  {n} {tag}")


if __name__ == "__main__":
    main()
