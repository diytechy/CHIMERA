import csv
from collections import defaultdict
ROOT = r"c:\Projects\ORIGEN2"
vmap = {}
with open(f"{ROOT}/.artifacts/BiomeTable.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        vmap[r["BiomeID"].strip()] = (r.get("VanillaID") or "").strip()
contrib = defaultdict(list)
land_total = 0
def is_land(n): return ("ocean" not in n) and n not in ("river","frozen_river") and n!=""
with open(f"{ROOT}/benchmark_CHIMERA.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        name=r["Biome"].strip(); sc=int(r["Surface Count"])
        if sc==0: continue
        van=vmap.get(name,"")
        if is_land(van):
            contrib[van].append((name,sc)); land_total+=sc
# also count unmapped land toward land_total? keep consistent w/ analyze (excluded)
OVER = ["desert","snowy_taiga","jungle","frozen_peaks","meadow","snowy_plains",
        "windswept_hills","ice_spikes","pale_garden","mushroom_fields","badlands"]
for v in OVER:
    items=sorted(contrib.get(v,[]),key=lambda x:-x[1])
    share=100*sum(s for _,s in items)/land_total
    print(f"\n### {v}  (chimera land share {share:.2f}%) — {len(items)} biomes")
    for n,s in items[:14]:
        print(f"    {100*s/land_total:5.2f}%  {n}")
