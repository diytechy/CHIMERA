import csv
ROOT = r"c:\Projects\ORIGEN2"
rows = {}
with open(f"{ROOT}/.artifacts/BiomeTable.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows[r["BiomeID"].strip()] = r
total_surf = 0
land_mapped = 0
unmapped = []
with open(f"{ROOT}/benchmark_CHIMERA.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        name = r["Biome"].strip(); sc = int(r["Surface Count"])
        if sc == 0: continue
        total_surf += sc
        br = rows.get(name, {})
        van = (br.get("VanillaID") or "").strip()
        if not van:
            unmapped.append((name, sc, br.get("Category","").strip(),
                             br.get("Type","").strip(), br.get("TerrainParent","").strip()))
print(f"total chimera surface count: {total_surf:,}")
us = sum(x[1] for x in unmapped)
print(f"unmapped surface count: {us:,}  ({100*us/total_surf:.2f}% of all surface)\n")
print(f"{'biome':32s}{'surf%':>7s}  cat / type / terrainparent")
for n, sc, cat, typ, tp in sorted(unmapped, key=lambda x:-x[1]):
    print(f"{n:32s}{100*sc/total_surf:>6.3f}%  {cat} / {typ} / {tp}")
