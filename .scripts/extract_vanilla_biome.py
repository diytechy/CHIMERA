#!/usr/bin/env python3
"""
Extract a vanilla Minecraft biome's complete worldgen definition from the bundled
Mojang server jar, so it can be ported into the CHIMERA Terra pack.

Pulls EVERYTHING that defines the biome's appearance — the failure mode this guards
against is missing a source (e.g. surface_rules, which define cave wall materials and
are easy to overlook):
  - biome JSON          (colors, climate, spawners, carvers, feature list)
  - placed + configured features  (resolved recursively, incl. nested selectors)
  - surface_rule blocks for the biome  (sliced out of noise_settings/overworld.json)
  - noises referenced by those surface rules

Usage:
  python .scripts/extract_vanilla_biome.py <biome> [mojang.jar | cache_dir]

The jar is resolved from (in order): the 2nd arg, $CHIMERA_MOJANG_JAR,
$CHIMERA_MC_CACHE/mojang_*.jar (newest), or a built-in fallback cache path.
Output: .artifacts/vanilla-extract/<biome>/  (+ SUMMARY.md)
"""
import sys, os, re, io, json, zipfile, glob
from pathlib import Path

WG = "data/minecraft/worldgen"
FALLBACK_CACHE = r"Z:/MC_SERV_BACKUP_20260516/MINECRAFT_SERVER_TMP_4BACKUP/cache"


def newest(jars):
    jars = [j for j in jars if j and os.path.isfile(j)]
    return max(jars, key=os.path.getmtime) if jars else None


def resolve_jar(arg):
    # explicit jar file
    for c in (arg, os.environ.get("CHIMERA_MOJANG_JAR")):
        if c and os.path.isfile(c):
            return c
    # a directory of jars -> pick the NEWEST (by mtime; version names don't sort)
    for d in (arg, os.environ.get("CHIMERA_MC_CACHE"), FALLBACK_CACHE):
        if d and os.path.isdir(d):
            j = newest(glob.glob(os.path.join(d, "mojang_*.jar")))
            if j:
                return j
    sys.exit("Could not find a mojang server jar. Pass it as the 2nd arg, set "
             "$CHIMERA_MOJANG_JAR, or point $CHIMERA_MC_CACHE at the server's cache dir.")


def open_server_zip(mojang_jar):
    """mojang_*.jar is a bundler; the real data lives in the nested server jar."""
    z = zipfile.ZipFile(mojang_jar)
    nested = [n for n in z.namelist() if re.match(r"META-INF/versions/.*/server-.*\.jar$", n)]
    if not nested:
        return z  # already a flat jar
    return zipfile.ZipFile(io.BytesIO(z.read(nested[0])))


def read_json(z, path):
    try:
        return json.loads(z.read(path))
    except KeyError:
        return None


def find_feature_refs(node, out):
    """Collect every 'feature: <id-string>' reference anywhere in a configured feature."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "feature" and isinstance(v, str):
                out.add(v)
            else:
                find_feature_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            find_feature_refs(v, out)


def find_biome_surface_rules(node, biome, acc):
    """Capture surface_rule subtrees gated on this biome (type=biome, biome_is=<biome>)."""
    if isinstance(node, dict):
        cond = node.get("if_true")
        if isinstance(cond, dict) and cond.get("type") == "minecraft:biome" \
           and biome in str(cond.get("biome_is")):
            acc.append(node)
        for v in node.values():
            find_biome_surface_rules(v, biome, acc)
    elif isinstance(node, list):
        for v in node:
            find_biome_surface_rules(v, biome, acc)


def find_noise_refs(node, out):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "noise" and isinstance(v, str):
                out.add(v)
            else:
                find_noise_refs(v, out)
    elif isinstance(node, list):
        for v in node:
            find_noise_refs(v, out)


def short(rid):
    return rid.split(":", 1)[-1]


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    biome = short(sys.argv[1])
    z = open_server_zip(resolve_jar(sys.argv[2] if len(sys.argv) > 2 else None))
    out = Path(".artifacts/vanilla-extract") / biome
    out.mkdir(parents=True, exist_ok=True)

    def dump(relpath, obj):
        p = out / relpath
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(obj, indent=2), encoding="utf-8")

    summary, warn = [], []

    # 1. Biome
    bj = read_json(z, f"{WG}/biome/{biome}.json")
    if not bj:
        sys.exit(f"Biome not found: {WG}/biome/{biome}.json")
    dump(f"biome/{biome}.json", bj)
    spawn = {k: v for k, v in bj.get("spawners", {}).items() if v}
    summary.append(f"- biome/{biome}.json  (temp {bj.get('temperature')}, downfall {bj.get('downfall')})")
    summary.append(f"  colors/effects: { {**bj.get('effects', {}), **{k:v for k,v in bj.get('attributes',{}).items() if 'visual' in k}} }")
    summary.append(f"  spawners: { {k:[s['type'] for s in v] for k,v in spawn.items()} }")

    # 2. Features (placed -> configured, recursive)
    placed = [pf for step in bj.get("features", []) for pf in step]
    cfg_seen, noise_from_cfg = set(), set()
    for pf in placed:
        pj = read_json(z, f"{WG}/placed_feature/{short(pf)}.json")
        if not pj:
            warn.append(f"missing placed_feature {pf}")
            continue
        dump(f"placed_feature/{short(pf)}.json", pj)
        feat = pj.get("feature")
        roots = {feat} if isinstance(feat, str) else set()
        while roots:
            cid = roots.pop()
            if cid in cfg_seen:
                continue
            cfg_seen.add(cid)
            cj = read_json(z, f"{WG}/configured_feature/{short(cid)}.json")
            if not cj:
                warn.append(f"missing configured_feature {cid}")
                continue
            dump(f"configured_feature/{short(cid)}.json", cj)
            nested = set(); find_feature_refs(cj, nested)
            roots |= (nested - cfg_seen)
            find_noise_refs(cj, noise_from_cfg)
    summary.append(f"- {len(placed)} placed features, {len(cfg_seen)} configured features")

    # 3. Surface rules for this biome (THE easy-to-miss one)
    ow = read_json(z, f"{WG}/noise_settings/overworld.json")
    sr = []
    if ow:
        find_biome_surface_rules(ow.get("surface_rule", {}), f"minecraft:{biome}", sr)
    dump("surface_rules_for_biome.json", sr)
    nrefs = set(noise_from_cfg)
    for blk in sr:
        find_noise_refs(blk, nrefs)
    summary.append(f"- {len(sr)} surface-rule block(s) gating on this biome "
                   f"(wall/floor block replacement -- CHECK THESE)")

    # 4. Referenced noises
    for nid in sorted(nrefs):
        nj = read_json(z, f"{WG}/noise/{short(nid)}.json")
        if nj:
            dump(f"noise/{short(nid)}.json", nj)
    if nrefs:
        summary.append(f"- noises referenced: {sorted(short(n) for n in nrefs)}")

    (out / "SUMMARY.md").write_text(
        f"# Vanilla extract: {biome}\n\nSources pulled (read ALL before translating — see "
        f"docs/VANILLA_TO_TERRA_MAP.md):\n\n" + "\n".join(summary) +
        ("\n\n## WARNINGS\n" + "\n".join(f"- {w}" for w in warn) if warn else "") + "\n",
        encoding="utf-8")
    print(f"Extracted to {out}\n")
    print("\n".join(summary))
    if warn:
        print("\nWARNINGS:\n" + "\n".join(warn))


if __name__ == "__main__":
    main()
