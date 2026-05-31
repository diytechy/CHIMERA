#!/usr/bin/env python3
"""Compare predicted (BiomeTable.csv 'CHIMERA' col) vs benchmark (benchmark_CHIMERA.csv
'Surface %') per biome. Reports biggest absolute discrepancies to improve the predictor."""
import csv

PRED = r"C:\Projects\CHIMERA\.artifacts\BiomeTable.csv"
BENCH = r"C:\Projects\BiomeTool\benchmark_CHIMERA.csv"


def load_pred():
    out = {}
    for r in csv.DictReader(open(PRED, encoding="utf-8")):
        v = r["CHIMERA"].strip().rstrip("%")
        try:
            out[r["BiomeID"]] = float(v)
        except ValueError:
            out[r["BiomeID"]] = 0.0
    return out


def load_bench():
    out = {}
    for r in csv.DictReader(open(BENCH, encoding="utf-8")):
        out[r["Biome"]] = float(r["Surface %"])
    return out


def main():
    pred = load_pred()
    bench = load_bench()
    names = sorted(set(pred) | set(bench))
    rows = []
    for n in names:
        p = pred.get(n, 0.0)
        b = bench.get(n, 0.0)
        rows.append((n, p, b, p - b))

    # only-in-one
    only_pred = [n for n in names if n in pred and n not in bench]
    only_bench = [n for n in names if n in bench and n not in pred]

    # error stats over biomes present in benchmark with surface>0
    common = [(n, p, b, d) for n, p, b, d in rows if b > 0]
    mae = sum(abs(d) for _, _, _, d in common) / len(common)
    print(f"Biomes compared (bench surface>0): {len(common)}   MAE = {mae:.4f}%")
    print(f"Only in predictor ({len(only_pred)}): {only_pred[:20]}")
    print(f"Only in benchmark ({len(only_bench)}): {only_bench[:20]}")
    print()
    print("=== 30 largest |pred - bench| (pred / bench / diff) ===")
    for n, p, b, d in sorted(common, key=lambda x: -abs(x[3]))[:30]:
        print(f"  {d:+7.3f}   pred={p:7.3f}  bench={b:7.3f}  {n}")


if __name__ == "__main__":
    main()
