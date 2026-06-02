"""Apply a representative retag set and show before/after land-distribution vs
vanilla, to verify the recommendations move CHIMERA toward vanilla's shape.

A retag = changing a CHIMERA biome's VanillaID tag. It does NOT change terrain
coverage, only which vanilla biome that coverage is counted/treated as.
"""
import csv
from collections import defaultdict
ROOT = r"c:\Projects\ORIGEN2"

# BiomeID -> new VanillaID. Chosen to (a) fill vanilla's forest/plains/birch/
# dark_forest/sparse_jungle/stony_shore/savanna_plateau deficits and
# (b) drain the worst over-tagged rare buckets (frozen_peaks, ice_spikes,
# mushroom_fields, pale_garden). Also assigns the 11 untagged biomes.
RETAG = {
    # --- temperate "woodlands" mis-tagged snowy_taiga -> real temperate forests
    "OAK_WOODLANDS": "forest",
    "AUTUMNAL_WOODLANDS": "forest",
    "MAPLE_WOODLANDS": "forest",
    "SAKURA_WOODLANDS": "forest",
    "BIRCH_WOODLANDS": "birch_forest",
    "DARK_OAK_WOODLANDS": "dark_forest",
    "SPRUCE_WOODLANDS": "old_growth_spruce_taiga",
    "SUGAR_PINE_WOODLANDS": "old_growth_pine_taiga",
    "REDWOOD_WOODLANDS": "old_growth_pine_taiga",
    # --- a forest mis-tagged desert
    "FIRMIHIN_FOREST": "forest",
    # --- jungle surplus -> sparse_jungle deficit
    "PALM_FOREST": "sparse_jungle",
    "OVERGROWN_CLIFFS": "sparse_jungle",
    "ROCKY_JUNGLE": "sparse_jungle",
    # --- meadow surplus -> plains deficit (these are grasslands)
    "PRAIRIE": "plains",
    "TAIGA_CLEARING": "plains",
    "BOREAL_SHRUBLAND": "plains",
    # --- snowy birch
    "SNOWY_BIRCH_FOREST": "birch_forest",
    # --- drain over-tagged rare peaks
    "LAND_GLACIER": "snowy_slopes",
    "ICE_CAPS": "snowy_slopes",
    "SNOWY_MOUNTAINS": "snowy_slopes",
    "PERMAFROST_CLIFFS": "grove",
    # --- drain ice_spikes (vanilla-rare)
    "FROSTY_FINGERS": "snowy_plains",
    "FROZEN_SPIRES": "snowy_slopes",
    # --- drain mushroom_fields (vanilla-rare island biome)
    "FROZEN_FUNGI": "snowy_taiga",
    # --- drain pale_garden color variants (arid ones aren't dark pale forest)
    "ARID_PALE_GARDEN": "badlands",
    "ORANGE_ARID_PALE_GARDEN": "badlands",
    "RED_ARID_PALE_GARDEN": "badlands",
    "BLACK_ARID_PALE_GARDEN": "dark_forest",
    # --- assign the 11 untagged surface biomes
    "MONSOON_FOREST": "jungle",
    "CLOUD_FOREST": "sparse_jungle",
    "TEMPERATE_RAINFOREST": "forest",
    "DENSELY_WOODED_HIGHLANDS": "dark_forest",
    "FIR_FIELDS": "taiga",
    "MESA_MONUMENTS": "wooded_badlands",
    "BADLANDS_BUTTES": "badlands",
    "SAVANNA_OVERHANGS": "savanna_plateau",
    "SHALE_BEACH": "stony_shore",
    "BLACK_SAND_BEACH": "beach",
    "ROCKY_SEA_CAVES": "beach",
}

# vanilla land shares from the Monte-Carlo run (.artifacts CSV)
van = {}
with open(f"{ROOT}/.artifacts/vanilla_vs_chimera_landdist.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        van[r["vanilla_biome"]] = float(r["vanilla_land_pct"])

vmap = {}
with open(f"{ROOT}/.artifacts/BiomeTable.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        vmap[r["BiomeID"].strip()] = (r.get("VanillaID") or "").strip()

def is_land(n): return n and ("ocean" not in n) and n not in ("river", "frozen_river")

def aggregate(use_retag):
    counts = defaultdict(int)
    with open(f"{ROOT}/benchmark_CHIMERA.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            name = r["Biome"].strip(); sc = int(r["Surface Count"])
            if sc == 0: continue
            van_id = vmap.get(name, "")
            if use_retag and name in RETAG:
                van_id = RETAG[name]
            if is_land(van_id):
                counts[van_id] += sc
    tot = sum(counts.values())
    return {k: 100.0 * v / tot for k, v in counts.items()}

before = aggregate(False)
after = aggregate(True)

def l1(d):
    keys = set(d) | set(van)
    return sum(abs(d.get(k, 0) - van.get(k, 0)) for k in keys)

print(f"Total absolute deviation from vanilla (sum |C-V| over land biomes):")
print(f"   BEFORE retag: {l1(before):6.1f} points")
print(f"   AFTER  retag: {l1(after):6.1f} points   ({len(RETAG)} biomes retagged)\n")

focus = ["forest","plains","birch_forest","dark_forest","sparse_jungle","stony_shore",
         "savanna_plateau","wooded_badlands","old_growth_birch_forest",
         "desert","snowy_taiga","jungle","meadow","frozen_peaks","ice_spikes",
         "mushroom_fields","pale_garden","badlands"]
print(f"{'vanilla biome':24s}{'Vanilla%':>9s}{'before%':>9s}{'after%':>9s}")
print("-"*51)
for k in focus:
    print(f"{k:24s}{van.get(k,0):>8.2f}%{before.get(k,0):>8.2f}%{after.get(k,0):>8.2f}%")

# write suggested retag CSV
with open(f"{ROOT}/.artifacts/suggested_retags.csv","w",newline="",encoding="utf-8") as f:
    w=csv.writer(f); w.writerow(["BiomeID","current_VanillaID","suggested_VanillaID"])
    for b,nv in RETAG.items():
        w.writerow([b, vmap.get(b,"(none)"), nv])
print(f"\nWrote {ROOT}/.artifacts/suggested_retags.csv")
