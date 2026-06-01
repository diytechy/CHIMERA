"""Compare vanilla-Paper surface biome area distribution vs CHIMERA's
distribution (re-expressed through each CHIMERA biome's mapped vanilla biome).

Vanilla side: Monte-Carlo sample the 5 independent climate marginals (faithful
NormalNoise reproduction) and nearest-match against the ported
OverworldBiomeBuilder parameter list (Climate.fitness metric).

Chimera side: benchmark_CHIMERA.csv Surface Count, mapped BiomeID -> VanillaID
via BiomeTable.csv.

Both are restricted to land/surface biomes (ocean + river excluded) and
normalized to 100% of land surface, so the shapes are comparable.
"""
import csv
import numpy as np
from collections import defaultdict
from mc_noise import sample_marginal
from vanilla_builder import build_param_list

ROOT = r"c:\Projects\ORIGEN2"
N_SAMPLES = 600_000
SEED = 20260601


def q(v):
    return np.trunc(np.asarray(v) * 10000.0).astype(np.int64)


def is_ocean(name):
    return "ocean" in name
def is_river(name):
    return name in ("river", "frozen_river")
def is_land(name):
    return not is_ocean(name) and not is_river(name)


# ---------- VANILLA via Monte Carlo ----------
def vanilla_distribution():
    pts = build_param_list()
    biomes = [p[5] for p in pts]
    P = len(pts)
    # quantized param ranges, shape (P,)
    tmin = q([p[0][0] for p in pts]); tmax = q([p[0][1] for p in pts])
    hmin = q([p[1][0] for p in pts]); hmax = q([p[1][1] for p in pts])
    cmin = q([p[2][0] for p in pts]); cmax = q([p[2][1] for p in pts])
    emin = q([p[3][0] for p in pts]); emax = q([p[3][1] for p in pts])
    wmin = q([p[4][0] for p in pts]); wmax = q([p[4][1] for p in pts])

    T = q(sample_marginal("temperature", N_SAMPLES, SEED + 1))
    H = q(sample_marginal("humidity", N_SAMPLES, SEED + 2))
    C = q(sample_marginal("continentalness", N_SAMPLES, SEED + 3))
    E = q(sample_marginal("erosion", N_SAMPLES, SEED + 4))
    W = q(sample_marginal("weirdness", N_SAMPLES, SEED + 5))

    counts = defaultdict(int)
    B = 800
    def rng_dist(tq, lo, hi):
        above = tq[:, None] - hi[None, :]
        below = lo[None, :] - tq[:, None]
        return np.where(above > 0, above, np.maximum(below, 0))
    for s in range(0, N_SAMPLES, B):
        e = min(s + B, N_SAMPLES)
        dt = rng_dist(T[s:e], tmin, tmax)
        d2 = dt * dt
        d2 += rng_dist(H[s:e], hmin, hmax) ** 2
        d2 += rng_dist(C[s:e], cmin, cmax) ** 2
        d2 += rng_dist(E[s:e], emin, emax) ** 2
        d2 += rng_dist(W[s:e], wmin, wmax) ** 2
        idx = np.argmin(d2, axis=1)
        for i in idx:
            counts[biomes[i]] += 1
    return counts


# ---------- CHIMERA ----------
def chimera_distribution():
    # BiomeID -> VanillaID
    vmap = {}
    with open(f"{ROOT}/.artifacts/BiomeTable.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            vmap[row["BiomeID"].strip()] = (row.get("VanillaID") or "").strip()
    # benchmark surface counts
    counts = defaultdict(int)
    unmapped = []
    with open(f"{ROOT}/benchmark_CHIMERA.csv", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["Biome"].strip()
            sc = int(row["Surface Count"])
            if sc == 0:
                continue
            van = vmap.get(name, "")
            if not van:
                unmapped.append((name, sc))
                continue
            counts[van] += sc
    return counts, unmapped


def normalize_land(counts):
    land = {k: v for k, v in counts.items() if is_land(k)}
    tot = sum(land.values())
    return {k: 100.0 * v / tot for k, v in land.items()}, tot


def main():
    van_counts = vanilla_distribution()
    chi_counts, unmapped = chimera_distribution()

    van_total = sum(van_counts.values())
    van_ocean = sum(v for k, v in van_counts.items() if is_ocean(k))
    van_river = sum(v for k, v in van_counts.items() if is_river(k))
    chi_total = sum(chi_counts.values())
    chi_ocean = sum(v for k, v in chi_counts.items() if is_ocean(k))
    chi_river = sum(v for k, v in chi_counts.items() if is_river(k))

    van_land, van_land_tot = normalize_land(van_counts)
    chi_land, chi_land_tot = normalize_land(chi_counts)

    print("=" * 78)
    print("MACRO SPLIT (share of all sampled / counted surface)")
    print("=" * 78)
    print(f"{'':14s}{'Vanilla Paper':>18s}{'CHIMERA':>18s}")
    print(f"{'ocean':14s}{100*van_ocean/van_total:>17.1f}%{100*chi_ocean/chi_total:>17.1f}%")
    print(f"{'river':14s}{100*van_river/van_total:>17.1f}%{100*chi_river/chi_total:>17.1f}%")
    print(f"{'land(surface)':14s}{100*(van_total-van_ocean-van_river)/van_total:>17.1f}%"
          f"{100*(chi_total-chi_ocean-chi_river)/chi_total:>17.1f}%")

    keys = sorted(set(van_land) | set(chi_land), key=lambda k: -(van_land.get(k, 0)))
    print()
    print("=" * 78)
    print("LAND-SURFACE BIOME DISTRIBUTION (normalized to 100% of land surface)")
    print("=" * 78)
    print(f"{'vanilla biome':26s}{'Vanilla%':>10s}{'CHIMERA%':>10s}{'diff(C-V)':>11s}{'ratio C/V':>11s}")
    print("-" * 78)
    rows = []
    for k in keys:
        v = van_land.get(k, 0.0)
        c = chi_land.get(k, 0.0)
        ratio = (c / v) if v > 0.01 else float('inf')
        rows.append((k, v, c, c - v, ratio))
    for k, v, c, d, r in rows:
        rs = "  n/a" if r == float('inf') else f"{r:>10.2f}x"
        print(f"{k:26s}{v:>9.2f}%{c:>9.2f}%{d:>+10.2f}{rs:>11s}")

    print()
    print("=" * 78)
    print("MOST OVER-REPRESENTED in CHIMERA (C-V, positive = too much vs vanilla)")
    print("=" * 78)
    for k, v, c, d, r in sorted(rows, key=lambda x: -x[3])[:12]:
        print(f"  {k:26s} vanilla {v:5.2f}%  chimera {c:5.2f}%  (+{d:.2f} pts)")
    print()
    print("MOST UNDER-REPRESENTED in CHIMERA (vanilla wants more of these)")
    print("=" * 78)
    for k, v, c, d, r in sorted(rows, key=lambda x: x[3])[:12]:
        print(f"  {k:26s} vanilla {v:5.2f}%  chimera {c:5.2f}%  ({d:.2f} pts)")

    if unmapped:
        um = sorted(unmapped, key=lambda x: -x[1])[:10]
        print()
        print(f"NOTE: {len(unmapped)} CHIMERA surface biomes have no VanillaID mapping "
              f"(excluded). Largest:")
        for n, sc in um:
            print(f"  {n:30s} surface_count={sc}")

    # dump CSV
    out = f"{ROOT}/.artifacts/vanilla_vs_chimera_landdist.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["vanilla_biome", "vanilla_land_pct", "chimera_land_pct",
                    "diff_C_minus_V", "ratio_C_over_V"])
        for k, v, c, d, r in rows:
            w.writerow([k, f"{v:.4f}", f"{c:.4f}", f"{d:.4f}",
                        "" if r == float('inf') else f"{r:.4f}"])
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
