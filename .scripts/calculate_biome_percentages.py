#!/usr/bin/env python3
"""
calculate_biome_percentages.py

PURPOSE
-------
Trace the Terra biome pipeline for each preset in biome-distribution/presets/ and produce
a CSV with:
  - Per-biome percentage in each preset (surface biomes sum to 100%; extrusion biomes separate).
  - Expected temperature, precipitation, elevation (0-1) for each biome, derived from the
    pipeline stage distributions.  For biomes not processed by a named-sampler stage, the
    global mean of that sampler is used (0.5 for uniform distributions).

PIPELINE MODEL
--------------
Terra's ProbabilityCollection maps a sampler value to a biome slot via:
    index = clamp(int(((v + 1) / 2) * arraySize), 0, arraySize - 1)
where arraySize = sum of all weights.  Sampler output range is assumed [-1, 1].
Probability of biome B = integral of the sampler's PDF over the slice of [-1, 1]
assigned to B's weight slots.  For uniform samplers this reduces to weight/total.

NAMED CLIMATE SAMPLERS
-----------------------
Only three EXPRESSION sampler calls produce values tracked in the output CSV:
  - temperature(x, z)    → Temperature column
  - precipitation(x, z)  → Precipitation column
  - elevation(x, z)      → Elevation column
These names are configuration constants below (TEMPERATURE_SAMPLER_NAME, etc.).

DISTRIBUTION CATEGORIES
-----------------------
Biomes are tagged into a distribution category:
  SURFACE    — normal terrain from standard pipeline stages
  RIVER      — biomes produced by river REPLACE stages (from-biome matches RIVER_STAGE_TAGS)
  SUBSURFACE — cave/extrusion biomes (tracked separately, not in surface totals)

SAMPLER DISTRIBUTION CONFIG
----------------------------
sampler_distributions.yml (same directory) defines the CDF of each base sampler type.
Used by SamplerDistribution to compute slot-range integrals.
Re-generate with: python .scripts/extract_sampler_cdfs.py

BORDER STAGE MODEL
------------------
BORDER stages convert a fraction of the replace biome that neighbours the from biome.
The conversion fraction is estimated geometrically:
    border_fraction = min(BORDER_MAX_FRACTION, sqrt(from_prob) * BORDER_SCALE_FACTOR)

MAGIC IDENTIFIERS (implementation-specific — edit if pack changes)
-------------------------------------------------------------------
See the "PACK-SPECIFIC IDENTIFIERS" section below.
"""
from ensure_module import ensure_modules

ensure_modules(["yaml", "re", "csv"])

import yaml
import re
import sys
import csv
import math
from enum import Enum
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Any, Optional, Set

# Shared CDF / sampler resolution machinery
from sampler_cdf import (
    SAMPLER_DIST_CONFIG,
    RESOLVED_SAMPLERS_PATH,
    SamplerDistribution,
    NumericalCDF,
    PackSamplerRegistry,
    resolve_sampler_cdf,
    compute_slot_probabilities,
    register_sampler_point_masses,
    leaf_overrides,
    get_sampler_dist as _get_sampler_dist,
    get_pack_registry as _get_pack_registry,
)

# =============================================================================
# NAMED CLIMATE SAMPLERS  (edit if pack renames these expression functions)
# =============================================================================
TEMPERATURE_SAMPLER_NAME   = "temperature"
PRECIPITATION_SAMPLER_NAME = "precipitation"
ELEVATION_SAMPLER_NAME     = "elevation"

# =============================================================================
# ELEVATION DETECTION KEYWORDS (for terrain.sampler-2d)
# =============================================================================
ELEVATION_KEYWORDS = [
    "spotBaseElevation",
    "elevationDetailed",
    "elevation",
    "oceanElevation",
    "BiomeShapeLandmassBaseOffset",  # wraps elevationDetailed internally
]

# =============================================================================
# DISTRIBUTION CATEGORY RULES  (edit if pack structure changes)
# =============================================================================
# Tags on the 'from' biome that indicate a river replacement stage
RIVER_STAGE_TAGS: Set[str] = {
    "USE_RIVER", "USE_DESERT_RIVER", "USE_FROZEN_RIVER",
    "USE_FROZEN_RIVER_FROZEN_MARSH", "USE_COLD_RIVER",
}

# =============================================================================
# BORDER STAGE MODEL CONSTANTS
# =============================================================================
# Terra's BORDER stages (see BorderStage.java) replace a center cell that
# carries the ``replace`` tag whenever any of its 8 immediate neighbours carries
# the ``from`` tag.  The geometrically-driven fraction of replace cells that
# are actually converted is approximated by:
#
#     border_frac = min(BORDER_MAX_FRACTION,
#                       BORDER_SCALE_FACTOR * sqrt(p_from_tag))
#
# where ``p_from_tag`` is the summed probability of all biomes carrying the
# ``from`` (neighbour) tag in the current distribution.  Square-root scaling
# models perimeter-to-area ratios for spatially-correlated biome patches.  The
# constants are tunable; ``.scripts/calibrate_border.py`` sweeps them against
# ``benchmark_CHIMERA.csv``.
BORDER_SCALE_FACTOR = 0.08
BORDER_MAX_FRACTION = 0.05


def _border_fraction(from_total_prob: float) -> float:
    """
    Fraction of a ``replace``-tag biome that gets converted to border biomes,
    given the total probability mass of ``from``-tag (neighbour-trigger) biomes
    in the current distribution.  See BORDER_SCALE_FACTOR / BORDER_MAX_FRACTION.
    """
    if from_total_prob <= 0:
        return 0.0
    return min(BORDER_MAX_FRACTION,
               BORDER_SCALE_FACTOR * math.sqrt(from_total_prob))

# =============================================================================
# SPATIAL-GATE COVERAGE OVERRIDES  (pack-specific, calibrated to benchmark)
# =============================================================================
# Several pipeline stages gate a biome on a spatial field the generic CDF
# resolver cannot evaluate (DENDRY river networks, cellular rift zones, coast /
# spot distance fields).  Left to the uniform fallback the resolver hands the
# gated biome ~weight/total of its source, so it over-counts coverage by an
# order of magnitude (rivers 29% vs 4.6% measured, sinkholes 9% vs 1%).
#
# For each such named sampler we register the real output distribution as a set
# of ``(value, probability)`` point masses (see sampler_cdf.from_point_masses).
# Terra maps a sampler value v∈[-1,1] to a slot, so the value's POSITION sets
# WHICH slot the mass lands in and the probability sets HOW MUCH.  Place each
# value strictly inside its intended slot (avoid exact slot boundaries).
#
# These fractions are calibrated against benchmark_CHIMERA.csv (a very large but
# finite-area solve).  The river network is a 1-D channel over a 2-D area, so
# its areal coverage is small and roughly width/spacing; the rift/coast/spot
# gates likewise expose only a thin fraction of the land they pass over.

# Only TWO sampler families genuinely cannot be derived from the expression set
# and so keep an empirical coverage override:
#   1. the DENDRY river network (riverSampler and the rift gates that read the
#      river-distance field), and
#   2. the CELLULAR spot placer (spotPlacer / spotDistance), a Voronoi-cell
#      stamping whose areal rate is a cellular-geometry constant.
# Everything else (mesa, island, coast, …) is now DERIVED from its actual
# expression + variables + leaf-noise CDFs, conditioned on the stage's land/ocean
# region (see _RegionConditioner below).  These few constants are the only
# values that go stale if the underlying noise is retuned.

# Fraction of a river-eligible cell that the DENDRY river network actually
# covers (riverSampler returns +1) and the surrounding wetland/border band
# (returns -0.25); riverSampler returns -1 (no river) elsewhere.  Calibrated so
# total river-biome surface ≈ 4.6% (benchmark) vs 29% at nominal 50% weights.
RIVER_COVERAGE_FRACTION = 0.072
RIVER_BORDER_FRACTION   = 0.025

# Rift gates read ``continentalRiverDistSparseFarGrid`` (a DENDRY river-distance
# field) so they inherit the same non-derivable status as rivers.  Fractions:
# land flagged into the canyon/sinkhole system, and the floor-biome fraction
# inside an active canyon / well zone.
RIFT_LAND_FRACTION   = 0.10
RIFT_CANYON_FLOOR    = 0.36   # nominal SANDY_SPLITS/ICY_INCISIONS weight 9/(16+9)
RIFT_WELL_FLOOR      = 0.30   # nominal SINKHOLE weight 1/(1+1)

# Spot feature areal coverage (CELLULAR Voronoi stamping).  The pipeline source
# weights _land_spot / _ocean_spot at 1/22 each, but the gating sampler
# ``spotPlacer`` ignores those weights (per the preset comment) and stamps spots
# at its own sparse cellular rate.
SPOT_LAND_FRACTION  = 0.008
SPOT_OCEAN_FRACTION = 0.006


def _register_coverage_overrides() -> None:
    """
    Register the only non-derivable spatial-gate coverage overrides as point-mass
    output distributions for their named pack samplers (DENDRY rivers/rifts and
    the CELLULAR spot placer).  Called once at import.
    """
    f, b = RIVER_COVERAGE_FRACTION, RIVER_BORDER_FRACTION
    # riverSampler: +1 river, -0.25 border band, -1 no-river.  Values placed
    # inside their slots; for a [SELF:1, RIVER:1] list (boundary at v=0) RIVER
    # gets the +1 mass (=f) and SELF gets the rest.
    register_sampler_point_masses("riverSampler", [
        (0.97, f), (-0.25, b), (-0.97, 1.0 - f - b),
    ])

    # riftLandDistributor: [land:1, _rift_land:1] (boundary v=0) → _rift_land
    # gets the +v mass.
    register_sampler_point_masses("riftLandDistributor", [
        (0.5, RIFT_LAND_FRACTION), (-0.5, 1.0 - RIFT_LAND_FRACTION),
    ])
    # riftCanyon: [land:16, FLOOR:9] (boundary v = -1 + 2*16/25 = 0.28) → FLOOR
    # (inner) is the high-v slot.
    register_sampler_point_masses("riftCanyon", [
        (0.7, RIFT_CANYON_FLOOR), (-0.5, 1.0 - RIFT_CANYON_FLOOR),
    ])
    # riftWellPlacement: [land:1, SINKHOLE:1] (boundary v=0) → SINKHOLE high-v.
    register_sampler_point_masses("riftWellPlacement", [
        (0.5, RIFT_WELL_FLOOR), (-0.5, 1.0 - RIFT_WELL_FLOOR),
    ])

    # spotPlacer: gates the pipeline source [_ocean_spot:1, _non_spot:20,
    # _land_spot:1] (array size 22).  Slot order matches YAML: _ocean_spot in the
    # low-v slot, _non_spot in the middle, _land_spot in the high-v slot.
    register_sampler_point_masses("spotPlacer", [
        (-0.95, SPOT_OCEAN_FRACTION),
        (0.0,   1.0 - SPOT_OCEAN_FRACTION - SPOT_LAND_FRACTION),
        (0.95,  SPOT_LAND_FRACTION),
    ])


_register_coverage_overrides()


# =============================================================================
# PACK VARIABLE REFERENCE RESOLUTION
# =============================================================================
# Stage samplers reference tunables from other pack files as ``$file.yml:key``
# or ``${file.yml:key}`` (keys may be dotted paths), e.g. the coast gate tests
# ``dist2Coast(x,z) < $customization.yml:continental-coast-cutoff``.  Until these
# resolve to numbers the CDF resolver can't evaluate the comparison and falls
# back to uniform, over-counting the gated biome.  We substitute the numeric
# value (only numeric leaves are substituted; non-numeric refs are left as-is).
_PACK_YAML_CACHE: Dict[str, Any] = {}
_PACK_REF_RE = re.compile(r'\$\{?\s*([A-Za-z0-9_./-]+\.yml)\s*:\s*([A-Za-z0-9_.\-]+)\s*\}?')


def _load_pack_yaml(fname: str) -> Any:
    if fname not in _PACK_YAML_CACHE:
        try:
            with open(fname, 'r', encoding='utf-8') as f:
                _PACK_YAML_CACHE[fname] = yaml.safe_load(f)
        except Exception:
            _PACK_YAML_CACHE[fname] = {}
    return _PACK_YAML_CACHE[fname]


def _lookup_pack_ref(fname: str, keypath: str) -> Optional[float]:
    data = _load_pack_yaml(fname)
    for key in keypath.split('.'):
        if isinstance(data, dict) and key in data:
            data = data[key]
        else:
            return None
    return float(data) if isinstance(data, (int, float)) and not isinstance(data, bool) else None


def _resolve_pack_refs(obj: Any) -> Any:
    """Recursively substitute numeric ``$file.yml:key`` references in a config tree."""
    if isinstance(obj, dict):
        return {k: _resolve_pack_refs(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_resolve_pack_refs(v) for v in obj]
    if isinstance(obj, str):
        m = _PACK_REF_RE.fullmatch(obj.strip())
        if m:
            val = _lookup_pack_ref(m.group(1), m.group(2))
            if val is not None:
                return val
            return obj
        # Inline reference inside a larger expression — substitute in place.
        def _repl(mm: "re.Match") -> str:
            val = _lookup_pack_ref(mm.group(1), mm.group(2))
            return f'({val})' if val is not None else mm.group(0)
        return _PACK_REF_RE.sub(_repl, obj)
    return obj


# =============================================================================
# REGION-CONDITIONAL GATE RESOLUTION (spatial-correlation model)
# =============================================================================
# A gate such as ``if(mesaPresent(x,z)>0,1,-1)`` or the coast band runs only on
# the LAND (or OCEAN) region, but its gating field is the continental noise that
# *defines* that region.  Evaluated over the whole map the marginal coverage is
# far too high (island 8% vs ~0.4%); conditioned on land it is correct.
#
# We restrict each continental-family leaf to its land/ocean portion (the top
# ``land_fraction`` quantile is land, the rest ocean — land_fraction itself is
# derived from the continentalDistribution split) and resolve the gate with those
# leaves overridden.  Whether a stage's sampler actually depends on the
# continental field is auto-detected (resolve with vs. without the override),
# so nothing is hard-coded about which samplers are continental.
_CONTINENTAL_LEAVES = [
    "continents", "continental_sampler", "continental_landmass",
    "continentsWithSpots",
]

_REGION_STATE: Dict[str, Any] = {"init": False, "Land": None, "Ocean": None}
_CONT_DEP_CACHE: Dict[int, bool] = {}
_REGION_SLOT_MEMO: Dict[Tuple[int, Tuple[int, ...], str], List[float]] = {}


def _ensure_region_overrides() -> None:
    """Build the land/ocean-conditional continental leaf CDFs once."""
    if _REGION_STATE["init"]:
        return
    _REGION_STATE["init"] = True
    reg = _get_pack_registry()
    cont = reg.get_config("continentalDistribution")
    try:
        land_frac = _compute_slot_probabilities(cont, [1, 1])[1] if cont else 0.5
    except Exception:
        land_frac = 0.5
    land_ov: Dict[str, NumericalCDF] = {}
    ocean_ov: Dict[str, NumericalCDF] = {}
    for nm in _CONTINENTAL_LEAVES:
        c = reg.get_cdf(nm)
        if c is None:
            continue
        q = c.quantile(1.0 - land_frac)   # land = top land_frac quantile
        land_ov[nm] = c.condition_range(q, NumericalCDF.HI)
        ocean_ov[nm] = c.condition_range(NumericalCDF.LO, q)
    _REGION_STATE["Land"] = land_ov or None
    _REGION_STATE["Ocean"] = ocean_ov or None


def _region_of(distribution: "BiomeDistribution", biome: str) -> Optional[str]:
    """Return 'Land' / 'Ocean' / None for a from-biome (origin first, then source sets)."""
    origin = distribution.get_origin(biome)
    if origin in ("Land", "Ocean"):
        return origin
    low = biome.lower()
    if low in LAND_SOURCE_BIOMES:
        return "Land"
    if low in OCEAN_SOURCE_BIOMES:
        return "Ocean"
    return None


def _mean(cdf: NumericalCDF) -> float:
    return sum((cdf.cdf[i + 1] - cdf.cdf[i]) * cdf._val(i) for i in range(cdf.BINS))


def _is_continental_dependent(sampler_config: Any) -> bool:
    """Auto-detect whether a sampler's resolved distribution shifts under the
    land-region continental override (i.e. it gates on the continental field)."""
    if not isinstance(sampler_config, dict) or not sampler_config:
        return False
    sid = id(sampler_config)
    if sid in _CONT_DEP_CACHE:
        return _CONT_DEP_CACHE[sid]
    _ensure_region_overrides()
    ov = _REGION_STATE["Land"]
    dep = False
    if ov:
        try:
            sd, reg = _get_sampler_dist(), _get_pack_registry()
            base = resolve_sampler_cdf(sampler_config, sd, reg)
            with leaf_overrides(ov):
                test = resolve_sampler_cdf(sampler_config, sd, reg)
            dep = abs(_mean(base) - _mean(test)) > 1e-4
        except Exception:
            dep = False
    _CONT_DEP_CACHE[sid] = dep
    return dep


def _region_slot_probs(sampler_config: Any, weights: List[int],
                       region: Optional[str]) -> List[float]:
    """Slot probabilities for a weighted list, conditioned on the from-biome's
    land/ocean region when the gating sampler is continental-dependent."""
    if region in ("Land", "Ocean") and _is_continental_dependent(sampler_config):
        ov = _region_overrides_for(region)
        if ov:
            key = (id(sampler_config), tuple(weights), region)
            cached = _REGION_SLOT_MEMO.get(key)
            if cached is not None:
                return cached
            with leaf_overrides(ov):
                p = _compute_slot_probabilities(sampler_config, weights)
            _REGION_SLOT_MEMO[key] = p
            return p
    return _compute_slot_probabilities(sampler_config, weights)


def _region_overrides_for(region: str) -> Optional[Dict[str, NumericalCDF]]:
    _ensure_region_overrides()
    return _REGION_STATE.get(region)


# =============================================================================
# CLIMATE DATA PRESET  (edit if the main climate-stages preset changes)
# =============================================================================
# The preset used to derive temperature/precipitation/elevation values.
# This should be the preset that runs the full climate pipeline
# (temperature.yml → precipitation.yml → elevation.yml → set_biomes_in_climates.yml).
# It may differ from the pack's active preset (pack.yml:biomes).
CLIMATE_PRESET_NAME = "CHIMERA"

# =============================================================================
# PACK-SPECIFIC IDENTIFIERS  (may break on other packs without updating these)
# =============================================================================
OCEAN_SOURCE_BIOMES: Set[str] = {"ocean", "deep-ocean", "shallow-ocean"}
LAND_SOURCE_BIOMES: Set[str]  = {
    "land", "coast", "mesa", "crater-lake",
    "extinct-volcano", "island", "vast-forest",
}

# =============================================================================
# ELEVATION FLAT REGION DETECTION
# =============================================================================
# Paths to the elevation and downstream biome-assignment stage files
ELEVATION_STAGE_FILE      = Path("biome-distribution/stages/climate/elevation.yml")
SET_BIOMES_STAGE_FILES: List[Path] = [
    Path("biome-distribution/stages/set_biomes_in_climates.yml"),
    Path("biome-distribution/stages/set_biomes_in_climates_origen.yml"),
]


def _extract_slot0_biomes(stage: Dict) -> Set[str]:
    """Return all biome IDs that occupy slot 0 in a REPLACE_LIST stage's to-lists."""
    result: Set[str] = set()

    def _first_biome(weighted_list: List) -> None:
        if weighted_list and isinstance(weighted_list, list):
            first = weighted_list[0]
            if isinstance(first, dict):
                result.update(first.keys())

    _first_biome(stage.get('default-to', []))
    for to_list in stage.get('to', {}).values():
        _first_biome(to_list)

    return result


def _load_stage_file(path: Path) -> List[Dict]:
    """Load a stage YAML file and return its stages list, or [] on failure."""
    if not path.exists():
        print(f"Warning: stage file not found: {path}", file=sys.stderr)
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('stages', []) if data else []
    except Exception as e:
        print(f"Warning: could not parse {path}: {e}", file=sys.stderr)
        return []


def _build_elevation_flat_biomes() -> Set[str]:
    """
    Return the set of CONCRETE biome IDs that are distributed to the FLAT region
    of the land-elevation REPLACE_LIST in elevation.yml.

    Because the flat-slot biomes produced by elevation.yml (e.g. 'tundra-flat')
    are abstract intermediates, this function resolves them one stage further by
    parsing set_biomes_in_climates.yml and collecting every concrete biome that
    is produced from a flat intermediate.
    """
    # --- Step 1: collect flat intermediate IDs from elevation.yml ---
    flat_intermediates: Set[str] = set()
    for stage in _load_stage_file(ELEVATION_STAGE_FILE):
        if stage.get('type') != 'REPLACE_LIST':
            continue
        expr = stage.get('sampler', {}).get('expression', '')
        # The land-elevation stage calls elevation(x,z), not oceanElevation
        if 'elevation(x' not in expr or 'oceanElevation' in expr:
            continue
        flat_intermediates = _extract_slot0_biomes(stage)
        break  # Only one matching stage expected

    if not flat_intermediates:
        return set()

    # --- Step 2: resolve intermediates → concrete biomes via all set_biomes files ---
    concrete_flat: Set[str] = set()
    for stage_file in SET_BIOMES_STAGE_FILES:
        for stage in _load_stage_file(stage_file):
            if stage.get('type') not in ('REPLACE_LIST', 'REPLACE'):
                continue

            # default-from maps to default-to when the from-biome is a flat intermediate
            default_from = stage.get('default-from')
            if default_from in flat_intermediates:
                for item in stage.get('default-to', []):
                    if isinstance(item, dict):
                        concrete_flat.update(item.keys())

            # Each key in 'to' that is a flat intermediate maps to concrete biomes
            for from_key, to_list in stage.get('to', {}).items():
                if from_key not in flat_intermediates:
                    continue
                if isinstance(to_list, list):
                    for item in to_list:
                        if isinstance(item, dict):
                            concrete_flat.update(item.keys())
                elif isinstance(to_list, str):
                    concrete_flat.add(to_list)

    return concrete_flat


# =============================================================================
# Local helpers that wrap the shared sampler_cdf module
# =============================================================================

def _leaf_sampler_type(sampler: Any) -> str:
    """
    Walk a sampler config dict to find the innermost non-wrapper type.

    LEGACY helper — used only when NumericalCDF resolution is not needed
    (e.g., for quick type detection in climate stage identification).
    Prefer resolve_sampler_cdf() for probability computation.
    """
    _WRAPPERS = {"CACHE", "DOMAIN_WARP", "FBM", "CLAMP", "LINEAR", "LINEAR_MAP",
                 "NORMALIZER", "TRANSLATE"}
    if not isinstance(sampler, dict):
        return "uniform"
    t = sampler.get("type", "")
    if t in _WRAPPERS:
        inner = sampler.get("sampler")
        if inner:
            return _leaf_sampler_type(inner)
    if t == "CELLULAR" and sampler.get("return") == "CellValue":
        return "uniform"
    return t if t else "uniform"


# Convenience alias preserving the prior private name throughout this module.
_compute_slot_probabilities = compute_slot_probabilities



def _compute_climate_band_values(
    items: List[Tuple[str, int]],
    probs: List[float],
    sampler_config: Optional[Any] = None,
) -> Dict[str, float]:
    """
    Compute the expected climate value (0–1) for each biome in a weighted list.

    For a climate stage (temperature / precipitation / elevation), the sampler
    selects a slot in the weighted list.  The climate value for a biome is the
    expected sampler output (mapped to [0, 1]) over the slots assigned to that
    biome — i.e., E[V | V ∈ slot_range], NOT the slot midpoint.

    For non-uniform sampler distributions (FBM, Gaussian-like), the slot
    midpoint can be very different from the conditional mean.  When the
    sampler config is available we use its NumericalCDF to compute the true
    conditional mean; otherwise we fall back to the midpoint.
    """
    if not items:
        return {}

    array_size = sum(w for _, w in items)
    if array_size == 0:
        return {}

    # Resolve the sampler's CDF once; reuse for every slot.
    cdf: Optional[NumericalCDF] = None
    if sampler_config is not None:
        try:
            sd = _get_sampler_dist()
            pack_reg = _get_pack_registry()
            cdf = resolve_sampler_cdf(sampler_config, sd, pack_reg)
        except Exception:
            cdf = None

    cumulative = 0
    band_num: Dict[str, float] = {}
    band_den: Dict[str, float] = {}

    for (to_biome, w), p in zip(items, probs):
        if p <= 0 or w <= 0:
            cumulative += w
            continue
        v_start = -1.0 + 2.0 * cumulative / array_size
        v_end   = -1.0 + 2.0 * (cumulative + w) / array_size
        # E[V | V ∈ [v_start, v_end]] when CDF is known; otherwise midpoint.
        if cdf is not None:
            v_mean = cdf.conditional_mean(v_start, v_end)
        else:
            v_mean = (v_start + v_end) / 2.0
        # Map sampler space [-1, 1] → climate value [0, 1]
        band_val = max(0.0, min(1.0, (v_mean + 1.0) / 2.0))
        band_num[to_biome] = band_num.get(to_biome, 0.0) + band_val * p
        band_den[to_biome] = band_den.get(to_biome, 0.0) + p
        cumulative += w

    result: Dict[str, float] = {}
    for biome in band_den:
        if band_den[biome] > 0:
            result[biome] = max(0.0, min(1.0, band_num[biome] / band_den[biome]))
    return result


def _get_climate_sampler_name(stage: Dict) -> Optional[str]:
    """
    Return the named climate sampler called by this stage's EXPRESSION sampler,
    or None if this is not a climate stage.
    """
    sampler = stage.get("sampler", {})
    if not isinstance(sampler, dict):
        return None
    if sampler.get("type") == "EXPRESSION":
        expr = str(sampler.get("expression", ""))
        # Check for direct calls: temperature(x, z)
        for name in (TEMPERATURE_SAMPLER_NAME, PRECIPITATION_SAMPLER_NAME, ELEVATION_SAMPLER_NAME):
            if f"{name}(" in expr:
                return name
        # Check for wrapper functions: BiomeShapeLandmassTemperature, spotTemperature, etc.
        if "Temperature" in expr:
            return TEMPERATURE_SAMPLER_NAME
        if "Precipitation" in expr:
            return PRECIPITATION_SAMPLER_NAME
        if "Elevation" in expr or "elevation" in expr:
            return ELEVATION_SAMPLER_NAME
    return None


def _is_river_stage(stage: Dict) -> bool:
    """Return True if the 'from' tag indicates a river replacement stage.

    Matches any tag in RIVER_STAGE_TAGS OR any tag that starts with 'USE_'
    and contains 'RIVER' (covers USE_PALE_GARDEN_RIVER, USE_MUSHROOM_RIVER, etc.).
    """
    for key in ("from", "default-from"):
        val = stage.get(key, "")
        if isinstance(val, str):
            if val in RIVER_STAGE_TAGS:
                return True
            # Pattern match: USE_*_RIVER tags produced by the river stage file
            if val.startswith("USE_") and "RIVER" in val:
                return True
    return False


# Cached result of _rivers_disabled().
_RIVERS_DISABLED_CACHE: Optional[bool] = None


def _rivers_disabled() -> bool:
    """True when the pack's river DENDRY sampler is switched off (``n`` negative).

    The benchmark build disables rivers via ``math/samplers/rivers.yml`` by setting
    the river DENDRY sampler's ``n: -1`` (the river channel then produces nothing, so
    ``riverSampler`` always selects the SELF/no-river slot and no RIVER biomes are
    generated).  The predictor cannot evaluate the DENDRY semantics, so without this
    check it would model the river REPLACE stages at their nominal ``[SELF:1, RIVER:1]``
    weights (~25% of the surface as rivers) and under-count every land biome by that
    much.  Detecting the disable lets the predictor match the rivers-disabled benchmark.
    """
    global _RIVERS_DISABLED_CACHE
    if _RIVERS_DISABLED_CACHE is not None:
        return _RIVERS_DISABLED_CACHE
    result = False
    try:
        txt = Path("math/samplers/rivers.yml").read_text(encoding="utf-8")
        # Scan each DENDRY sampler block; a negative `n` means rivers are off.
        for m in re.finditer(r'type:\s*DENDRY(.*?)(?=\n\s*\w+:\s*\n|\Z)', txt, re.S):
            nm = re.search(r'^\s*n:\s*(-?\d+)', m.group(1), re.M)
            if nm and int(nm.group(1)) < 0:
                result = True
                break
    except Exception:
        result = False
    _RIVERS_DISABLED_CACHE = result
    return result


def _apply_climate_value(tracker: "ClimateTracker", sampler_name: str,
                         biome: str, value: float) -> None:
    """Write a pipeline-derived climate value into the climate tracker."""
    if sampler_name == TEMPERATURE_SAMPLER_NAME:
        tracker.apply_temperature_value(biome, value)
    elif sampler_name == PRECIPITATION_SAMPLER_NAME:
        tracker.apply_precipitation_value(biome, value)
    elif sampler_name == ELEVATION_SAMPLER_NAME:
        tracker.apply_elevation_value(biome, value)


def _propagate_climate(tracker: "ClimateTracker",
                       from_biome: str, to_biome: str) -> None:
    """
    Inherit climate context from from_biome to to_biome for any field not yet set.

    Called when a REPLACE/REPLACE_LIST stage transforms biome A into biome B
    so that B inherits A's temperature/precipitation/elevation values.
    Existing values on to_biome are preserved (pipeline values take precedence).
    """
    from_ctx = tracker.contexts.get(from_biome)
    if from_ctx is None:
        return
    to_ctx = tracker.contexts.get(to_biome, ClimateContext())
    changed = False
    if to_ctx.temperature is None and from_ctx.temperature is not None:
        to_ctx.temperature = from_ctx.temperature
        changed = True
    if to_ctx.precipitation is None and from_ctx.precipitation is not None:
        to_ctx.precipitation = from_ctx.precipitation
        changed = True
    if to_ctx.elevation is None and from_ctx.elevation is not None:
        to_ctx.elevation = from_ctx.elevation
        changed = True
    if to_ctx.origin_type is None and from_ctx.origin_type is not None:
        to_ctx.origin_type = from_ctx.origin_type
        changed = True
    if changed:
        tracker.contexts[to_biome] = to_ctx


# =============================================================================
# Distribution Category
# =============================================================================

class DistributionCategory(Enum):
    SURFACE    = "SURFACE"
    RIVER      = "RIVER"
    SUBSURFACE = "SUBSURFACE"


# =============================================================================
# Terra Schema Validation
# =============================================================================

class TerraSchemaValidator:
    """
    Validates Terra configuration files against known schema.

    Based on Terra 7.0 source code:
    - Stage types from biome-provider-pipeline addon
    - Sampler types from noise addon
    """

    # Valid pipeline stage types and their required fields
    STAGE_TYPES = {
        'REPLACE': {
            'required': ['from', 'to'],
            'optional': ['sampler', 'range'],
        },
        'REPLACE_LIST': {
            'required': ['default-from', 'default-to', 'to'],
            'optional': ['sampler', 'range'],
        },
        'BORDER': {
            'required': ['from', 'replace', 'to'],
            'optional': ['sampler'],
        },
        'BORDER_LIST': {
            'required': ['from', 'default-replace', 'default-to', 'replace'],
            'optional': ['sampler'],
        },
        'SMOOTH': {
            'required': [],
            'optional': ['sampler'],
        },
        'FRACTAL_EXPAND': {
            'required': [],
            'optional': ['sampler'],
        },
    }

    # Valid sampler types
    SAMPLER_TYPES = {
        'CELLULAR', 'CONSTANT', 'DOMAIN_WARP', 'EXPRESSION',
        'GAUSSIAN', 'IMAGE', 'KERNEL', 'LINEAR', 'NORMALIZER',
        'OPEN_SIMPLEX_2', 'OPEN_SIMPLEX_2S', 'PERLIN', 'PROBABILITY',
        'SIMPLEX', 'VALUE', 'VALUE_CUBIC', 'WHITE_NOISE',
        'DISTANCE', 'LINEAR_HEIGHTMAP', 'TRANSLATE', 'CLAMP',
        'ADD', 'SUB', 'MUL', 'DIV', 'MAX', 'MIN',
    }

    # Valid provider types
    PROVIDER_TYPES = {
        'PIPELINE', 'EXTRUSION', 'SINGLE', 'SAMPLER', 'IMAGE',
    }

    def __init__(self):
        self.errors: List[Tuple[str, str, str]] = []  # (file, location, message)
        self.warnings: List[Tuple[str, str, str]] = []
        # Track which stage files failed to load and which presets were affected
        self.failed_stage_files: Dict[str, List[str]] = defaultdict(list)  # file -> [presets]
        self.skipped_stages_by_preset: Dict[str, List[str]] = defaultdict(list)  # preset -> [files]

    def record_failed_stage_load(self, stage_file: str, preset_name: str):
        """Record that a stage file failed to load for a preset."""
        self.failed_stage_files[stage_file].append(preset_name)
        self.skipped_stages_by_preset[preset_name].append(stage_file)

    def validate_stage(self, stage: Dict, file_path: str, stage_index: int) -> bool:
        """Validate a single pipeline stage configuration."""
        if not isinstance(stage, dict):
            return True  # Skip non-dict stages (e.g., string references)

        stage_type = stage.get('type')
        location = f"stage[{stage_index}]"

        if not stage_type:
            self.errors.append((file_path, location, "Stage missing 'type' field"))
            return False

        if stage_type not in self.STAGE_TYPES:
            # Check for common typos
            similar = self._find_similar(stage_type, self.STAGE_TYPES.keys())
            msg = f"Invalid stage type '{stage_type}'"
            if similar:
                msg += f". Did you mean '{similar}'?"
            self.errors.append((file_path, location, msg))
            return False

        # Check required fields
        schema = self.STAGE_TYPES[stage_type]
        for field in schema['required']:
            if field not in stage:
                self.errors.append((
                    file_path, location,
                    f"Stage type '{stage_type}' missing required field '{field}'"
                ))

        # Validate nested sampler if present
        if 'sampler' in stage:
            self.validate_sampler(stage['sampler'], file_path, f"{location}.sampler")

        return True

    def validate_sampler(self, sampler: Any, file_path: str, location: str) -> bool:
        """Validate a sampler configuration."""
        if not isinstance(sampler, dict):
            return True

        sampler_type = sampler.get('type')
        if not sampler_type:
            # Sampler might be a reference or have implicit type
            return True

        if sampler_type not in self.SAMPLER_TYPES:
            similar = self._find_similar(sampler_type, self.SAMPLER_TYPES)
            msg = f"Unknown sampler type '{sampler_type}'"
            if similar:
                msg += f". Did you mean '{similar}'?"
            self.warnings.append((file_path, location, msg))

        # Recursively validate nested samplers
        for key in ['sampler', 'samplers', 'lookup']:
            if key in sampler:
                nested = sampler[key]
                if isinstance(nested, dict):
                    if 'type' in nested:
                        self.validate_sampler(nested, file_path, f"{location}.{key}")
                    else:
                        # Named samplers dict
                        for name, s in nested.items():
                            self.validate_sampler(s, file_path, f"{location}.{key}.{name}")

        return True

    def validate_anchors_and_aliases(self, file_path: Path) -> List[str]:
        """
        Pre-parse validation of YAML anchors and aliases.

        Checks:
        1. No anchor is defined more than once
        2. All aliases reference anchors that were defined earlier

        Returns list of error messages.
        """
        errors = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return [f"Could not read file: {e}"]

        lines = content.split('\n')

        # Track anchors: name -> (line_number, column)
        anchors_defined: Dict[str, Tuple[int, int]] = {}
        # Track aliases: name -> [(line_number, column), ...]
        aliases_used: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

        # Regex patterns for anchors and aliases
        # Anchor: &name (not preceded by *)
        anchor_pattern = re.compile(r'(?<!\*)&([a-zA-Z_][a-zA-Z0-9_]*)')
        # Alias: *name
        alias_pattern = re.compile(r'\*([a-zA-Z_][a-zA-Z0-9_]*)')

        for line_num, line in enumerate(lines, start=1):
            # Skip comments
            line_content = line.split('#')[0] if '#' in line else line

            # Find anchors
            for match in anchor_pattern.finditer(line_content):
                anchor_name = match.group(1)
                col = match.start() + 1

                if anchor_name in anchors_defined:
                    first_line, first_col = anchors_defined[anchor_name]
                    errors.append(
                        f"Line {line_num}: Duplicate anchor '&{anchor_name}' "
                        f"(first defined at line {first_line}). "
                        f"Use alias '*{anchor_name}' to reference it instead."
                    )
                else:
                    anchors_defined[anchor_name] = (line_num, col)

            # Find aliases
            for match in alias_pattern.finditer(line_content):
                alias_name = match.group(1)
                col = match.start() + 1
                aliases_used[alias_name].append((line_num, col))

        # Check for undefined aliases
        for alias_name, usages in aliases_used.items():
            if alias_name not in anchors_defined:
                for line_num, col in usages:
                    errors.append(
                        f"Line {line_num}: Alias '*{alias_name}' references undefined anchor. "
                        f"Define anchor '&{alias_name}' before using it."
                    )
            else:
                # Check that alias is used after anchor is defined
                anchor_line = anchors_defined[alias_name][0]
                for line_num, col in usages:
                    if line_num < anchor_line:
                        errors.append(
                            f"Line {line_num}: Alias '*{alias_name}' used before anchor is defined "
                            f"(anchor defined at line {anchor_line})."
                        )

        return errors

    def validate_yaml_file(self, file_path: Path) -> Tuple[Optional[Dict], List[str]]:
        """
        Load and validate a YAML file.
        Returns (parsed_data, errors) where errors is a list of error messages.
        """
        errors = []

        # Pre-parse validation for anchors and aliases
        anchor_errors = self.validate_anchors_and_aliases(file_path)
        if anchor_errors:
            errors.extend(anchor_errors)
            # Don't try to parse if we found anchor/alias issues
            return None, errors

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            return data, errors
        except yaml.YAMLError as e:
            # Extract meaningful error info
            error_str = str(e)
            if hasattr(e, 'problem_mark'):
                mark = e.problem_mark
                # Check for common issues and provide helpful messages
                if 'duplicate anchor' in error_str.lower():
                    # Extract anchor name from error
                    import re as regex
                    anchor_match = regex.search(r"anchor ['\"]?(\w+)['\"]?", error_str)
                    anchor_name = anchor_match.group(1) if anchor_match else "unknown"
                    error_msg = (
                        f"YAML error at line {mark.line + 1}: Duplicate anchor '&{anchor_name}'. "
                        f"Use alias '*{anchor_name}' to reference existing anchor instead of redefining it."
                    )
                else:
                    error_msg = f"YAML error at line {mark.line + 1}, column {mark.column + 1}: {e.problem}"
            else:
                error_msg = f"YAML error: {error_str.split(chr(10))[0]}"
            errors.append(error_msg)
            return None, errors
        except Exception as e:
            errors.append(f"Error reading file: {e}")
            return None, errors

    def validate_stage_file(self, file_path: Path) -> bool:
        """Validate a stage definition file."""
        data, yaml_errors = self.validate_yaml_file(file_path)

        for err in yaml_errors:
            self.errors.append((str(file_path), "file", err))

        if data is None:
            return False

        stages = data.get('stages', [])
        if not isinstance(stages, list):
            return True

        for i, stage in enumerate(stages):
            self.validate_stage(stage, str(file_path), i)

        return True

    def _find_similar(self, value: str, candidates: Any) -> Optional[str]:
        """Find a similar string from candidates (for typo suggestions)."""
        value_lower = value.lower().replace('-', '_')
        for candidate in candidates:
            candidate_lower = candidate.lower().replace('-', '_')
            # Check for common transformations
            if value_lower == candidate_lower:
                return candidate
            # Check Levenshtein distance of 1-2
            if self._levenshtein_distance(value_lower, candidate_lower) <= 2:
                return candidate
        return None

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculate Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return TerraSchemaValidator._levenshtein_distance(s2, s1)
        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]

    def get_report(self) -> str:
        """Generate a validation report."""
        lines = []

        if self.errors:
            lines.append("\n" + "=" * 70)
            lines.append("SCHEMA VALIDATION ERRORS:")
            lines.append("=" * 70)
            for file_path, location, message in self.errors:
                lines.append(f"  ERROR in {file_path}")
                lines.append(f"    Location: {location}")
                lines.append(f"    Message: {message}")
                lines.append("")

        if self.warnings:
            lines.append("\n" + "-" * 70)
            lines.append("SCHEMA VALIDATION WARNINGS:")
            lines.append("-" * 70)
            for file_path, location, message in self.warnings:
                lines.append(f"  WARNING in {file_path}")
                lines.append(f"    Location: {location}")
                lines.append(f"    Message: {message}")
                lines.append("")

        # Report skipped stage files and their impact
        if self.skipped_stages_by_preset:
            lines.append("\n" + "=" * 70)
            lines.append("SKIPPED STAGE FILES (biome calculations may be incomplete):")
            lines.append("=" * 70)
            for preset_name in sorted(self.skipped_stages_by_preset.keys()):
                skipped_files = self.skipped_stages_by_preset[preset_name]
                lines.append(f"\n  Preset '{preset_name}' skipped {len(skipped_files)} stage file(s):")
                for stage_file in skipped_files:
                    lines.append(f"    - {stage_file}")
            lines.append("")
            lines.append("  These presets may have missing or incorrect biome percentages.")
            lines.append("  Fix the errors above and re-run to get accurate calculations.")
            lines.append("")

        if not self.errors and not self.warnings and not self.skipped_stages_by_preset:
            lines.append("\nSchema validation passed - no errors or warnings found.")

        return "\n".join(lines)

    def has_errors(self) -> bool:
        """Check if any validation errors were found."""
        return len(self.errors) > 0


# Global validator instance
_validator: Optional[TerraSchemaValidator] = None

def get_validator() -> TerraSchemaValidator:
    """Get or create the global validator instance."""
    global _validator
    if _validator is None:
        _validator = TerraSchemaValidator()
    return _validator


# =============================================================================
# Climate Context Tracking
# =============================================================================

@dataclass
class ClimateContext:
    """
    Tracks climate attributes for a biome.

    Attributes:
        origin_type: "Land" or "Ocean" based on source biome
        temperature: Normalized temperature value (0=coldest, 1=hottest), None if not climate-affected
        precipitation: Normalized precipitation value (0=driest, 1=wettest), None if not climate-affected
        elevation: Normalized elevation value (0=lowest, 1=highest), None if not climate-affected
    """
    origin_type: Optional[str] = None
    temperature: Optional[float] = None
    precipitation: Optional[float] = None
    elevation: Optional[float] = None

    def copy(self) -> 'ClimateContext':
        return ClimateContext(
            origin_type=self.origin_type,
            temperature=self.temperature,
            precipitation=self.precipitation,
            elevation=self.elevation
        )

    @staticmethod
    def weighted_combine(contexts: List[Tuple['ClimateContext', float]]) -> 'ClimateContext':
        """
        Combine multiple climate contexts with weights.
        Returns a new context with weighted average values.
        """
        if not contexts:
            return ClimateContext()

        total_weight = sum(w for _, w in contexts)
        if total_weight <= 0:
            return ClimateContext()

        # Determine origin type (use majority)
        origin_counts: Dict[str, float] = defaultdict(float)
        for ctx, weight in contexts:
            if ctx.origin_type:
                origin_counts[ctx.origin_type] += weight

        origin_type = max(origin_counts.keys(), key=lambda k: origin_counts[k]) if origin_counts else None

        # Calculate weighted averages for numeric fields
        def weighted_avg(field_name: str) -> Optional[float]:
            values = [(getattr(ctx, field_name), w) for ctx, w in contexts if getattr(ctx, field_name) is not None]
            if not values:
                return None
            total = sum(v * w for v, w in values)
            weight_sum = sum(w for _, w in values)
            return total / weight_sum if weight_sum > 0 else None

        return ClimateContext(
            origin_type=origin_type,
            temperature=weighted_avg('temperature'),
            precipitation=weighted_avg('precipitation'),
            elevation=weighted_avg('elevation')
        )


class ClimateTracker:
    """
    Tracks climate context for biomes as they flow through the pipeline.

    The climate values are derived from the position in weighted lists:
    - Temperature: ice-cap (0) to tropical-rainforest (1)
    - Precipitation: desert (0) to veryWet (1)
    - Elevation: flat/deep (0) to highlands (1)
    """

    # Temperature bands from temperature.yml (coldest to hottest)
    TEMPERATURE_BANDS = [
        'ice-cap', 'tundra', 'boreal-snowy', 'boreal-cold', 'boreal-warm', 'boreal-hot',
        'temperate-cold', 'temperate-warm', 'temperate-hot',
        'tropical-savanna-wet', 'tropical-monsoon', 'tropical-rainforest'
    ]

    # Precipitation bands from precipitation.yml (driest to wettest)
    PRECIPITATION_BANDS = ['desert', 'desertBorder', 'semiArid', 'mid', 'mildlyWet', 'veryWet']

    # Elevation bands from elevation.yml (lowest to highest)
    ELEVATION_BANDS = ['flat', 'lowlands', 'midlands', 'highlands']
    OCEAN_ELEVATION_BANDS = ['deep', 'regular', 'shallow']

    def __init__(self):
        # Maps biome_id -> ClimateContext
        self.contexts: Dict[str, ClimateContext] = {}
        # Maps biome_id -> list of (parent_biome, weight) for tracking lineage
        self.lineage: Dict[str, List[Tuple[str, float]]] = defaultdict(list)

    def set_origin(self, biome: str, origin_type: str):
        """Set the origin type (Land/Ocean) for a source biome."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].origin_type = origin_type

    def get_context(self, biome: str) -> ClimateContext:
        """Get the climate context for a biome."""
        return self.contexts.get(biome, ClimateContext())

    def set_context(self, biome: str, context: ClimateContext):
        """Set the climate context for a biome."""
        self.contexts[biome] = context

    def propagate_context(self, from_biome: str, to_biome: str, weight: float = 1.0):
        """Propagate climate context from one biome to another."""
        if from_biome in self.contexts:
            self.lineage[to_biome].append((from_biome, weight))

    def apply_temperature(self, biome: str, band_index: int):
        """Apply temperature band to a biome (index-based; prefer apply_temperature_value)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].temperature = band_index / max(1, len(self.TEMPERATURE_BANDS) - 1)

    def apply_precipitation(self, biome: str, band_index: int):
        """Apply precipitation band to a biome (index-based; prefer apply_precipitation_value)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].precipitation = band_index / max(1, len(self.PRECIPITATION_BANDS) - 1)

    def apply_elevation(self, biome: str, band_index: int, is_ocean: bool = False):
        """Apply elevation band to a biome (index-based; prefer apply_elevation_value)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        bands = self.OCEAN_ELEVATION_BANDS if is_ocean else self.ELEVATION_BANDS
        self.contexts[biome].elevation = band_index / max(1, len(bands) - 1)

    def apply_temperature_value(self, biome: str, value: float):
        """Set temperature to a pipeline-derived normalized value (0–1)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].temperature = value

    def apply_precipitation_value(self, biome: str, value: float):
        """Set precipitation to a pipeline-derived normalized value (0–1)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].precipitation = value

    def apply_elevation_value(self, biome: str, value: float):
        """Set elevation to a pipeline-derived normalized value (0–1)."""
        if biome not in self.contexts:
            self.contexts[biome] = ClimateContext()
        self.contexts[biome].elevation = value

    def apply_default_climate(self, biome_ids: Set[str], default_value: float = 0.5):
        """
        For biomes without pipeline-derived climate values, apply a neutral default.
        The default is 0.5, representing the mean of a uniform sampler on [-1, 1]
        mapped to [0, 1].
        """
        for biome_id in biome_ids:
            ctx = self.contexts.get(biome_id, ClimateContext())
            changed = False
            if ctx.temperature is None:
                ctx.temperature = default_value
                changed = True
            if ctx.precipitation is None:
                ctx.precipitation = default_value
                changed = True
            if ctx.elevation is None:
                ctx.elevation = default_value
                changed = True
            if changed:
                self.contexts[biome_id] = ctx

    def finalize_contexts(self):
        """
        Finalize all contexts by computing weighted combinations from lineage.
        Call this after all pipeline processing is complete.
        """
        # Process biomes that have lineage information
        for biome, parents in self.lineage.items():
            if not parents:
                continue

            parent_contexts = []
            for parent_biome, weight in parents:
                if parent_biome in self.contexts:
                    parent_contexts.append((self.contexts[parent_biome], weight))

            if parent_contexts:
                # Combine parent contexts, preserving any directly-set values
                combined = ClimateContext.weighted_combine(parent_contexts)

                # Merge with existing context (directly-set values take precedence)
                existing = self.contexts.get(biome, ClimateContext())
                if existing.origin_type is None:
                    existing.origin_type = combined.origin_type
                if existing.temperature is None:
                    existing.temperature = combined.temperature
                if existing.precipitation is None:
                    existing.precipitation = combined.precipitation
                if existing.elevation is None:
                    existing.elevation = combined.elevation

                self.contexts[biome] = existing

    def copy(self) -> 'ClimateTracker':
        """Create a copy of this tracker."""
        new_tracker = ClimateTracker()
        new_tracker.contexts = {k: v.copy() for k, v in self.contexts.items()}
        new_tracker.lineage = {k: list(v) for k, v in self.lineage.items()}
        return new_tracker

    # infer_climate_from_name() and infer_all_contexts() removed.
    # Climate values are now derived from the pipeline stage structure:
    # when a REPLACE_LIST stage uses the temperature/precipitation/elevation
    # EXPRESSION sampler, the expected band index is computed via CDF and
    # stored via apply_temperature_value() / apply_precipitation_value() /
    # apply_elevation_value().  Biomes that don't pass through such a stage
    # receive the default value (0.5) via apply_default_climate().


class BiomeDistribution:
    """Tracks probability distribution of biomes with climate context and origin tracking"""

    # Source biomes that are considered "Ocean" / "Land" origin (from constants above)
    OCEAN_SOURCES = OCEAN_SOURCE_BIOMES
    LAND_SOURCES  = LAND_SOURCE_BIOMES

    def __init__(self):
        self.probabilities: Dict[str, float] = {}
        self.categories: Dict[str, DistributionCategory] = {}
        self.climate: ClimateTracker = ClimateTracker()
        # Track origin: biome_id -> "Land" | "Ocean" | "Mixed"
        self.origins: Dict[str, str] = {}

    def set(self, biome: str, prob: float,
            category: DistributionCategory = DistributionCategory.SURFACE):
        """Set probability for a biome"""
        self.probabilities[biome] = prob
        if biome not in self.categories:
            self.categories[biome] = category

    def get(self, biome: str) -> float:
        """Get probability for a biome"""
        return self.probabilities.get(biome, 0.0)

    def remove(self, biome: str):
        """Remove a biome from distribution"""
        if biome in self.probabilities:
            del self.probabilities[biome]

    def add(self, biome: str, prob: float,
            category: DistributionCategory = DistributionCategory.SURFACE):
        """Add probability to a biome (accumulate)"""
        self.probabilities[biome] = self.get(biome) + prob
        if biome not in self.categories:
            self.categories[biome] = category

    def get_category(self, biome: str) -> DistributionCategory:
        """Get the distribution category for a biome."""
        return self.categories.get(biome, DistributionCategory.SURFACE)

    def set_origin(self, biome: str, origin: str):
        """Set origin for a biome"""
        if origin in ("Land", "Ocean"):
            # Check if biome already has a different origin
            if biome in self.origins and self.origins[biome] != origin:
                self.origins[biome] = "Mixed"
            else:
                self.origins[biome] = origin

    def add_origin_from(self, to_biome: str, from_biome: str):
        """Propagate origin from one biome to another"""
        # Check if from_biome is a known source biome
        from_lower = from_biome.lower()
        if from_lower in self.OCEAN_SOURCES:
            self.set_origin(to_biome, "Ocean")
        elif from_lower in self.LAND_SOURCES:
            self.set_origin(to_biome, "Land")
        elif from_biome in self.origins:
            self.set_origin(to_biome, self.origins[from_biome])

    def get_origin(self, biome: str) -> Optional[str]:
        """Get the origin for a biome"""
        return self.origins.get(biome)

    def normalize(self):
        """Normalize probabilities to sum to 1.0"""
        total = sum(self.probabilities.values())
        if total > 0:
            for biome in self.probabilities:
                self.probabilities[biome] /= total

    def copy(self):
        """Create a copy of this distribution"""
        new_dist = BiomeDistribution()
        new_dist.probabilities = self.probabilities.copy()
        new_dist.categories = self.categories.copy()
        new_dist.climate = self.climate.copy()
        new_dist.origins = self.origins.copy()
        return new_dist

    def get_top_biomes(self, n: int = 20) -> List[Tuple[str, float]]:
        """Get top N biomes by probability"""
        return sorted(self.probabilities.items(), key=lambda x: x[1], reverse=True)[:n]

    def __str__(self):
        top_10 = self.get_top_biomes(10)
        return "\n".join([f"  {biome}: {prob:.4%}" for biome, prob in top_10])


class StageProcessor:
    """Processes Terra pipeline stages"""

    @staticmethod
    def parse_weighted_list(yaml_list: List) -> Dict[str, int]:
        """Parse a weighted biome list from YAML (merges duplicate biome names)."""
        weights = {}
        for item in yaml_list:
            if isinstance(item, dict):
                for biome, weight in item.items():
                    if isinstance(weight, (int, float)):
                        weights[biome] = int(weight)
                    else:
                        weights[biome] = 1
        return weights

    @staticmethod
    def parse_weighted_list_ordered(yaml_list: List) -> List[Tuple[str, int]]:
        """
        Parse a weighted biome list preserving order and duplicates.

        Unlike parse_weighted_list(), returns [(biome, weight), ...] in YAML order.
        Duplicate biome IDs are kept as separate entries so that their slot positions
        (needed for CDF-based probability and climate band computation) are preserved.
        """
        result = []
        for item in yaml_list:
            if isinstance(item, dict):
                for biome, weight in item.items():
                    if isinstance(weight, (int, float)):
                        result.append((biome, int(weight)))
                    else:
                        result.append((biome, 1))
        return result

    @staticmethod
    def process_replace_list(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a REPLACE_LIST stage

        Tag matching: Both 'default-from' and the keys in 'to' section can be tags.
        A biome matches if its ID equals the identifier OR it has the identifier as a tag.
        """
        new_dist = BiomeDistribution()
        # Carry forward climate values and origins
        new_dist.climate = distribution.climate.copy()
        new_dist.origins = distribution.origins.copy()

        # Get default-from and default-to
        default_from = stage.get('default-from')
        default_to   = stage.get('default-to', [])

        # Get transformation mapping
        to_section = stage.get('to', {})

        # Resolve sampler config for CDF-based probability computation
        sampler_config = stage.get('sampler', {})

        # Detect climate stage (temperature / precipitation / elevation)
        climate_name = _get_climate_sampler_name(stage)

        # Detect river stage: output biomes other than SELF get RIVER category
        is_river = _is_river_stage(stage)

        # Pre-compute ordered items + slot probabilities for the default list
        default_items = StageProcessor.parse_weighted_list_ordered(default_to)
        default_probs = _compute_slot_probabilities(
            sampler_config, [w for _, w in default_items])
        # Aggregate by biome (duplicate biome IDs in the list are merged)
        default_biome_dist: Dict[str, float] = {}
        for (to_biome, _), p in zip(default_items, default_probs):
            default_biome_dist[to_biome] = default_biome_dist.get(to_biome, 0.0) + p

        # Pre-compute climate band values for default list.
        # For climate stages, the expected sampler value for each slot determines
        # the climate attribute (temperature/precipitation/elevation).
        # We compute the expected value of the sampler conditional on each slot
        # and normalize to [0, 1] across the full list range.
        default_band_values: Dict[str, float] = {}
        if climate_name and default_items:
            default_band_values = _compute_climate_band_values(
                default_items, default_probs, sampler_config)

        # Helper: add biome with origin and climate propagation
        def add_with_origin(to_biome: str, from_biome: str, prob: float,
                            band_value: Optional[float] = None):
            actual = from_biome if to_biome == 'SELF' else to_biome
            # River stages: new biomes (not SELF) are RIVER category
            out_cat = DistributionCategory.RIVER if (is_river and actual != from_biome) \
                      else distribution.get_category(from_biome)
            new_dist.add(actual, prob, out_cat)
            # Propagate origin
            if actual != from_biome:
                new_dist.add_origin_from(actual, from_biome)
            # Apply pipeline-derived climate value if this is a named climate stage
            if climate_name is not None and band_value is not None:
                _apply_climate_value(new_dist.climate, climate_name, actual, band_value)
            # Always propagate inherited climate values from predecessor
            # (non-climate stages inherit T/P/E from the biome being replaced)
            if actual != from_biome:
                _propagate_climate(new_dist.climate, from_biome, actual)

        # Process each biome in current distribution
        for from_biome, from_prob in list(distribution.probabilities.items()):
            matched = False
            # Region of this from-biome — gates whose sampler reads the
            # continental field are resolved conditioned on it (land vs ocean).
            region = _region_of(distribution, from_biome)

            # Check if there's a specific transformation for this biome
            for to_key, to_list in to_section.items():
                if BiomeReader.matches_biome_or_tag(to_key, from_biome):
                    matched = True
                    if isinstance(to_list, str):
                        # Shorthand: direct replacement (no sampler weighting)
                        add_with_origin(to_list, from_biome, from_prob)
                    elif isinstance(to_list, list):
                        to_items = StageProcessor.parse_weighted_list_ordered(to_list)
                        to_probs = _region_slot_probs(
                            sampler_config, [w for _, w in to_items], region)
                        # Aggregate by biome
                        biome_dist: Dict[str, float] = {}
                        for (tb, _), p in zip(to_items, to_probs):
                            biome_dist[tb] = biome_dist.get(tb, 0.0) + p
                        # Compute climate band values for this specific to_list
                        band_vals: Dict[str, float] = {}
                        if climate_name and to_items:
                            band_vals = _compute_climate_band_values(
                                to_items, to_probs, sampler_config)
                        for tb, p in biome_dist.items():
                            if p > 0:
                                add_with_origin(tb, from_biome, from_prob * p,
                                                band_vals.get(tb))
                    break  # Only apply one transformation per biome

            # If no specific match, check default-from
            if not matched and default_from and BiomeReader.matches_biome_or_tag(default_from, from_biome):
                matched = True
                if region in ("Land", "Ocean") and _is_continental_dependent(sampler_config):
                    probs = _region_slot_probs(
                        sampler_config, [w for _, w in default_items], region)
                    region_default_dist: Dict[str, float] = {}
                    for (tb, _), p in zip(default_items, probs):
                        region_default_dist[tb] = region_default_dist.get(tb, 0.0) + p
                else:
                    region_default_dist = default_biome_dist
                for tb, p in region_default_dist.items():
                    if p > 0:
                        add_with_origin(tb, from_biome, from_prob * p,
                                        default_band_values.get(tb))

            if not matched:
                # Pass through (never pass through literal "SELF")
                if from_biome != 'SELF':
                    new_dist.add(from_biome, from_prob, distribution.get_category(from_biome))
                    new_dist.add_origin_from(from_biome, from_biome)

        return new_dist

    @staticmethod
    def process_replace(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a simple REPLACE stage

        Based on Terra source code (ReplaceStage.java):
        - The 'from' field matches biomes by tag/ID
        - ALL matching biomes are replaced (100%, not partial)
        - The 'sampler' determines WHICH biome from 'to' is selected at each location
        - The 'to' weights determine proportional distribution (modified by sampler spatial pattern)

        Tag matching: If 'from' is a tag (e.g., LAND_CAVES), all biomes with that tag
        in the distribution are replaced.
        """
        new_dist = distribution.copy()

        from_identifier = stage.get('from')
        to_spec = stage.get('to')

        if not from_identifier:
            return new_dist

        # Find all biomes in the distribution that match the 'from' identifier
        # This includes direct ID matches AND biomes with the identifier as a tag
        matching_biomes = []
        for biome_id in list(new_dist.probabilities.keys()):
            if BiomeReader.matches_biome_or_tag(from_identifier, biome_id):
                matching_biomes.append(biome_id)

        # Process each matching biome
        for matched_biome in matching_biomes:
            from_prob = new_dist.get(matched_biome)
            if from_prob <= 0:
                continue

            # Remove the matched biome from distribution
            new_dist.remove(matched_biome)

            # Helper to add biome with origin propagation
            def add_with_origin(to_biome: str, prob: float):
                if to_biome == 'SELF':
                    new_dist.add(matched_biome, prob)
                    if matched_biome in distribution.origins:
                        new_dist.origins[matched_biome] = distribution.origins[matched_biome]
                else:
                    new_dist.add(to_biome, prob)
                    new_dist.add_origin_from(to_biome, matched_biome)

            # Distribute the probability according to 'to' weights using CDF-based probabilities
            sampler_config = stage.get('sampler', {})
            from_cat = new_dist.categories.get(matched_biome, DistributionCategory.SURFACE)
            is_river = _is_river_stage(stage)
            out_cat = DistributionCategory.RIVER if is_river else from_cat
            # Region of the replaced biome — continental gates (mesa/island/…) are
            # resolved conditioned on it so coverage reflects the land/ocean subset.
            region = _region_of(distribution, matched_biome)

            if isinstance(to_spec, str):
                actual = matched_biome if to_spec == 'SELF' else to_spec
                new_dist.add(actual, from_prob, out_cat)
                new_dist.add_origin_from(actual, matched_biome)
                if actual != matched_biome:
                    _propagate_climate(new_dist.climate, matched_biome, actual)
            elif isinstance(to_spec, list):
                to_items = StageProcessor.parse_weighted_list_ordered(to_spec)
                to_probs = _region_slot_probs(
                    sampler_config, [w for _, w in to_items], region)
                biome_dist: Dict[str, float] = {}
                for (tb, _), p in zip(to_items, to_probs):
                    biome_dist[tb] = biome_dist.get(tb, 0.0) + p
                for tb, p in biome_dist.items():
                    actual = matched_biome if tb == 'SELF' else tb
                    new_dist.add(actual, from_prob * p, out_cat)
                    new_dist.add_origin_from(actual, matched_biome)
                    if actual != matched_biome:
                        _propagate_climate(new_dist.climate, matched_biome, actual)
            elif isinstance(to_spec, dict):
                # Dict format — treat like an ordered list
                to_items_d = [(k, v) for k, v in to_spec.items()
                              if isinstance(v, (int, float))]
                to_probs_d = _region_slot_probs(
                    sampler_config, [int(w) for _, w in to_items_d], region)
                biome_dist_d: Dict[str, float] = {}
                for (tb, _), p in zip(to_items_d, to_probs_d):
                    biome_dist_d[tb] = biome_dist_d.get(tb, 0.0) + p
                for tb, p in biome_dist_d.items():
                    actual = matched_biome if tb == 'SELF' else tb
                    new_dist.add(actual, from_prob * p, out_cat)
                    new_dist.add_origin_from(actual, matched_biome)
                    if actual != matched_biome:
                        _propagate_climate(new_dist.climate, matched_biome, actual)

        return new_dist

    @staticmethod
    def process_border(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a BORDER stage

        BORDER stages find borders between two biomes and create a third biome at the boundary.
        For probability calculation, we approximate this by:
        - Taking a percentage of the 'replace' biome's probability
        - Converting it to the 'to' biome(s)
        - The percentage is proportional to the 'from' biome's probability (more 'from' = more borders)

        Tag matching: Both 'from' and 'replace' can be tags that match multiple biomes.
        The 'to' field can be a single biome or a weighted list.
        """
        new_dist = distribution.copy()

        from_identifier = stage.get('from')
        replace_identifier = stage.get('replace')
        to_spec = stage.get('to')

        if not from_identifier or not replace_identifier or not to_spec:
            return distribution

        # Parse the 'to' specification - can be string or weighted list
        if isinstance(to_spec, str):
            to_weights = {to_spec: 1}
        elif isinstance(to_spec, list):
            to_weights = StageProcessor.parse_weighted_list(to_spec)
        elif isinstance(to_spec, dict):
            to_weights = {k: v for k, v in to_spec.items() if isinstance(v, (int, float))}
        else:
            return distribution

        total_to_weight = sum(to_weights.values())
        if total_to_weight <= 0:
            return distribution

        # Find all biomes that match the 'from' identifier (for calculating border probability)
        from_total_prob = 0.0
        for biome_id in new_dist.probabilities.keys():
            if BiomeReader.matches_biome_or_tag(from_identifier, biome_id):
                from_total_prob += new_dist.get(biome_id)

        if from_total_prob <= 0:
            # No 'from' biomes exist, no borders possible
            return new_dist

        # Find all biomes that match the 'replace' identifier
        replace_biomes = []
        for biome_id in list(new_dist.probabilities.keys()):
            if BiomeReader.matches_biome_or_tag(replace_identifier, biome_id):
                replace_biomes.append(biome_id)

        if not replace_biomes:
            # No 'replace' biomes exist, no borders possible
            return new_dist

        # Per-biome border conversion fraction (geometric, sqrt-of-from model).
        # Pre-compute once; same for every replace biome in this stage.
        border_frac = _border_fraction(from_total_prob)

        # Process each matching replace biome
        for replace_biome in replace_biomes:
            replace_prob = new_dist.get(replace_biome)
            if replace_prob <= 0:
                continue

            border_prob = replace_prob * border_frac

            # Transfer probability from replace_biome to to_biome(s)
            new_dist.probabilities[replace_biome] = replace_prob - border_prob

            # Distribute border_prob using CDF-based probabilities
            sampler_config = stage.get('sampler', {})
            items = list(to_weights.items())
            probs = _compute_slot_probabilities(
                sampler_config, [w for _, w in items])
            for (to_biome, _), p in zip(items, probs):
                actual_prob = border_prob * p
                if to_biome == 'SELF':
                    new_dist.add(replace_biome, actual_prob)
                else:
                    new_dist.add(to_biome, actual_prob)

        return new_dist

    @staticmethod
    def process_border_list(stage: Dict, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process a BORDER_LIST stage.

        BORDER_LIST is like BORDER but with per-biome replacement maps:
          - 'from':            tag on neighbour biomes that triggers border detection
          - 'default-replace': tag on center biome that makes it eligible for replacement
          - 'default-to':      default replacement weighted list
          - 'replace':         per-biome override map { biome_id: weighted_list }

        Probability model is the same geometric estimate as BORDER.
        """
        new_dist = distribution.copy()

        from_tag       = stage.get('from')
        default_replace = stage.get('default-replace')
        default_to     = stage.get('default-to', [])
        replace_map    = stage.get('replace', {})
        sampler_config = stage.get('sampler', {})

        if not from_tag or not default_replace:
            return distribution

        # Parse default-to weights
        if isinstance(default_to, str):
            default_weights = {default_to: 1}
        elif isinstance(default_to, list):
            default_weights = StageProcessor.parse_weighted_list(default_to)
        elif isinstance(default_to, dict):
            default_weights = {k: v for k, v in default_to.items() if isinstance(v, (int, float))}
        else:
            default_weights = {}

        # Total probability of 'from' biomes (used for border fraction estimate)
        from_total_prob = 0.0
        for biome_id in new_dist.probabilities:
            if BiomeReader.matches_biome_or_tag(from_tag, biome_id):
                from_total_prob += new_dist.get(biome_id)

        if from_total_prob <= 0:
            return new_dist

        # Find all biomes that match default-replace tag
        replace_biomes = []
        for biome_id in list(new_dist.probabilities.keys()):
            if BiomeReader.matches_biome_or_tag(default_replace, biome_id):
                replace_biomes.append(biome_id)

        if not replace_biomes:
            return new_dist

        border_frac = _border_fraction(from_total_prob)

        for replace_biome in replace_biomes:
            replace_prob = new_dist.get(replace_biome)
            if replace_prob <= 0:
                continue

            border_prob = replace_prob * border_frac

            new_dist.probabilities[replace_biome] = replace_prob - border_prob

            # Determine which to-list applies (per-biome override or default)
            to_weights = default_weights
            for biome_key, biome_to_list in replace_map.items():
                if BiomeReader.matches_biome_or_tag(biome_key, replace_biome):
                    if isinstance(biome_to_list, list):
                        to_weights = StageProcessor.parse_weighted_list(biome_to_list)
                    elif isinstance(biome_to_list, str):
                        to_weights = {biome_to_list: 1}
                    break

            # Distribute border_prob using CDF-based probabilities
            if to_weights:
                items = list(to_weights.items())
                probs = _compute_slot_probabilities(
                    sampler_config, [w for _, w in items])
                for (to_biome, _), p in zip(items, probs):
                    actual_prob = border_prob * p
                    if to_biome == 'SELF':
                        new_dist.add(replace_biome, actual_prob)
                    else:
                        new_dist.add(to_biome, actual_prob)

        return new_dist

    @staticmethod
    def process_stage(stage_config: Any, distribution: BiomeDistribution) -> BiomeDistribution:
        """Process any stage type"""
        if not isinstance(stage_config, dict):
            return distribution

        stage_type = stage_config.get('type')

        # When the pack ships with rivers disabled (benchmark build), the river
        # REPLACE stages are effectively identity (riverSampler never selects RIVER).
        # Skip them so the predictor doesn't model ~25% phantom river coverage.
        if _rivers_disabled() and _is_river_stage(stage_config):
            return distribution

        if stage_type == 'REPLACE_LIST':
            return StageProcessor.process_replace_list(stage_config, distribution)
        elif stage_type == 'REPLACE':
            return StageProcessor.process_replace(stage_config, distribution)
        elif stage_type == 'BORDER':
            return StageProcessor.process_border(stage_config, distribution)
        elif stage_type == 'BORDER_LIST':
            return StageProcessor.process_border_list(stage_config, distribution)
        else:
            # EXPAND, SMOOTH, etc. don't affect probabilities
            return distribution


class ExtrusionDistribution:
    """
    Tracks extrusion biome distributions.

    Extrusions are underground biome replacements that happen at specific Y-ranges.
    They don't replace surface biome percentages - instead they occupy additional
    underground space, derived from the surface biomes above them.
    """

    def __init__(self):
        # Maps biome_id -> (parent_biome_or_ALL, weight_fraction, source_file)
        self.extrusion_biomes: Dict[str, List[Tuple[str, float, str]]] = defaultdict(list)

    def add_extrusion_biome(self, biome_id: str, parent: str, weight_fraction: float, source_file: str):
        """
        Add an extrusion biome.

        Args:
            biome_id: The cave/underground biome being added
            parent: The parent biome (or 'ALL' if applies to all)
            weight_fraction: The fraction of the parent space this biome occupies
            source_file: The extrusion file this came from
        """
        self.extrusion_biomes[biome_id].append((parent, weight_fraction, source_file))

    def get_extrusion_biomes(self) -> Set[str]:
        """Get all biomes that come from extrusions"""
        return set(self.extrusion_biomes.keys())

    def calculate_percentage(self, biome_id: str, surface_distribution: BiomeDistribution,
                             _visited: Optional[Set[str]] = None) -> float:
        """
        Calculate the effective percentage for an extrusion biome.

        For 'ALL' parent: percentage = weight_fraction (applies uniformly)
        For specific parent/tag: percentage = sum(matching_biome_pcts) * weight_fraction

        Chained extrusions: If the parent biome is itself an extrusion (not in the
        surface distribution), recursively resolve its extrusion percentage.

        Tag matching: If parent is a tag (e.g., LAND_CAVES), we sum the probabilities
        of all surface biomes that have that tag.
        """
        if biome_id not in self.extrusion_biomes:
            return 0.0

        if _visited is None:
            _visited = set()
        if biome_id in _visited:
            return 0.0  # prevent infinite recursion
        _visited.add(biome_id)

        total_pct = 0.0
        for parent_identifier, weight_fraction, _ in self.extrusion_biomes[biome_id]:
            if parent_identifier == 'ALL':
                # Applies to all surface biomes - use the weight fraction directly
                # This represents the fraction of underground space
                total_pct += weight_fraction
            else:
                # Find all biomes in the surface distribution that match the parent identifier
                # This includes direct ID matches AND biomes with the identifier as a tag
                matching_pct = 0.0
                for surface_biome in surface_distribution.probabilities.keys():
                    if BiomeReader.matches_biome_or_tag(parent_identifier, surface_biome):
                        matching_pct += surface_distribution.get(surface_biome)

                # If parent has no surface presence, check if it's a chained extrusion
                if matching_pct == 0.0 and parent_identifier in self.extrusion_biomes:
                    matching_pct = self.calculate_percentage(
                        parent_identifier, surface_distribution, _visited
                    )

                total_pct += matching_pct * weight_fraction

        return total_pct

    def get_source_info(self, biome_id: str) -> str:
        """Get the source file(s) for an extrusion biome"""
        if biome_id not in self.extrusion_biomes:
            return ""
        sources = set(src for _, _, src in self.extrusion_biomes[biome_id])
        return ", ".join(sorted(sources))


class ExtrusionProcessor:
    """Processes extrusion definitions from preset files"""

    # World Y constants from meta.yml (used to scale extrusion Y-range to a
    # subsurface-volume fraction).  bottom-y=-64, top-y=319 → 383 blocks total.
    # Most cave/subsurface activity lives between bottom-y and cave-top=200.
    WORLD_Y_TOP    = 319
    WORLD_Y_BOTTOM = -64
    WORLD_Y_RANGE  = WORLD_Y_TOP - WORLD_Y_BOTTOM    # 383
    # Resolved $meta.yml references commonly seen in extrusion 'range' fields
    META_Y_VALUES = {
        'top-y':              319,
        'ocean-level':        62,
        'sinkhole-ocean-level': 40,
        'deepslate-top':      7,
        'deepslate-bottom':  -7,
        'cave-top':           200,
        'cave-bottom':       -40,
        'bedrock-top':       -60,
        'bottom-y':          -64,
    }

    @staticmethod
    def _resolve_y_value(val: Any) -> Optional[float]:
        """Resolve a Y-range bound which may be a literal int or a $meta.yml ref."""
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            # Strip $ and $meta.yml: prefix, look up known keys
            s = val.strip()
            if s.startswith('$'):
                s = s[1:]
            if s.startswith('meta.yml:'):
                s = s[len('meta.yml:'):]
            # Try direct lookup
            if s in ExtrusionProcessor.META_Y_VALUES:
                return float(ExtrusionProcessor.META_Y_VALUES[s])
        return None

    @classmethod
    def _y_range_fraction(cls, range_dict: Any) -> float:
        """
        Convert an extrusion's 'range:{min,max}' to a fraction of total world Y.

        Returns 1.0 if the range field is missing or unresolvable (preserving
        legacy behavior).  Otherwise returns (max−min)/WORLD_Y_RANGE clamped to
        [0, 1].
        """
        if not isinstance(range_dict, dict):
            return 1.0
        y_min = cls._resolve_y_value(range_dict.get('min'))
        y_max = cls._resolve_y_value(range_dict.get('max'))
        if y_min is None or y_max is None or y_max <= y_min:
            return 1.0
        frac = (y_max - y_min) / cls.WORLD_Y_RANGE
        return max(0.0, min(1.0, frac))

    @staticmethod
    def parse_extrusion_file(extrusion_path: Path) -> List[Dict]:
        """Load extrusions from a file"""
        try:
            with open(extrusion_path, 'r') as f:
                data = yaml.safe_load(f)
                return data.get('extrusions', [])
        except Exception as e:
            print(f"Warning: Could not load extrusion file {extrusion_path}: {e}", file=sys.stderr)
            return []

    @staticmethod
    def process_extrusion(extrusion_config: Dict, source_file: str) -> List[Tuple[str, str, float]]:
        """
        Process a single extrusion config.

        Returns list of (biome_id, parent, weight_fraction) tuples.
        Uses CDF-based slot probabilities when a sampler is present.

        The weight_fraction is scaled by the extrusion's Y-range as a fraction
        of total world height — an extrusion only producing blocks in a slim
        Y-slice contributes proportionally less to the subsurface volume.
        """
        results = []

        extrusion_type = extrusion_config.get('type')
        if extrusion_type != 'REPLACE':
            return results

        from_biome = extrusion_config.get('from', '')
        to_spec = extrusion_config.get('to')
        sampler_config = extrusion_config.get('sampler', {})

        if not to_spec:
            return results

        # Y-range scale: how much of total world Y this extrusion covers.
        # When the range is missing (chained extrusions like LOW_CAVES_PRE →
        # DEEP_DARK in add_deep_dark.yml), assume 1.0 so the parent's own
        # Y-range governs.  Specific bound-pairs get scaled down.
        y_scale = ExtrusionProcessor._y_range_fraction(extrusion_config.get('range'))

        # Parse the 'to' specification to get weights
        if isinstance(to_spec, str):
            # Single biome replacement
            if to_spec != 'SELF':
                results.append((to_spec, from_biome, 1.0 * y_scale))
        elif isinstance(to_spec, list):
            # Weighted list — use CDF-based probabilities
            items = StageProcessor.parse_weighted_list_ordered(to_spec)
            if items:
                probs = _compute_slot_probabilities(
                    sampler_config, [w for _, w in items])
                # Aggregate by biome (merge duplicates)
                biome_probs: Dict[str, float] = {}
                for (biome_id, _), p in zip(items, probs):
                    if biome_id != 'SELF':
                        biome_probs[biome_id] = biome_probs.get(biome_id, 0.0) + p
                for biome_id, weight_fraction in biome_probs.items():
                    results.append((biome_id, from_biome, weight_fraction * y_scale))
        elif isinstance(to_spec, dict):
            # Dict format
            items = [(k, int(v)) for k, v in to_spec.items()
                     if isinstance(v, (int, float))]
            if items:
                probs = _compute_slot_probabilities(
                    sampler_config, [w for _, w in items])
                for (biome_id, _), p in zip(items, probs):
                    if biome_id != 'SELF':
                        results.append((biome_id, from_biome, p * y_scale))

        return results


class BiomeMetadata:
    """Holds metadata for a biome"""

    def __init__(self, biome_id: str):
        self.biome_id = biome_id
        self.extends: Optional[str] = None
        self.color: Optional[str] = None
        self.percentages: Dict[str, float] = {}  # preset_name -> percentage
        self.extrusion_percentages: Dict[str, float] = {}  # preset_name -> extrusion percentage
        self.is_extrusion: bool = False  # True if this biome only comes from extrusions
        self.extrusion_source: str = ""  # Which extrusion file(s) this comes from
        # Climate attributes (from default preset)
        self.biome_type: Optional[str] = None  # "Land" or "Ocean" (inferred from name)
        self.origin: Optional[str] = None  # "Land" or "Ocean" (derived from pipeline lineage)
        self.temperature: Optional[float] = None  # 0-1 (coldest to hottest)
        self.precipitation: Optional[float] = None  # 0-1 (driest to wettest)
        self.elevation: Optional[float] = None  # 0-1 (lowest to highest)

        # New properties from biome files
        self.vanilla_raw: Optional[str] = None  # raw 'vanilla' value from YAML (e.g., 'minecraft:jungle')
        self.vanilla_match: str = ""  # Matched 'Vanilla ID' or 'Multiple' or blank
        self.tags: List[str] = []  # merged tags from extends chain
        self._has_own_tags: bool = False  # True if biome YAML defines its own 'tags' key
        self.land_caves: bool = False
        self.special_caves: bool = False
        self.caverns_land: bool = False
        self.river: str = ""  # 'Desert' | 'Cold' | 'General' | ''
        self.category: str = "SURFACE"  # 'SURFACE' | 'RIVER' | 'SUBSURFACE'
        self.uses_elevation: bool = False  # True if terrain.sampler-2d uses elevation keywords
        self.terrain_parent: str = ""     # Abstract terrain biome (e.g. EQ_LAND, EQ_GLOBAL_OCEAN)
        self.elevation_sampler: str = ""  # Which elevation sampler: "elevation", "oceanElevation", ""
        self.avg_surface_y: Optional[float] = None  # Estimated surface Y when elevation not used
        self.is_elevation_flat: bool = False  # True if distributed to flat region in elevation.yml

    def set_climate(self, context: ClimateContext):
        """Set climate attributes from a ClimateContext"""
        self.biome_type = context.origin_type
        self.temperature = context.temperature
        self.precipitation = context.precipitation
        self.elevation = context.elevation

    def set_origin(self, origin: Optional[str]):
        """Set the pipeline-derived origin (Land/Ocean)"""
        self.origin = origin

    @staticmethod
    def format_climate_value(value: Optional[float]) -> str:
        """Format a climate value for CSV output"""
        if value is None:
            return ""
        return f"{value:.4f}"

    def to_csv_row(self, preset_names: List[str], include_extrusion: bool = True) -> List[str]:
        """Convert to CSV row format"""
        # Include new columns: Extends, VanillaID, LAND_CAVES, SPECIAL_CAVES, CAVERNS_LAND, River
        extends_str = self.extends if self.extends else ""
        land_caves_str = "True" if self.land_caves else ""
        special_caves_str = "True" if self.special_caves else ""
        caverns_str = "True" if self.caverns_land else ""
        uses_elevation_str = "True" if self.uses_elevation else ""
        elevation_flat_str = "True" if self.is_elevation_flat else ""
        avg_y_str = f"{self.avg_surface_y:.1f}" if self.avg_surface_y is not None else ""

        tags_str = str(self.tags) if self.tags else ""

        row = [
            self.biome_id,
            extends_str,
            self.vanilla_match or "",
            land_caves_str,
            special_caves_str,
            caverns_str,
            self.river or "",
            tags_str,
            self.category,                              # Category: SURFACE/RIVER/SUBSURFACE
            'extrusion' if self.is_extrusion else 'surface',
            self.origin or "",                          # Origin: Land/Ocean (pipeline-derived)
            self.biome_type or "",                      # Type: Land/Ocean (name-inferred legacy)
            self.format_climate_value(self.temperature),
            self.format_climate_value(self.precipitation),
            self.format_climate_value(self.elevation),
            self.terrain_parent,                        # Abstract terrain parent
            self.elevation_sampler,                     # Which elevation sampler used
            uses_elevation_str,                         # Boolean: uses any elevation
            elevation_flat_str,                         # Boolean: flat region in elevation.yml
            avg_y_str,                                  # Avg surface Y when no elevation
        ]
        # Add percentage columns for each preset
        for preset_name in preset_names:
            if self.is_extrusion:
                # For extrusion-only biomes, show extrusion percentage
                pct = self.extrusion_percentages.get(preset_name, 0.0)
            else:
                # For surface biomes, show surface percentage
                pct = self.percentages.get(preset_name, 0.0)
            row.append(f"{pct:.4%}")
        return row


class BiomeReader:
    """Reads biome files and extracts metadata including tags"""

    _cache: Optional[Dict[str, Path]] = None
    _metadata_cache: Dict[str, BiomeMetadata] = {}
    _valid_biomes: Optional[Set[str]] = None
    _biome_tags: Dict[str, List[str]] = {}  # biome_id -> list of tags
    _tag_index: Dict[str, Set[str]] = {}  # tag -> set of biome_ids with that tag

    @classmethod
    def build_cache(cls, biomes_dir: Path = Path("biomes")):
        """Build cache of all biome files including tags"""
        if cls._cache is not None:
            return

        print(f"Building biome file cache from {biomes_dir}...", file=sys.stderr)
        cls._cache = {}
        cls._valid_biomes = set()
        cls._biome_tags = {}
        cls._tag_index = defaultdict(set)

        for biome_file in biomes_dir.rglob("*.yml"):
            try:
                with open(biome_file, 'r') as f:
                    data = yaml.safe_load(f)
                    if data and data.get('type') == 'BIOME':
                        biome_id = data.get('id')
                        is_abstract = data.get('abstract', False)
                        if biome_id:
                            cls._cache[biome_id] = biome_file
                            # Only non-abstract biomes are valid for world generation
                            if not is_abstract:
                                cls._valid_biomes.add(biome_id)

                            # Extract tags (merge if biome ID already seen from another file)
                            tags = data.get('tags', [])
                            if isinstance(tags, list):
                                existing = cls._biome_tags.get(biome_id, [])
                                merged = list(dict.fromkeys(existing + tags))  # preserve order, dedupe
                                cls._biome_tags[biome_id] = merged
                                # Build reverse index: tag -> biomes
                                for tag in tags:
                                    cls._tag_index[tag].add(biome_id)
            except:
                continue

        # Count unique tags
        unique_tags = set(cls._tag_index.keys())
        biomes_with_tags = sum(1 for tags in cls._biome_tags.values() if tags)

        print(f"Cached {len(cls._cache)} biome files ({len(cls._valid_biomes)} valid, {len(cls._cache) - len(cls._valid_biomes)} abstract)", file=sys.stderr)
        print(f"Found {len(unique_tags)} unique tags across {biomes_with_tags} biomes", file=sys.stderr)

    @classmethod
    def find_biome_file(cls, biome_id: str) -> Optional[Path]:
        """Find the YAML file for a given biome ID"""
        cls.build_cache()
        return cls._cache.get(biome_id)

    @classmethod
    def get_all_valid_biomes(cls) -> Set[str]:
        """Get all valid (non-abstract) biome IDs"""
        cls.build_cache()
        return cls._valid_biomes.copy()

    @classmethod
    def get_biome_tags(cls, biome_id: str) -> List[str]:
        """Get tags for a specific biome"""
        cls.build_cache()
        return cls._biome_tags.get(biome_id, [])

    @classmethod
    def get_biomes_with_tag(cls, tag: str) -> Set[str]:
        """Get all biomes that have a specific tag"""
        cls.build_cache()
        return cls._tag_index.get(tag, set()).copy()

    @classmethod
    def matches_biome_or_tag(cls, identifier: str, biome_id: str) -> bool:
        """
        Check if a biome matches an identifier (either by ID or tag).

        Args:
            identifier: The ID or tag to match against (e.g., 'LAND_CAVES', 'JUNGLE', 'ALL')
            biome_id: The biome ID to check

        Returns:
            True if biome_id equals identifier OR biome_id has identifier as a tag
            Special case: 'ALL' matches every biome
        """
        cls.build_cache()

        # Special case: ALL matches everything
        if identifier == 'ALL':
            return True

        # Direct ID match
        if identifier == biome_id:
            return True

        # Tag match - check if the biome has this tag
        biome_tags = cls._biome_tags.get(biome_id, [])
        return identifier in biome_tags

    @classmethod
    def get_matching_biomes(cls, identifier: str) -> Set[str]:
        """
        Get all biomes that match an identifier (by ID or tag).

        Args:
            identifier: The ID or tag to match (e.g., 'LAND_CAVES', 'ALL')

        Returns:
            Set of biome IDs that match
        """
        cls.build_cache()

        # Special case: ALL matches all valid biomes
        if identifier == 'ALL':
            return cls._valid_biomes.copy()

        matching = set()

        # Direct ID match
        if identifier in cls._valid_biomes:
            matching.add(identifier)

        # Tag match - get all biomes with this tag
        matching.update(cls._tag_index.get(identifier, set()))

        return matching

    @classmethod
    def reset_cache(cls):
        """Reset internal caches (useful for tests)."""
        cls._cache = None
        cls._metadata_cache = {}
        cls._valid_biomes = None
        cls._biome_tags = {}
        cls._tag_index = defaultdict(set)
        cls._vanilla_map = None
        cls._terrain_cache = {}

    @classmethod
    def _load_vanilla_map(cls):
        """Load mapping from Vanilla Java biomes CSV file: vanilla id -> list of matches."""
        if getattr(cls, '_vanilla_map', None) is not None:
            return
        cls._vanilla_map = defaultdict(list)
        try:
            with open(Path('VanillaJavaBiomes.csv'), 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    vanilla_id = row.get('Vanilla ID') or row.get('VanillaID') or row.get('vanilla id')
                    if vanilla_id:
                        # Normalize: BIOME_JAGGED_PEAKS -> jagged_peaks
                        normalized = vanilla_id.replace('BIOME_', '').lower()
                        cls._vanilla_map[normalized].append(row)
        except Exception:
            cls._vanilla_map = defaultdict(list)

    @classmethod
    def _match_vanilla(cls, vanilla_raw: Optional[str]) -> str:
        """Return match string for vanilla_raw: exact match or 'Multiple' or ''."""
        if not vanilla_raw:
            return ""
        cls._load_vanilla_map()
        # Extract key: minecraft:jagged_peaks -> jagged_peaks
        vanilla_key = vanilla_raw.split(':')[-1] if ':' in vanilla_raw else vanilla_raw
        # Normalize to lowercase
        vanilla_key_normalized = vanilla_key.lower()
        matches = cls._vanilla_map.get(vanilla_key_normalized, [])
        if len(matches) == 0:
            return ""
        if len(matches) == 1:
            # Return the original key from biome file (e.g., jagged_peaks)
            return vanilla_key
        return "Multiple"

    @classmethod
    def _merge_extends(cls, biome_id: str, metadata: BiomeMetadata, visited: Optional[Set[str]] = None):
        """Merge properties from parent biomes transitively. Child takes precedence."""
        if visited is None:
            visited = set()
        if biome_id in visited:
            return
        visited.add(biome_id)

        # Normalize extends into list
        extends_field = metadata.extends
        if not extends_field:
            return
        parent_ids = []
        if isinstance(extends_field, list):
            parent_ids = extends_field
        elif isinstance(extends_field, str):
            parent_ids = [extends_field]

        for parent_id in parent_ids:
            parent_meta = cls.read_biome_metadata(parent_id)
            # Recurse first to gather parent's inherited properties
            cls._merge_extends(parent_id, parent_meta, visited)

            # Terra extends: parameters from parent are only used if NOT already
            # defined in the child config.  If the child defines 'tags', the
            # parent's tags are ignored entirely (no union/merge).
            if not metadata._has_own_tags:
                parent_tags = getattr(parent_meta, 'tags', [])
                if parent_tags:
                    metadata.tags = list(parent_tags)
                    metadata._has_own_tags = parent_meta._has_own_tags

            # Merge vanilla_raw if child doesn't have it
            if not metadata.vanilla_raw and parent_meta.vanilla_raw:
                metadata.vanilla_raw = parent_meta.vanilla_raw

            # Merge color if missing
            if not metadata.color and parent_meta.color:
                metadata.color = parent_meta.color

    # Cache for terrain analysis results
    _terrain_cache: Dict[str, Dict] = {}

    @classmethod
    def _find_elevation_keywords_in_config(cls, config: Any) -> Set[str]:
        """Recursively find which elevation keywords appear in a sampler config."""
        found: Set[str] = set()
        if isinstance(config, str):
            for keyword in ELEVATION_KEYWORDS:
                if keyword in config:
                    found.add(keyword)
        elif isinstance(config, dict):
            expression = config.get('expression', '')
            if isinstance(expression, str):
                for keyword in ELEVATION_KEYWORDS:
                    if keyword in expression:
                        found.add(keyword)
            for key in ['sampler', 'samplers', 'warp', 'lookup']:
                nested = config.get(key)
                if nested:
                    if isinstance(nested, dict):
                        found.update(cls._find_elevation_keywords_in_config(nested))
                        for v in nested.values():
                            found.update(cls._find_elevation_keywords_in_config(v))
                    elif isinstance(nested, list):
                        for item in nested:
                            found.update(cls._find_elevation_keywords_in_config(item))
        elif isinstance(config, list):
            for item in config:
                found.update(cls._find_elevation_keywords_in_config(item))
        return found

    @classmethod
    def _resolve_terrain_config(cls, biome_id: str,
                                _visited: Optional[Set[str]] = None
                                ) -> Tuple[Optional[Dict], Optional[Dict], Optional[str]]:
        """
        Resolve terrain.sampler and terrain.sampler-2d through the extends chain.

        Returns (sampler_3d, sampler_2d, terrain_parent_id):
          - sampler_3d:  the resolved 3D terrain sampler config dict (or None)
          - sampler_2d:  the resolved 2D terrain sampler config dict (or None)
          - terrain_parent_id: the biome ID that first defined terrain.sampler-2d
        """
        if _visited is None:
            _visited = set()
        if biome_id in _visited:
            return None, None, None
        _visited.add(biome_id)

        biome_file = cls.find_biome_file(biome_id)
        if not biome_file:
            return None, None, None

        try:
            with open(biome_file, 'r') as f:
                data = yaml.safe_load(f)
        except Exception:
            return None, None, None

        terrain = data.get('terrain', {})
        if not isinstance(terrain, dict):
            terrain = {}

        sampler_3d = terrain.get('sampler')
        sampler_2d = terrain.get('sampler-2d')

        # If this biome defines sampler-2d, it IS the terrain parent
        if sampler_2d is not None:
            return sampler_3d, sampler_2d, biome_id

        # Walk extends chain to find terrain definition
        extends = data.get('extends')
        if extends:
            parent_ids = [extends] if isinstance(extends, str) else extends
            for parent_id in parent_ids:
                p_3d, p_2d, parent_name = cls._resolve_terrain_config(
                    parent_id, _visited)
                if p_2d is not None:
                    # If this biome defines a 3D sampler but no 2D, use its 3D + parent's 2D
                    return (sampler_3d if sampler_3d else p_3d), p_2d, parent_name

        return sampler_3d, None, None

    @classmethod
    def _resolve_terrain_config_3d(cls, biome_id: str,
                                    _visited: Optional[Set[str]] = None
                                    ) -> Tuple[Optional[Dict], Optional[Dict], Optional[str]]:
        """
        Like _resolve_terrain_config but finds the parent that defined terrain.sampler (3D).
        Used as fallback for biomes like EQ_MESA that embed elevation in the 3D sampler.
        """
        if _visited is None:
            _visited = set()
        if biome_id in _visited:
            return None, None, None
        _visited.add(biome_id)

        biome_file = cls.find_biome_file(biome_id)
        if not biome_file:
            return None, None, None

        try:
            with open(biome_file, 'r') as f:
                data = yaml.safe_load(f)
        except Exception:
            return None, None, None

        terrain = data.get('terrain', {})
        if not isinstance(terrain, dict):
            terrain = {}

        sampler_3d = terrain.get('sampler')

        # If this biome defines a 3D sampler, it's the terrain parent
        if sampler_3d is not None:
            return sampler_3d, None, biome_id

        extends = data.get('extends')
        if extends:
            parent_ids = [extends] if isinstance(extends, str) else extends
            for parent_id in parent_ids:
                p_3d, _, parent_name = cls._resolve_terrain_config_3d(
                    parent_id, _visited)
                if p_3d is not None:
                    return p_3d, None, parent_name

        return None, None, None

    @classmethod
    def _extract_base_y(cls, sampler_3d: Optional[Dict]) -> Optional[float]:
        """
        Extract the base Y level from a 3D terrain sampler.

        Most ORIGEN2 biomes use: expression: -y + base
        where base is resolved from customization.yml:terrain-base-y-level (65)
        or terrain-ocean-base-y-level (60), or a hardcoded value.
        """
        if not isinstance(sampler_3d, dict):
            return None

        variables = sampler_3d.get('variables', {})
        if not isinstance(variables, dict):
            return None

        # Look for 'base' variable
        base_val = variables.get('base')
        if base_val is None:
            return None

        # If it's a direct number, use it
        if isinstance(base_val, (int, float)):
            return float(base_val)

        # If it's a reference like $customization.yml:terrain-base-y-level
        if isinstance(base_val, str):
            if 'terrain-base-y-level' in base_val:
                return 65.0   # from customization.yml
            if 'terrain-ocean-base-y-level' in base_val:
                return 60.0   # from customization.yml

        return None

    @classmethod
    def _estimate_avg_surface_y(cls, sampler_3d: Optional[Dict],
                                sampler_2d: Optional[Dict]) -> Optional[float]:
        """
        Estimate the average surface Y for a biome.

        For biomes with the pattern: density = -y + base + sampler2d(x,z)
        the surface is at Y = base + sampler2d(x,z) on average.

        For biomes NOT using elevation, sampler-2d is typically:
          - CONSTANT → 0 → surface at Y = base
          - Simple noise like (simplex(x,z)+1)/6 → avg ≈ 0.167 → surface ≈ base + 0.167

        For biomes USING elevation:
          - sampler-2d = scale * elevation(x,z) → avg depends on elevation distribution
          - We use the climate elevation value from the pipeline to estimate this per-biome
          - Return None here; the pipeline elevation value is used instead
        """
        base_y = cls._extract_base_y(sampler_3d)
        if base_y is None:
            return None

        if not isinstance(sampler_2d, dict):
            return base_y  # No 2D sampler → flat at base

        s2d_type = sampler_2d.get('type', '')

        # CONSTANT → flat surface
        if s2d_type == 'CONSTANT':
            val = sampler_2d.get('value', 0.0)
            if isinstance(val, (int, float)):
                return base_y + float(val)
            return base_y

        # Simple EXPRESSION without elevation → try to evaluate average
        if s2d_type == 'EXPRESSION':
            expr = str(sampler_2d.get('expression', ''))
            # If it references elevation, we can't compute a single average
            for kw in ELEVATION_KEYWORDS:
                if kw in expr:
                    return None

            # For simple expressions like "(simplex(x, z)+1)/6", average of
            # simplex ≈ 0, so average ≈ (0+1)/6 = 0.167
            # For general expressions, try replacing function calls with 0
            try:
                import re as _re
                # Replace sampler calls like func(x, z) with 0
                simplified = _re.sub(r'[a-zA-Z_]\w*\s*\([^)]*\)', '0', expr)
                avg = eval(simplified.strip(), {"__builtins__": {}}, {})
                if isinstance(avg, (int, float)):
                    return base_y + float(avg)
            except Exception:
                pass

        return base_y  # Fall back to base

    @classmethod
    def _estimate_avg_surface_y_from_3d(cls, sampler_3d: Optional[Dict]) -> Optional[float]:
        """
        Estimate average surface Y from a 3D-only terrain sampler.

        For 3D expressions like: -y + base + (noise(x,z)+1)/2 * height + ...
        Surface is where density=0: Y = base + f(x,z)

        Uses numerical bisection: evaluate density(y) with noise calls replaced
        by 0 (their mean), and find the Y where density crosses zero.
        """
        if not isinstance(sampler_3d, dict):
            return None

        base_y = cls._extract_base_y(sampler_3d)
        if base_y is None:
            return None

        expression = sampler_3d.get('expression', '')
        if not isinstance(expression, str):
            return base_y

        variables = sampler_3d.get('variables', {})
        if not isinstance(variables, dict):
            variables = {}

        import re as _re

        # Strip comments and collapse to single line
        expr = _re.sub(r'//[^\n]*', '', expression)
        expr = ' '.join(expr.split())
        expr = _re.sub(r'\^', '**', expr)  # caret → Python **

        # Replace x/z sampler function calls with 0 (symmetric noise mean).
        # Keep y in the expression so we can evaluate density(y).
        # Iteratively replace innermost calls first (handles nesting).
        for _ in range(5):
            new_expr = _re.sub(r'[a-zA-Z_]\w*\s*\([^()]*\)', '0', expr)
            if new_expr == expr:
                break
            expr = new_expr

        # Build variable substitution dict
        var_vals = {}
        for k, v in variables.items():
            if k == '<<':
                continue
            if isinstance(v, (int, float)):
                var_vals[k] = float(v)
            elif isinstance(v, str) and 'terrain-base-y-level' in v:
                var_vals[k] = 65.0
            elif isinstance(v, str) and 'legacy-terrain-base-y-level' in v:
                var_vals[k] = 65.0
            elif isinstance(v, str) and 'terrain-ocean-base-y-level' in v:
                var_vals[k] = 60.0
            elif isinstance(v, str) and 'terrain-height' in v:
                var_vals[k] = 180.0

        safe_builtins = {'round': round, 'min': min, 'max': max, 'abs': abs}

        def eval_density(y_val: float) -> Optional[float]:
            try:
                return float(eval(expr.strip(), {"__builtins__": {}},
                                  {**var_vals, **safe_builtins, 'y': y_val}))
            except Exception:
                return None

        # Bisection: find Y where density crosses 0
        # density is positive below surface (solid) and negative above (air)
        lo, hi = -64.0, 320.0
        d_lo = eval_density(lo)
        d_hi = eval_density(hi)
        if d_lo is None or d_hi is None:
            return base_y

        # If no sign change, density is constant-sign — fall back
        if d_lo * d_hi > 0:
            return base_y

        for _ in range(50):
            mid = (lo + hi) / 2
            d_mid = eval_density(mid)
            if d_mid is None:
                return base_y
            if abs(d_mid) < 0.01:
                break
            if d_lo * d_mid <= 0:
                hi = mid
            else:
                lo = mid
                d_lo = d_mid

        avg_y = (lo + hi) / 2
        if -64 < avg_y < 320:
            return round(avg_y, 1)

        return base_y

    @classmethod
    def _analyze_terrain(cls, biome_id: str) -> Dict:
        """
        Full terrain analysis for a biome.

        Returns dict with:
          terrain_parent:    abstract biome ID that defines sampler-2d
          elevation_sampler: "elevation", "oceanElevation", or ""
          uses_elevation:    True if any elevation keyword found
          avg_surface_y:     estimated avg surface Y (only for non-elevation biomes)
        """
        if biome_id in cls._terrain_cache:
            return cls._terrain_cache[biome_id]

        result = {
            'terrain_parent': '',
            'elevation_sampler': '',
            'uses_elevation': False,
            'avg_surface_y': None,
        }

        sampler_3d, sampler_2d, terrain_parent = cls._resolve_terrain_config(biome_id)
        if terrain_parent:
            result['terrain_parent'] = terrain_parent

        # Collect elevation keywords from BOTH 3D and 2D samplers.
        # Some biomes (e.g. EQ_MESA) put elevation directly in the 3D sampler:
        #   expression: -y + base + scale * elevationDetailed(x, z)
        all_keywords: Set[str] = set()
        if sampler_2d is not None:
            all_keywords.update(cls._find_elevation_keywords_in_config(sampler_2d))
        if sampler_3d is not None:
            all_keywords.update(cls._find_elevation_keywords_in_config(sampler_3d))

        if all_keywords:
            result['uses_elevation'] = True
            if 'oceanElevation' in all_keywords:
                result['elevation_sampler'] = 'oceanElevation'
            elif any(k in all_keywords for k in ('elevation', 'elevationDetailed',
                                                  'spotBaseElevation',
                                                  'BiomeShapeLandmassBaseOffset')):
                result['elevation_sampler'] = 'elevation'
            else:
                result['elevation_sampler'] = ', '.join(sorted(all_keywords))

        # If no terrain parent was found from sampler-2d, try to find one from
        # the 3D sampler (biomes like EQ_MESA define terrain only in sampler 3D).
        # Also resolve the 3D sampler from parents for elevation keyword checking.
        if not result['terrain_parent']:
            s3d_fallback, _, terrain_parent_3d = cls._resolve_terrain_config_3d(biome_id)
            if terrain_parent_3d:
                result['terrain_parent'] = terrain_parent_3d
            # If we didn't get a 3D sampler from the primary resolve, use the fallback
            if sampler_3d is None and s3d_fallback is not None:
                sampler_3d = s3d_fallback
                fb_keywords = cls._find_elevation_keywords_in_config(sampler_3d)
                if fb_keywords:
                    all_keywords.update(fb_keywords)
                    result['uses_elevation'] = True
                    if 'oceanElevation' in all_keywords:
                        result['elevation_sampler'] = 'oceanElevation'
                    elif any(k in all_keywords for k in ('elevation', 'elevationDetailed',
                                                          'spotBaseElevation')):
                        result['elevation_sampler'] = 'elevation'
                    else:
                        result['elevation_sampler'] = ', '.join(sorted(all_keywords))

        if not result['uses_elevation']:
            if sampler_2d is not None:
                result['avg_surface_y'] = cls._estimate_avg_surface_y(
                    sampler_3d, sampler_2d)
            else:
                result['avg_surface_y'] = cls._estimate_avg_surface_y_from_3d(sampler_3d)

        cls._terrain_cache[biome_id] = result
        return result

    @classmethod
    def read_biome_metadata(cls, biome_id: str) -> BiomeMetadata:
        """Read metadata for a biome and merge properties from parents"""
        # Check metadata cache first
        if biome_id in cls._metadata_cache:
            return cls._metadata_cache[biome_id]

        metadata = BiomeMetadata(biome_id)

        biome_file = cls.find_biome_file(biome_id)
        if not biome_file:
            cls._metadata_cache[biome_id] = metadata
            return metadata

        try:
            with open(biome_file, 'r') as f:
                data = yaml.safe_load(f)
                metadata.extends = data.get('extends')
                metadata.color = data.get('color')
                # Raw vanilla value
                metadata.vanilla_raw = data.get('vanilla')
                # Start with tags found on this file
                metadata.tags = cls.get_biome_tags(biome_id)
                # Track whether this biome defines its own 'tags' key
                metadata._has_own_tags = 'tags' in data
        except Exception as e:
            print(f"Warning: Could not read metadata for {biome_id}: {e}", file=sys.stderr)

        # Merge transitive properties from parents
        cls._merge_extends(biome_id, metadata)

        # After merge, set boolean flags from tags
        tags_set = set([t for t in (metadata.tags or [])])
        metadata.land_caves = 'LAND_CAVES' in tags_set
        metadata.special_caves = 'SPECIAL_CAVES' in tags_set
        metadata.caverns_land = 'CAVERNS_LAND' in tags_set

        # River detection: any tag starting with USE_ and containing RIVER
        river_tags = [t for t in tags_set if t.startswith('USE_') and 'RIVER' in t]
        if river_tags:
            # Categorize: Desert > Cold > Frozen > Lukewarm > Tropical > General
            if any('DESERT' in t for t in river_tags):
                metadata.river = 'Desert'
            elif any('COLD' in t for t in river_tags):
                metadata.river = 'Cold'
            elif any('FROZEN' in t or 'GLACIER' in t for t in river_tags):
                metadata.river = 'Frozen'
            elif any('LUKEWARM' in t for t in river_tags):
                metadata.river = 'Lukewarm'
            elif any('TROPICAL' in t for t in river_tags):
                metadata.river = 'Tropical'
            else:
                metadata.river = 'General'
        else:
            metadata.river = ''

        # Resolve VanillaID match
        metadata.vanilla_match = cls._match_vanilla(metadata.vanilla_raw)

        # Terrain analysis: elevation usage, terrain parent, avg surface Y
        terrain_info = cls._analyze_terrain(biome_id)
        metadata.uses_elevation = terrain_info['uses_elevation']
        metadata.terrain_parent = terrain_info['terrain_parent']
        metadata.elevation_sampler = terrain_info['elevation_sampler']
        metadata.avg_surface_y = terrain_info['avg_surface_y']

        cls._metadata_cache[biome_id] = metadata
        return metadata


class PresetAnalyzer:
    """Analyzes a Terra preset and calculates biome percentages"""

    def __init__(self, preset_path: Path):
        self.preset_path = preset_path
        self.preset_name = preset_path.stem

        # Load preset YAML
        with open(preset_path, 'r') as f:
            self.preset_data = yaml.safe_load(f)

    def get_source_distribution(self) -> BiomeDistribution:
        """Extract initial biome distribution from preset source"""
        dist = BiomeDistribution()

        try:
            biomes_config = self.preset_data.get('biomes', {})
            provider = biomes_config.get('provider', {})
            pipeline = provider.get('pipeline', {})
            source = pipeline.get('source', {})

            # Source might be a string reference or inline config
            if isinstance(source, str):
                print(f"  Source is a reference: {source} (skipping)", file=sys.stderr)
                return dist

            biomes = source.get('biomes', {})

            # Biomes might also be a string reference
            if isinstance(biomes, str):
                print(f"  Biomes is a reference: {biomes} (skipping)", file=sys.stderr)
                return dist

            if not isinstance(biomes, dict):
                print(f"  Unexpected biomes format: {type(biomes)}", file=sys.stderr)
                return dist

            # Parse source biomes and weights.  The source SAMPLER assigns each
            # biome its slot of [-1,1]; for a plain uniform sampler this reduces
            # to weight/total, but a spatial placer (e.g. spotPlacer, registered
            # in NAMED_SAMPLER_POINT_MASSES) stamps the rare _land_spot/_ocean_spot
            # slots at a far lower rate than their nominal weight.  Honour it.
            biome_items = [(b, int(w)) for b, w in biomes.items()
                           if isinstance(w, (int, float))]
            total_weight = sum(w for _, w in biome_items)
            if total_weight > 0:
                sampler_config = source.get('sampler') if isinstance(source, dict) else None
                if sampler_config:
                    probs = _compute_slot_probabilities(
                        _resolve_pack_refs(sampler_config), [w for _, w in biome_items])
                else:
                    probs = [w / total_weight for _, w in biome_items]
                for (biome, _), prob in zip(biome_items, probs):
                    dist.set(biome, prob)

                    # Set origin based on source biome type
                    biome_lower = biome.lower()
                    if biome_lower in BiomeDistribution.OCEAN_SOURCES:
                        dist.set_origin(biome, "Ocean")
                    elif biome_lower in BiomeDistribution.LAND_SOURCES:
                        dist.set_origin(biome, "Land")

        except Exception as e:
            print(f"Warning: Could not parse source biomes: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc(file=sys.stderr)

        return dist

    def get_stage_files(self) -> List[Path]:
        """Extract list of stage files from preset"""
        stage_files = []

        try:
            biomes_config = self.preset_data.get('biomes', {})
            provider = biomes_config.get('provider', {})
            pipeline = provider.get('pipeline', {})
            stages = pipeline.get('stages', [])

            for stage in stages:
                if isinstance(stage, str):
                    # Include reference: << file.yml:stages
                    match = re.match(r'<<\s+([^:]+\.yml):stages', stage)
                    if match:
                        stage_file = Path(match.group(1))
                        stage_files.append(stage_file)
                elif isinstance(stage, dict):
                    # Inline stage - we'll process it directly
                    stage_files.append(('INLINE', stage))

        except Exception as e:
            print(f"Warning: Could not parse stages: {e}", file=sys.stderr)

        return stage_files

    def load_stage_file(self, stage_path: Path, record_failure: bool = True) -> List[Dict]:
        """Load stages from a stage file with schema validation"""
        validator = get_validator()

        # Use validator to load and check YAML
        data, yaml_errors = validator.validate_yaml_file(stage_path)

        if yaml_errors:
            for err in yaml_errors:
                validator.errors.append((str(stage_path), "file", err))
            print(f"Warning: Could not load {stage_path}: {yaml_errors[0]}", file=sys.stderr)
            # Record that this stage file failed for this preset
            if record_failure:
                validator.record_failed_stage_load(str(stage_path), self.preset_name)
            return []

        if data is None:
            # Record failure if we couldn't load the file
            if record_failure:
                validator.record_failed_stage_load(str(stage_path), self.preset_name)
            return []

        stages = data.get('stages', [])
        if not isinstance(stages, list):
            return []

        # Validate each stage
        for i, stage in enumerate(stages):
            validator.validate_stage(stage, str(stage_path), i)

        # Resolve cross-file pack variable references (e.g. coast cutoff) so the
        # sampler CDF resolver can evaluate threshold comparisons instead of
        # falling back to uniform.
        return _resolve_pack_refs(stages)

    def get_extrusion_refs(self) -> List[Tuple[str, Path]]:
        """Extract list of extrusion file references from preset"""
        extrusion_refs = []

        try:
            biomes_config = self.preset_data.get('biomes', {})
            extrusions = biomes_config.get('extrusions', [])

            for extrusion in extrusions:
                if isinstance(extrusion, str):
                    # Include reference: << file.yml:extrusions
                    match = re.match(r'<<\s+([^:]+\.yml):extrusions', extrusion)
                    if match:
                        extrusion_file = Path(match.group(1))
                        extrusion_refs.append((extrusion_file.stem, extrusion_file))

        except Exception as e:
            print(f"Warning: Could not parse extrusions: {e}", file=sys.stderr)

        return extrusion_refs

    def calculate_extrusions(self) -> ExtrusionDistribution:
        """Extract and process extrusion definitions"""
        extrusion_dist = ExtrusionDistribution()

        extrusion_refs = self.get_extrusion_refs()
        if not extrusion_refs:
            return extrusion_dist

        print(f"  Processing {len(extrusion_refs)} extrusion files...")

        for source_name, extrusion_path in extrusion_refs:
            print(f"    - {extrusion_path}")
            extrusions = ExtrusionProcessor.parse_extrusion_file(extrusion_path)

            for extrusion_config in extrusions:
                results = ExtrusionProcessor.process_extrusion(extrusion_config, source_name)
                for biome_id, parent, weight_fraction in results:
                    extrusion_dist.add_extrusion_biome(biome_id, parent, weight_fraction, source_name)

        # Log what we found
        extrusion_biomes = extrusion_dist.get_extrusion_biomes()
        if extrusion_biomes:
            print(f"  Found {len(extrusion_biomes)} extrusion biomes: {sorted(extrusion_biomes)}")

        return extrusion_dist

    def calculate_percentages(self) -> BiomeDistribution:
        """Calculate final biome percentages for this preset"""
        print(f"\nProcessing preset: {self.preset_name}")

        # Get initial distribution
        distribution = self.get_source_distribution()
        print(f"Initial distribution:")
        print(distribution)

        # Get and process stages
        stage_refs = self.get_stage_files()

        for i, stage_ref in enumerate(stage_refs):
            if isinstance(stage_ref, tuple) and stage_ref[0] == 'INLINE':
                # Inline stage
                print(f"\nStage {i+1}: INLINE")
                _, stage_config = stage_ref
                distribution = StageProcessor.process_stage(stage_config, distribution)
            else:
                # File reference
                print(f"\nStage {i+1}: {stage_ref}")
                stages = self.load_stage_file(stage_ref)

                for stage_config in stages:
                    distribution = StageProcessor.process_stage(stage_config, distribution)

                # Debug: Show distribution after key stages
                if 'set_biomes_in_climates' in str(stage_ref):
                    print(f"  After {stage_ref.name}:")
                    print(f"    Total biomes: {len(distribution.probabilities)}")
                    print(f"    Top 5: {distribution.get_top_biomes(5)}")

        print(f"\nFinal distribution:")
        print(distribution)

        return distribution


def generate_csv_output(
    results: Dict[str, BiomeDistribution],
    extrusion_results: Dict[str, ExtrusionDistribution],
    output_path: Path,
    default_preset: str = "origen2",
    climate_preset: Optional[str] = None,
):
    """
    Generate BiomeTable.csv with percentages and climate data.

    The table now includes:
    - Source column: 'surface' for regular biomes, 'extrusion' for underground biomes
    - Type column: 'Land' or 'Ocean' based on biome origin
    - Temperature column: normalized temperature value (0=coldest, 1=hottest)
    - Precipitation column: normalized precipitation value (0=driest, 1=wettest)
    - Elevation column: normalized elevation value (0=lowest, 1=highest)
    - Percentages: surface biomes sum to 100%, extrusion biomes shown separately

    Climate data is derived from climate_preset (defaults to CLIMATE_PRESET_NAME constant).
    The pack's active preset (default_preset) is used for category/origin/percentage data.
    """
    # Determine which preset to use for climate data.
    # Falls back through: climate_preset arg → CLIMATE_PRESET_NAME constant → default_preset.
    if climate_preset is None:
        climate_preset = CLIMATE_PRESET_NAME
    if climate_preset not in results:
        climate_preset = default_preset
    print(f"\nGenerating CSV output: {output_path}")

    # Get all valid biomes from file system (non-abstract biomes)
    valid_biomes = BiomeReader.get_all_valid_biomes()
    print(f"Valid biomes found in files: {len(valid_biomes)}")

    # Collect all biomes referenced in distributions (surface)
    surface_biomes = set()
    for distribution in results.values():
        surface_biomes.update(distribution.probabilities.keys())

    print(f"Biomes found in surface distributions: {len(surface_biomes)}")

    # Collect all biomes referenced in extrusions
    extrusion_biomes_set = set()
    for extrusion_dist in extrusion_results.values():
        extrusion_biomes_set.update(extrusion_dist.get_extrusion_biomes())

    print(f"Biomes found in extrusions: {len(extrusion_biomes_set)}")

    # Determine which biomes are extrusion-only (not in surface distributions)
    extrusion_only_biomes = extrusion_biomes_set - surface_biomes
    print(f"Extrusion-only biomes: {len(extrusion_only_biomes)}")
    if extrusion_only_biomes:
        print(f"  {sorted(extrusion_only_biomes)}")

    # Combine all sets - we want all valid biomes plus any referenced
    all_biomes = valid_biomes | surface_biomes | extrusion_biomes_set

    print(f"Total biomes to include in table: {len(all_biomes)}")

    # Build set of biomes distributed to the flat region in elevation.yml
    elevation_flat_biomes = _build_elevation_flat_biomes()
    print(f"Elevation flat biomes: {len(elevation_flat_biomes)}")

    # Identify unresolved intermediate biomes
    # An intermediate biome is one that appears in distributions but is NOT a valid biome
    unresolved_biomes = set()
    for biome_id in surface_biomes:
        # A biome is intermediate/unresolved if:
        # 1. It's not in the valid biomes set (no valid biome file exists)
        # 2. It's not 'SELF' (which is a special keyword, not a biome)
        if biome_id not in valid_biomes and biome_id != 'SELF':
            unresolved_biomes.add(biome_id)
            print(f"  Warning: Unresolved intermediate biome: {biome_id}", file=sys.stderr)

    # Read metadata for each biome
    biome_metadata_map = {}
    for biome_id in sorted(all_biomes):
        # For unresolved biomes, rename them to make it clear they're not final biomes
        display_id = biome_id
        if biome_id in unresolved_biomes:
            # Convert intermediate names like "_desert" to "UNLINKED_desert"
            if biome_id.startswith('_'):
                display_id = f"UNLINKED{biome_id}"  # Keeps the underscore: UNLINKED_desert
            else:
                display_id = f"UNLINKED_{biome_id}"

        metadata = BiomeReader.read_biome_metadata(biome_id)
        metadata.biome_id = display_id  # Use the display ID in output

        # Mark if this is an extrusion-only biome
        if biome_id in extrusion_only_biomes:
            metadata.is_extrusion = True
            # Get the extrusion source from any preset that has it
            for preset_name, extrusion_dist in extrusion_results.items():
                source_info = extrusion_dist.get_source_info(biome_id)
                if source_info:
                    metadata.extrusion_source = source_info
                    break

        # Add percentages from all presets
        for preset_name, distribution in results.items():
            # Surface percentage
            metadata.percentages[preset_name] = distribution.get(biome_id)

            # Extrusion percentage (calculated from parent biomes)
            if preset_name in extrusion_results:
                extrusion_dist = extrusion_results[preset_name]
                extrusion_pct = extrusion_dist.calculate_percentage(biome_id, distribution)
                metadata.extrusion_percentages[preset_name] = extrusion_pct

        # Get origin from default preset (pipeline-derived)
        if default_preset in results:
            origin = results[default_preset].get_origin(biome_id)
            metadata.set_origin(origin)

        # Set distribution category from the full-pipeline preset (climate_preset = "origen2")
        # Using default_preset (ExploreTest) would miss RIVER biomes because ExploreTest
        # has different/incomplete stages (climate stages commented out, etc.)
        cat_preset = climate_preset if climate_preset in results else default_preset
        if cat_preset in results:
            cat = results[cat_preset].get_category(biome_id)
            metadata.category = cat.value

        # Override category for extrusion-only biomes
        if biome_id in extrusion_only_biomes:
            metadata.category = DistributionCategory.SUBSURFACE.value

        # Mark if this biome is distributed to the flat region in elevation.yml
        if biome_id in elevation_flat_biomes:
            metadata.is_elevation_flat = True

        biome_metadata_map[display_id] = metadata

    # Get sorted list of preset names
    preset_names = sorted(results.keys())

    # Get climate data from the climate preset (may differ from pack's active preset)
    print(f"Using '{climate_preset}' preset for climate data (T/P/E columns)")
    climate_distribution = results.get(climate_preset)
    if climate_distribution:
        # Fill in 0.5 for any biome that didn't pass through a named climate stage
        climate_distribution.climate.apply_default_climate(all_biomes)
        n_nondefault = sum(
            1 for b in all_biomes
            if climate_distribution.climate.contexts.get(b) is not None
            and abs((climate_distribution.climate.contexts[b].temperature or 0.5) - 0.5) > 0.001
        )
        print(f"  Biomes with non-default temperature: {n_nondefault} / {len(all_biomes)}")

        # Apply climate data to metadata
        for biome_id, metadata in biome_metadata_map.items():
            # Get the original biome ID (strip UNLINKED prefix if present)
            original_id = biome_id
            if biome_id.startswith('UNLINKED_'):
                original_id = biome_id[9:]  # Remove 'UNLINKED_' prefix
            elif biome_id.startswith('UNLINKED'):
                original_id = biome_id[8:]  # Remove 'UNLINKED' prefix (keeps underscore)

            context = climate_distribution.climate.get_context(original_id)
            metadata.set_climate(context)
    else:
        print(f"  Warning: Climate preset '{climate_preset}' not found, climate data unavailable")

    # Write CSV
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)

        # Header row
        header = [
            'BiomeID', 'Extends', 'VanillaID', 'LAND_CAVES', 'SPECIAL_CAVES', 'CAVERNS_LAND', 'River', 'Tags',
            'Category', 'Source', 'Origin', 'Type', 'Temperature', 'Precipitation', 'Elevation',
            'TerrainParent', 'ElevationSampler', 'UsesElevation', 'ElevationFlat', 'AvgSurfaceY'
        ] + preset_names
        writer.writerow(header)

        # Data rows
        for biome_id in sorted(biome_metadata_map.keys()):
            metadata = biome_metadata_map[biome_id]
            row = metadata.to_csv_row(preset_names)
            writer.writerow(row)

    print(f"CSV written successfully: {output_path}")    
    # If a SuggestedImprovements.md exists in project root or .scripts, copy it to artifacts
    suggested_candidates = [Path('SuggestedImprovements.md'), Path('.scripts/SuggestedImprovements.md')]
    for cand in suggested_candidates:
        if cand.exists():
            try:
                dest = Path('.artifacts') / 'SuggestedImprovements.md'
                with open(cand, 'r', encoding='utf-8') as srcf, open(dest, 'w', encoding='utf-8') as dstf:
                    dstf.write(srcf.read())
                print(f"Copied {cand} -> {dest}")
                break
            except Exception as e:
                print(f"Warning: Could not copy SuggestedImprovements.md: {e}", file=sys.stderr)
    else:
        # Create an initial placeholder file in artifacts if none found
        try:
            dest = Path('.artifacts') / 'SuggestedImprovements.md'
            with open(dest, 'w', encoding='utf-8') as f:
                f.write("# Suggested Improvements\n\nNo suggested improvements generated.\n")
            print(f"Created placeholder {dest}")
        except Exception as e:
            print(f"Warning: Could not create placeholder SuggestedImprovements.md: {e}", file=sys.stderr)
    print(f"  Valid biomes: {len(valid_biomes)}")
    print(f"  Surface biomes: {len(surface_biomes)}")
    print(f"  Extrusion-only biomes: {len(extrusion_only_biomes)}")
    print(f"  Unresolved intermediates: {len(unresolved_biomes)}")


def get_default_preset_from_pack() -> str:
    """
    Read pack.yml to find the default preset name.
    Returns the preset name (e.g., 'origen2') or 'origen2' as fallback.
    """
    pack_path = Path("pack.yml")
    if not pack_path.exists():
        print("  Warning: pack.yml not found, using 'origen2' as default preset", file=sys.stderr)
        return "origen2"

    try:
        with open(pack_path, 'r') as f:
            pack_data = yaml.safe_load(f)

        biomes_ref = pack_data.get('biomes')
        if isinstance(biomes_ref, str):
            # Parse reference like "$biome-distribution/presets/origen2.yml:biomes"
            match = re.match(r'\$biome-distribution/presets/([^.]+)\.yml:biomes', biomes_ref)
            if match:
                return match.group(1)

        print("  Warning: Could not parse biomes reference in pack.yml, using 'origen2'", file=sys.stderr)
        return "origen2"
    except Exception as e:
        print(f"  Warning: Error reading pack.yml: {e}, using 'origen2'", file=sys.stderr)
        return "origen2"


def main():
    """Main entry point"""
    preset_dir = Path("biome-distribution/presets")
    artifacts_dir = Path(".artifacts")
    output_file = artifacts_dir / "BiomeTable.csv"

    if not preset_dir.exists():
        print(f"Error: Preset directory not found: {preset_dir}", file=sys.stderr)
        sys.exit(1)

    # Ensure artifacts directory exists
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create artifacts directory {artifacts_dir}: {e}", file=sys.stderr)

    # CLI flag: --explain-expressions emits per-expression resolution diagnostics
    # to stderr (which path matched, or UNRESOLVED for uniform fallback).
    if '--explain-expressions' in sys.argv:
        import sampler_cdf as _sc
        _sc.EXPLAIN_EXPRESSIONS = True
        print("Expression-resolution diagnostics enabled (stderr)", file=sys.stderr)

    print("Terra Biome Percentage Calculator")
    print("=" * 70)

    # Get default preset from pack.yml
    default_preset = get_default_preset_from_pack()
    print(f"Default preset (from pack.yml): {default_preset}")

    # Analyze each preset
    results = {}
    extrusion_results = {}

    for preset_file in preset_dir.glob("*.yml"):
        try:
            analyzer = PresetAnalyzer(preset_file)
            distribution = analyzer.calculate_percentages()
            results[analyzer.preset_name] = distribution

            # Also extract extrusion data
            extrusion_dist = analyzer.calculate_extrusions()
            extrusion_results[analyzer.preset_name] = extrusion_dist
        except Exception as e:
            print(f"\nError processing {preset_file}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    # Output console summary
    print("\n\n" + "=" * 70)
    print("SUMMARY - Top 20 biomes per preset:")
    print("=" * 70)

    # Get valid biomes for marking unresolved ones
    valid_biomes = BiomeReader.get_all_valid_biomes()

    for preset_name, distribution in results.items():
        print(f"\n{preset_name}:")
        for biome, prob in distribution.get_top_biomes(20):
            marker = " [UNRESOLVED]" if biome not in valid_biomes and biome != 'SELF' else ""
            print(f"  {biome:<40} {prob:>8.4%}{marker}")

    # Output extrusion summary
    print("\n\n" + "=" * 70)
    print("EXTRUSION BIOMES (underground/caves):")
    print("=" * 70)
    print("These biomes generate below the surface via extrusion definitions.")
    print("Percentages represent the fraction of underground space they occupy.")
    print()

    for preset_name in sorted(extrusion_results.keys()):
        extrusion_dist = extrusion_results[preset_name]
        surface_dist = results.get(preset_name)

        if not extrusion_dist.extrusion_biomes:
            continue

        print(f"\n{preset_name}:")
        for biome_id in sorted(extrusion_dist.extrusion_biomes.keys()):
            pct = extrusion_dist.calculate_percentage(biome_id, surface_dist)
            sources = extrusion_dist.get_source_info(biome_id)
            print(f"  {biome_id:<40} {pct:>8.4%}  (from: {sources})")

    # Generate CSV output with extrusion data and climate info
    generate_csv_output(results, extrusion_results, output_file, default_preset)

    # Final summary of unresolved biomes
    print("\n" + "=" * 70)
    print("UNRESOLVED INTERMEDIATE BIOMES:")
    print("=" * 70)
    print("These biomes appear in the distribution but are not final biomes.")
    print("They should be fully resolved through REPLACE stages or removed.")
    print()

    # Only check the core climate preset for unresolved biomes
    climate_distribution = results.get(CLIMATE_PRESET_NAME)
    if climate_distribution is None:
        print(f"  Skipped — climate preset '{CLIMATE_PRESET_NAME}' not found in results.")
        unresolved_found = False
    else:
        distribution_biomes = set(climate_distribution.probabilities.keys())

        unresolved_found = False
        for biome_id in sorted(distribution_biomes):
            # Check if biome is not valid and not the special 'SELF' keyword
            if biome_id not in valid_biomes and biome_id != 'SELF':
                prob = climate_distribution.get(biome_id)
                # Skip intermediates that are never triggered (0% probability)
                if prob <= 0:
                    continue
                unresolved_found = True
                print(f"  {biome_id} ({prob:.4%})")

    if not unresolved_found:
        print("  None - all biomes properly resolved!")

    # Output schema validation report
    validator = get_validator()
    print(validator.get_report())

    # Return exit code based on validation errors
    if validator.has_errors():
        print("\nValidation completed with errors. Please fix the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
