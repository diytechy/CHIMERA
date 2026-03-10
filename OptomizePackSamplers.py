#!/usr/bin/env python3
"""
OptomizePackSamplers.py

Optimizes pack-level sampler definition files by:
  1. Discovering all pack sampler files from pack.yml (samplers section).
  2. Removing unused named samplers (zero references across alias, stage, and
     expression-call sources). Variables blocks are preserved.
  3. Removing YAML anchors from named samplers (only named samplers, not variables).
  4. Replacing in-file aliases to named samplers with explicit cross-file
     string references (e.g. "$math/samplers/rivers.yml:samplers.riverNoise").
  5. Wrapping named samplers used more than 3 times (combined across sampler
     files and biome-distribution stage files) in a CACHE sampler with exp: 2.
     Samplers of type CACHE or DENDRY are excluded from wrapping.

Usage:
    pip install ruamel.yaml
    python OptomizePackSamplers.py
"""

import re
import csv
from pathlib import Path
from collections import Counter
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq

PACK_ROOT = Path(__file__).parent
PACK_YML = PACK_ROOT / "pack.yml"
CACHE_THRESHOLD = 100        # wrap in CACHE if combined usages exceed this value


# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------

def make_yaml():
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096  # prevent unwanted line-wrapping
    yaml.best_sequence_indent = 2
    yaml.best_map_flow_style = False
    return yaml


def load_yaml(path: Path):
    yaml = make_yaml()
    with open(path, encoding="utf-8") as f:
        return yaml.load(f)


def save_yaml(data, path: Path):
    yaml = make_yaml()
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        yaml.dump(data, f)


# ---------------------------------------------------------------------------
# Phase 1 — Discovery
# ---------------------------------------------------------------------------

def discover_sampler_files():
    """
    Parse pack.yml and return [(rel_path_str, abs_Path), ...] for each
    file listed in samplers["<<"].
    Each entry in that list looks like "math/samplers/rivers.yml:samplers".
    """
    data = load_yaml(PACK_YML)
    samplers_section = data.get("samplers", {})
    merge_list = samplers_section.get("<<", [])

    # merge_list may be a plain list of strings, or a CommentedSeq of strings
    result = []
    for entry in merge_list:
        file_part = str(entry).split(":")[0]
        abs_path = PACK_ROOT / file_part
        result.append((file_part, abs_path))
    return result


def discover_pipeline_resolution():
    """
    Detect the biome pipeline resolution from the active preset in pack.yml.

    Reads the 'biomes' key (e.g. "$biome-distribution/presets/CHIMERA.yml:biomes"),
    loads the referenced preset file, and extracts provider.resolution.
    Returns the resolution value, or 1 as a fallback.
    """
    data = load_yaml(PACK_YML)
    biomes_ref = data.get("biomes")

    if not isinstance(biomes_ref, str) or not biomes_ref.startswith("$"):
        print("  WARNING: Could not parse biomes reference from pack.yml, using resolution=1")
        return 1

    # Parse "$biome-distribution/presets/CHIMERA.yml:biomes"
    ref_body = biomes_ref[1:]  # strip leading $
    parts = ref_body.split(":")
    if len(parts) < 2:
        print(f"  WARNING: Unexpected biomes ref format: {biomes_ref}, using resolution=1")
        return 1

    preset_file = PACK_ROOT / parts[0]
    key_path = parts[1].split(".")  # e.g. ["biomes"]

    if not preset_file.exists():
        print(f"  WARNING: Preset file not found: {preset_file}, using resolution=1")
        return 1

    preset_data = load_yaml(preset_file)

    # Navigate to the referenced key (e.g. biomes)
    node = preset_data
    for key in key_path:
        if isinstance(node, CommentedMap) and key in node:
            node = node[key]
        else:
            print(f"  WARNING: Key '{key}' not found in preset, using resolution=1")
            return 1

    # Navigate into provider.resolution
    if isinstance(node, CommentedMap):
        provider = node.get("provider", {})
        if isinstance(provider, CommentedMap):
            resolution = provider.get("resolution", 1)
            return int(resolution)

    print("  WARNING: Could not find provider.resolution in preset, using resolution=1")
    return 1


# ---------------------------------------------------------------------------
# Phase 2 — Catalog helpers
# ---------------------------------------------------------------------------

def get_named_sampler_ids(data):
    """
    Return {python_object_id: sampler_name} for every entry directly under
    data['samplers'].  Only CommentedMap / CommentedSeq values are included
    (scalar values are not samplers).
    """
    result = {}
    samplers = data.get("samplers", {})
    if isinstance(samplers, CommentedMap):
        for name, val in samplers.items():
            if isinstance(val, (CommentedMap, CommentedSeq)):
                result[id(val)] = name
    return result


def get_definition_sites(data):
    """
    Return a set of (id(parent), key) pairs that represent the *definition*
    location of each named sampler (i.e. its slot in the top-level samplers map).
    Used to distinguish definitions from alias uses during the tree walk.
    """
    sites = set()
    samplers = data.get("samplers", {})
    if isinstance(samplers, CommentedMap):
        for name in samplers:
            sites.add((id(samplers), name))
    return sites


# ---------------------------------------------------------------------------
# Tree walker
# ---------------------------------------------------------------------------

def walk_tree(node, parent, key, named_sampler_ids, definition_sites, callback):
    """
    Recursively walk the YAML tree.  For every node that is an alias to a
    named sampler (detected by Python object identity), call:

        callback(parent, key, node, sampler_name)

    Rules:
      - Skip the definition site itself (where the sampler is *defined*).
      - Skip YAML merge keys ('<<') entirely.
      - Do not recurse further into an alias node — the shared object would
        already have been (or will be) visited at its definition site.
    """
    if parent is not None and key is not None:
        if key != "<<" and (id(parent), key) not in definition_sites:
            if id(node) in named_sampler_ids:
                callback(parent, key, node, named_sampler_ids[id(node)])
                # Do NOT recurse: the same shared object is handled at its
                # definition site; recursing would risk double-processing.
                return

    # Recurse into children
    if isinstance(node, CommentedMap):
        for k in list(node.keys()):
            child = node[k]
            if isinstance(child, (CommentedMap, CommentedSeq)):
                walk_tree(child, node, k, named_sampler_ids, definition_sites, callback)
    elif isinstance(node, CommentedSeq):
        for i, child in enumerate(node):
            if isinstance(child, (CommentedMap, CommentedSeq)):
                walk_tree(child, node, i, named_sampler_ids, definition_sites, callback)


# ---------------------------------------------------------------------------
# Phase 2 — Counting alias usages
# ---------------------------------------------------------------------------

def count_usages_in_file(data, named_sampler_ids, definition_sites, counter):
    """Accumulate alias usage counts from one file into `counter`."""
    def on_alias(_parent, _key, _val, sampler_name):
        counter[sampler_name] += 1

    walk_tree(data, None, None, named_sampler_ids, definition_sites, on_alias)


# ---------------------------------------------------------------------------
# Phase 2b — Text-based usage counting
# ---------------------------------------------------------------------------

def _build_sampler_patterns(sampler_names):
    """
    Build compiled regex patterns for detecting sampler references in text.

    Returns (expr_pattern, ref_pattern) where:
      - expr_pattern matches expression calls: samplerName(
      - ref_pattern  matches string cross-file refs: samplers.samplerName
    """
    names = sorted(sampler_names)
    expr_pattern = re.compile(
        r'(?<![a-zA-Z_0-9])(' +
        '|'.join(re.escape(n) for n in names) +
        r')\s*\(',
    )
    ref_pattern = re.compile(
        r'samplers\.(' +
        '|'.join(re.escape(n) for n in names) +
        r')(?![a-zA-Z_0-9])',
    )
    return expr_pattern, ref_pattern


def _count_text_refs(file_paths, expr_pattern, ref_pattern, counter):
    """
    Scan a list of file paths for sampler references using the given patterns.
    Accumulates counts into ``counter``.  Returns total matches found.
    """
    total = 0
    for path in file_paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue

        for m in expr_pattern.finditer(text):
            counter[m.group(1)] += 1
            total += 1
        for m in ref_pattern.finditer(text):
            counter[m.group(1)] += 1
            total += 1
    return total


def _count_yaml_tree_refs(node, expr_pat, ref_pat, counter, visited):
    """
    Walk a parsed YAML tree and count sampler references in all string values.

    Handles YAML aliases correctly: when a node is encountered that has already
    been visited (same Python object = YAML alias), its string values are still
    counted as a separate usage, but its children are not recursed into (they
    were already counted at the anchor definition site).

    This ensures that YAML alias references like ``*riverSampler`` each count
    as a separate sampler usage even though they share the same underlying object.
    """
    total = 0

    if isinstance(node, CommentedMap):
        node_id = id(node)
        is_alias = node_id in visited

        # Count string values at this level
        for _, v in node.items():
            if isinstance(v, str):
                for m in expr_pat.finditer(v):
                    counter[m.group(1)] += 1
                    total += 1
                for m in ref_pat.finditer(v):
                    counter[m.group(1)] += 1
                    total += 1

        if not is_alias:
            visited.add(node_id)
            # Recurse into children
            for _, v in node.items():
                if isinstance(v, (CommentedMap, CommentedSeq)):
                    total += _count_yaml_tree_refs(v, expr_pat, ref_pat, counter, visited)

    elif isinstance(node, CommentedSeq):
        node_id = id(node)
        is_alias = node_id in visited

        for item in node:
            if isinstance(item, str):
                for m in expr_pat.finditer(item):
                    counter[m.group(1)] += 1
                    total += 1
                for m in ref_pat.finditer(item):
                    counter[m.group(1)] += 1
                    total += 1

        if not is_alias:
            visited.add(node_id)
            for item in node:
                if isinstance(item, (CommentedMap, CommentedSeq)):
                    total += _count_yaml_tree_refs(item, expr_pat, ref_pat, counter, visited)

    return total


def _count_yaml_file_refs(file_paths, expr_pattern, ref_pattern, counter):
    """
    Parse YAML files and count sampler references by walking the resolved tree.
    Unlike _count_text_refs, this correctly counts YAML alias references as
    separate usages.
    """
    total = 0
    for path in file_paths:
        try:
            data = load_yaml(path)
        except Exception:
            continue
        if data is not None:
            total += _count_yaml_tree_refs(data, expr_pattern, ref_pattern, counter, set())
    return total


def _discover_yml_files(*directories):
    """Return all .yml files under the given directories (relative to PACK_ROOT)."""
    paths = []
    for dirname in directories:
        d = PACK_ROOT / dirname
        if d.exists():
            paths.extend(d.rglob("*.yml"))
    return paths


def count_stage_usages(sampler_names, counter):
    """
    Scan biome-distribution stage files for references to pack-level samplers.

    Parses YAML and walks the resolved tree to correctly count YAML alias
    references (e.g. *riverSampler used 30+ times in add_rivers.yml).

    Counts two kinds of references:
      1. Expression function calls: samplerName(x, z) or samplerName(x, y, z)
      2. String cross-file refs:    $path:samplers.samplerName
    """
    files = _discover_yml_files("biome-distribution")
    if not files or not sampler_names:
        return 0
    expr_pat, ref_pat = _build_sampler_patterns(sampler_names)
    return _count_yaml_file_refs(files, expr_pat, ref_pat, counter)


def count_biome_usages(sampler_names, counter):
    """
    Scan biome definition files (biomes/) and feature files (features/) for
    references to pack-level samplers in expressions and string refs.

    Parses YAML and walks the resolved tree to correctly count YAML alias
    references as separate usages.
    """
    files = _discover_yml_files("biomes", "features")
    if not files or not sampler_names:
        return 0
    expr_pat, ref_pat = _build_sampler_patterns(sampler_names)
    return _count_yaml_file_refs(files, expr_pat, ref_pat, counter)


def count_tesf_usages(sampler_names, counter):
    """
    Scan .tesf (structure script) files for references to pack-level samplers.

    In .tesf files, samplers are referenced via sampler("samplerName", ...).
    These usages prevent a sampler from being removed as unused, but are NOT
    counted toward the CACHE threshold (tesf scripts run rarely and would not
    benefit from caching).

    Returns total number of references found.
    """
    if not sampler_names:
        return 0

    paths = []
    structures_dir = PACK_ROOT / "structures"
    if structures_dir.exists():
        paths.extend(structures_dir.rglob("*.tesf"))

    if not paths:
        return 0

    names = sorted(sampler_names)
    # Match sampler("samplerName" pattern used in .tesf files
    tesf_pattern = re.compile(
        r'sampler\s*\(\s*"(' +
        '|'.join(re.escape(n) for n in names) +
        r')"',
    )

    total = 0
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in tesf_pattern.finditer(text):
            counter[m.group(1)] += 1
            total += 1
    return total


def count_sampler_text_usages(sampler_files, sampler_names, counter):
    """
    Scan sampler file text for expression-based references to other
    pack-level samplers (e.g. ``otherSampler(x, z)`` inside an expression).

    This catches cross-sampler references that aren't YAML aliases — for
    example, EXPRESSION samplers that call other pack-level samplers by
    name.

    To avoid false positives from YAML definition keys (e.g.
    ``samplerName:`` at the top of a samplers block), only expression-call
    patterns (``name(``) and string-ref patterns (``samplers.name``) are
    matched — neither fires on a bare key.

    Returns total number of text references found.
    """
    if not sampler_names:
        return 0
    paths = [abs_path for _, abs_path in sampler_files if abs_path.exists()]
    expr_pat, ref_pat = _build_sampler_patterns(sampler_names)
    return _count_text_refs(paths, expr_pat, ref_pat, counter)


def write_usage_csv(all_sampler_names, stage_counts, biome_counts, alias_counts,
                    combined_counts, output_path):
    """
    Write a CSV file containing sampler usage statistics.
    Columns: sampler, stage, biome, alias, combined, will_cache
    Sorted by combined usage descending.
    """
    rows = []
    for name in all_sampler_names:
        stage = stage_counts.get(name, 0)
        biome = biome_counts.get(name, 0)
        alias = alias_counts.get(name, 0)
        combined = combined_counts.get(name, 0)
        will_cache = "TRUE" if combined > CACHE_THRESHOLD else "FALSE"
        rows.append({
            "sampler": name,
            "stage": stage,
            "biome": biome,
            "alias": alias,
            "combined": combined,
            "will_cache": will_cache,
        })

    # Sort by combined usage descending
    rows.sort(key=lambda r: -r["combined"])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["sampler", "stage", "biome", "alias", "combined", "will_cache"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nUsage table written to: {output_path}")


# ---------------------------------------------------------------------------
# Phase 3 — Transformations
# ---------------------------------------------------------------------------

def remove_anchors(data):
    """
    Remove YAML anchors (&name) from every named sampler definition.
    Anchors on variables blocks or other non-sampler entries are left alone.
    Returns list of anchor names that were removed.
    """
    removed = []
    samplers = data.get("samplers", {})
    if isinstance(samplers, CommentedMap):
        for name, val in samplers.items():
            if isinstance(val, CommentedMap):
                anchor = getattr(val, "anchor", None)
                if anchor and anchor.value:
                    removed.append(anchor.value)
                    anchor.value = None
    return removed


def replace_aliases(data, named_sampler_ids, definition_sites, rel_path):
    """
    Walk the file tree and replace every alias to a named sampler with an
    explicit cross-file string reference.
    Returns list of (key, new_ref_string) replacements made.
    """
    replacements = []

    def on_alias(parent, key, _val, sampler_name):
        ref = f"${rel_path}:samplers.{sampler_name}"
        parent[key] = ref
        replacements.append((key, ref))

    walk_tree(data, None, None, named_sampler_ids, definition_sites, on_alias)
    return replacements


def remove_unused_samplers(data, all_usage_counts, named_sampler_ids):
    """
    Remove named samplers that have zero usages across all counted sources
    (alias references, stage expression calls, and sampler-file text refs).

    Skips keys that are not named samplers (e.g. 'variables' blocks).
    Returns list of sampler names that were removed.
    """
    samplers = data.get("samplers", {})
    removed = []

    if not isinstance(samplers, CommentedMap):
        return removed

    # Only consider keys that were identified as named samplers
    sampler_names_in_file = set(named_sampler_ids.values())

    for name in list(samplers.keys()):
        if name not in sampler_names_in_file:
            continue  # not a sampler (e.g. variables block)
        if all_usage_counts.get(name, 0) == 0:
            del samplers[name]
            removed.append(name)

    return removed


def unwrap_underused_cache_samplers(data, combined_counts):
    """
    Remove CACHE wrappers from samplers that do not exceed the usage threshold.
    For each CACHE sampler with combined_counts[name] <= CACHE_THRESHOLD,
    replace it with its inner sampler definition.
    Returns list of unwrapped sampler names.
    """
    samplers = data.get("samplers", {})
    unwrapped = []

    if not isinstance(samplers, CommentedMap):
        return unwrapped

    for name in list(samplers.keys()):
        sampler_def = samplers[name]
        if not isinstance(sampler_def, CommentedMap):
            continue

        # Only process CACHE samplers
        if sampler_def.get("type") != "CACHE":
            continue

        # Check if it exceeds threshold
        if combined_counts.get(name, 0) > CACHE_THRESHOLD:
            continue  # Keep this CACHE sampler

        # Unwrap: replace with the inner sampler
        inner_sampler = sampler_def.get("sampler")
        if inner_sampler is not None:
            # If the inner sampler doesn't have dimensions, use the CACHE wrapper's dimensions
            if isinstance(inner_sampler, CommentedMap):
                if "dimensions" not in inner_sampler:
                    inner_sampler["dimensions"] = sampler_def.get("dimensions", 2)
            samplers[name] = inner_sampler
            unwrapped.append(name)

    return unwrapped


def update_existing_cache_samplers(data, pipeline_resolution):
    """
    Update all existing CACHE samplers to the new Terra API format:
    - Remove 'exp' field (use Terra dimension defaults)
    - Set 'int' to true
    - Set 'resolution' to pipeline_resolution
    Returns list of updated sampler names.
    """
    samplers = data.get("samplers", {})
    updated = []

    if not isinstance(samplers, CommentedMap):
        return updated

    for name, sampler_def in samplers.items():
        if not isinstance(sampler_def, CommentedMap):
            continue

        if sampler_def.get("type") != "CACHE":
            continue

        # Remove exp field if present
        if "exp" in sampler_def:
            del sampler_def["exp"]

        # Set new fields
        sampler_def["int"] = True
        sampler_def["resolution"] = pipeline_resolution
        updated.append(name)

    return updated


def apply_cache_wrapping(data, usage_counts, pipeline_resolution):
    """
    For each named sampler used more than CACHE_THRESHOLD times (across all
    files), wrap its definition in a CACHE sampler with int: true and
    resolution: pipeline_resolution. Skips samplers whose top-level type is
    already CACHE (they are handled by update_existing_cache_samplers).
    Returns list of sampler names that were wrapped.
    """
    samplers = data.get("samplers", {})
    wrapped = []

    if not isinstance(samplers, CommentedMap):
        return wrapped

    for name in list(samplers.keys()):
        if usage_counts.get(name, 0) <= CACHE_THRESHOLD:
            continue

        original = samplers[name]
        if not isinstance(original, CommentedMap):
            continue

        # Skip if already a CACHE sampler (will be handled by update_existing_cache_samplers)
        if original.get("type") == "CACHE":
            print(f"    (skipping {name!r}: already CACHE)")
            continue

        # Skip DENDRY samplers — they inherently cache values
        if original.get("type") == "DENDRY":
            print(f"    (skipping {name!r}: DENDRY inherently caches)")
            continue

        dims = original.get("dimensions", 2)

        cache_wrapper = CommentedMap()
        cache_wrapper["dimensions"] = dims
        cache_wrapper["type"] = "CACHE"
        cache_wrapper["int"] = True
        cache_wrapper["resolution"] = pipeline_resolution
        cache_wrapper["sampler"] = original

        samplers[name] = cache_wrapper
        wrapped.append(name)

    return wrapped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Pack root : {PACK_ROOT}")
    print(f"Pack file : {PACK_YML}")

    pipeline_resolution = discover_pipeline_resolution()
    print(f"Pipeline resolution: {pipeline_resolution}")

    sampler_files = discover_sampler_files()
    if not sampler_files:
        print("No sampler files found in pack.yml. Exiting.")
        return

    print(f"\nFound {len(sampler_files)} sampler file(s):")
    for rel, _ in sampler_files:
        print(f"  {rel}")

    # ------------------------------------------------------------------
    # Pass 1 — parse every file and count alias usages
    # ------------------------------------------------------------------
    print("\n--- Pass 1: cataloging named samplers and counting alias usages ---")

    file_data = {}        # rel_path -> parsed CommentedMap
    file_named_ids = {}   # rel_path -> {object_id: sampler_name}
    file_def_sites = {}   # rel_path -> set of (parent_id, key)
    usage_counts: Counter = Counter()

    for rel_path, abs_path in sampler_files:
        if not abs_path.exists():
            print(f"  WARNING: {abs_path} not found — skipping.")
            continue

        data = load_yaml(abs_path)
        named_ids = get_named_sampler_ids(data)
        def_sites = get_definition_sites(data)

        file_data[rel_path] = data
        file_named_ids[rel_path] = named_ids
        file_def_sites[rel_path] = def_sites

        count_usages_in_file(data, named_ids, def_sites, usage_counts)
        print(f"  {rel_path}: {len(named_ids)} named sampler(s)")

    # Collect all pack-level sampler names for stage scanning
    all_sampler_names = set()
    for named_ids in file_named_ids.values():
        all_sampler_names.update(named_ids.values())

    if usage_counts:
        print("\n  Alias usage counts (within sampler files):")
        for name, count in sorted(usage_counts.items(), key=lambda x: -x[1]):
            print(f"    {name}: {count}")

    # ------------------------------------------------------------------
    # Pass 1b — count usages in biome-distribution stage files
    # ------------------------------------------------------------------
    print("\n--- Pass 1b: counting usages in biome-distribution stages ---")
    stage_counts: Counter = Counter()
    stage_total = count_stage_usages(all_sampler_names, stage_counts)

    if stage_counts:
        print(f"\n  Stage usage counts ({stage_total} references found):")
        for name, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            print(f"    {name}: {count}")
    else:
        print("\n  No stage references to pack-level samplers found.")

    # ------------------------------------------------------------------
    # Pass 1c — count usages in biome/feature definition files
    # ------------------------------------------------------------------
    print("\n--- Pass 1c: counting usages in biome & feature definitions ---")
    biome_counts: Counter = Counter()
    biome_total = count_biome_usages(all_sampler_names, biome_counts)

    if biome_counts:
        print(f"\n  Biome/feature usage counts ({biome_total} references found):")
        for name, count in sorted(biome_counts.items(), key=lambda x: -x[1]):
            print(f"    {name}: {count}")
    else:
        print("\n  No biome/feature references to pack-level samplers found.")

    # ------------------------------------------------------------------
    # Pass 1d — count text-based usages within sampler files
    # ------------------------------------------------------------------
    print("\n--- Pass 1d: counting expression/ref usages within sampler files ---")
    sampler_text_counts: Counter = Counter()
    sampler_text_total = count_sampler_text_usages(
        sampler_files, all_sampler_names, sampler_text_counts
    )

    if sampler_text_counts:
        print(f"\n  Sampler-file text usage counts ({sampler_text_total} references found):")
        for name, count in sorted(sampler_text_counts.items(), key=lambda x: -x[1]):
            print(f"    {name}: {count}")
    else:
        print("\n  No text-based references within sampler files found.")

    # ------------------------------------------------------------------
    # Pass 1e — count usages in .tesf structure script files
    # ------------------------------------------------------------------
    print("\n--- Pass 1e: counting usages in .tesf structure scripts ---")
    tesf_counts: Counter = Counter()
    tesf_total = count_tesf_usages(all_sampler_names, tesf_counts)

    if tesf_counts:
        print(f"\n  .tesf usage counts ({tesf_total} references found):")
        for name, count in sorted(tesf_counts.items(), key=lambda x: -x[1]):
            print(f"    {name}: {count}")
    else:
        print("\n  No .tesf references to pack-level samplers found.")

    # Combine counts for CACHE decisions (alias + stage + biome)
    # Note: tesf counts are excluded — tesf scripts run rarely and don't
    # benefit from caching.
    combined_counts: Counter = Counter()
    combined_counts.update(usage_counts)
    combined_counts.update(stage_counts)
    combined_counts.update(biome_counts)

    # All-source counts for unused detection (all sources including tesf)
    all_source_counts: Counter = Counter()
    all_source_counts.update(usage_counts)
    all_source_counts.update(stage_counts)
    all_source_counts.update(biome_counts)
    all_source_counts.update(sampler_text_counts)
    all_source_counts.update(tesf_counts)

    if all_source_counts:
        print("\n  All-source usage counts (alias + stage + biome + sampler-text + tesf):")
        for name, count in sorted(all_source_counts.items(), key=lambda x: -x[1]):
            parts = []
            if usage_counts.get(name, 0):
                parts.append(f"{usage_counts[name]} alias")
            if stage_counts.get(name, 0):
                parts.append(f"{stage_counts[name]} stage")
            if biome_counts.get(name, 0):
                parts.append(f"{biome_counts[name]} biome")
            if sampler_text_counts.get(name, 0):
                parts.append(f"{sampler_text_counts[name]} text")
            if tesf_counts.get(name, 0):
                parts.append(f"{tesf_counts[name]} tesf")
            detail = " + ".join(parts)
            cache_flag = f"  <- will CACHE" if combined_counts.get(name, 0) > CACHE_THRESHOLD else ""
            unused_flag = "  <- UNUSED (will remove)" if count == 0 else ""
            print(f"    {name}: {count} ({detail}){cache_flag}{unused_flag}")

        # Report any samplers with zero usages that aren't in the counter
        all_names_with_zero = all_sampler_names - set(all_source_counts.keys())
        for name in sorted(all_names_with_zero):
            print(f"    {name}: 0  <- UNUSED (will remove)")
    else:
        print("\n  No usages found.")

    # ------------------------------------------------------------------
    # Write usage CSV
    # ------------------------------------------------------------------
    csv_path = PACK_ROOT / "sampler_usage.csv"
    write_usage_csv(all_sampler_names, stage_counts, biome_counts, usage_counts,
                    combined_counts, csv_path)

    # ------------------------------------------------------------------
    # Pass 2 — apply transformations
    # ------------------------------------------------------------------
    print("\n--- Pass 2: applying transformations ---")

    for rel_path, abs_path in sampler_files:
        if rel_path not in file_data:
            continue  # was skipped above

        data = file_data[rel_path]
        named_ids = file_named_ids[rel_path]
        def_sites = file_def_sites[rel_path]

        print(f"\n  {rel_path}:")

        # Step A — remove unused samplers
        removed_unused = remove_unused_samplers(data, all_source_counts, named_ids)
        if removed_unused:
            print(f"    Unused samplers removed: {removed_unused}")

        # Step B — remove anchors from remaining named samplers
        removed = remove_anchors(data)
        if removed:
            print(f"    Anchors removed: {removed}")

        # Step C — replace aliases with cross-file refs
        replacements = replace_aliases(data, named_ids, def_sites, rel_path)
        if replacements:
            for key, ref in replacements:
                print(f"    Alias replaced: {key!r}  ->  {ref}")

        # Step D — unwrap CACHE samplers below threshold
        unwrapped = unwrap_underused_cache_samplers(data, combined_counts)
        if unwrapped:
            print(f"    CACHE unwrapped (below threshold): {unwrapped}")

        # Step E — update existing CACHE samplers to new format
        updated_caches = update_existing_cache_samplers(data, pipeline_resolution)
        if updated_caches:
            print(f"    CACHE samplers updated (int=true, resolution={pipeline_resolution}): {updated_caches}")

        # Step F — wrap heavily-used samplers in CACHE
        wrapped = apply_cache_wrapping(data, combined_counts, pipeline_resolution)
        if wrapped:
            print(f"    CACHE wrapped (int=true, resolution={pipeline_resolution}): {wrapped}")

        if not removed_unused and not removed and not replacements and not unwrapped and not updated_caches and not wrapped:
            print("    No changes needed.")

        # Write back
        save_yaml(data, abs_path)
        print(f"    Saved -> {abs_path}")

    print("\nDone.")


if __name__ == "__main__":
    main()
