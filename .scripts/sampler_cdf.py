#!/usr/bin/env python3
"""
sampler_cdf.py
==============

Shared probability-distribution machinery for Terra sampler chains.

This module owns:
  - ``NumericalCDF``   : discretized CDF supporting shift / scale / clamp /
                         convolution (add) / product (mul) / max / min, plus
                         conditional_mean for slot E[V|slot] queries.
  - ``SamplerDistribution`` : loads the leaf-noise empirical CDFs from
                              ``sampler_distributions.yml``.
  - ``PackSamplerRegistry`` : loads resolved pack samplers from
                              ``.artifacts/resolved_samplers.yml`` and caches
                              their resolved CDFs.
  - ``resolve_sampler_cdf`` : recursive resolver — walks a sampler config dict
                              into a NumericalCDF.
  - Expression-text parsing for ``type: EXPRESSION`` bodies — handles single
    function calls, affine wrappers, binary if-with-numeric-outputs, simple
    arithmetic (shift / scale / max / min / compound conditions), and inline
    ``variables:`` resolution.
  - ``compute_slot_probabilities`` : public entrypoint that resolves a sampler
    config and produces the per-slot probabilities for a weighted list.

Imported by both ``calculate_biome_percentages.py`` (for biome-pipeline slot
math) and (optionally) ``resolve_samplers.py`` (for pre-computing CDFs at
resolve time).

Pure logic — no biome-pipeline knowledge here.  Keep it that way.
"""
from __future__ import annotations

import math as _math
import re
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# Paths
# =============================================================================
SAMPLER_DIST_CONFIG = Path(__file__).parent / "sampler_distributions.yml"
RESOLVED_SAMPLERS_PATH = Path(".artifacts") / "resolved_samplers.yml"

# =============================================================================
# Diagnostics — flip on via --explain-expressions in calculate_biome_percentages
# =============================================================================
EXPLAIN_EXPRESSIONS: bool = False


def _explain(label: str, expr: str, cdf: Optional["NumericalCDF"] = None) -> None:
    """Emit a one-line diagnostic when EXPLAIN_EXPRESSIONS is set."""
    if not EXPLAIN_EXPRESSIONS:
        return
    expr_one_line = ' '.join(expr.split())
    if len(expr_one_line) > 120:
        expr_one_line = expr_one_line[:117] + '...'
    summary = ''
    if cdf is not None:
        pdf = cdf._get_pdf()
        total = sum(pdf) or 1.0
        mean = sum(pdf[i] * cdf._val(i) for i in range(cdf.BINS)) / total
        p_in_range = cdf.eval_cdf(1.0) - cdf.eval_cdf(-1.0)
        summary = f'  mean={mean:+.3f}  P[-1,1]={p_in_range:.3f}'
    print(f'[EXPR/{label}] {expr_one_line}{summary}', file=sys.stderr)


# =============================================================================
# SamplerDistribution — leaf-noise empirical CDFs
# =============================================================================

class SamplerDistribution:
    """
    Loads piecewise-linear CDFs from sampler_distributions.yml.  Provides
    legacy slot_probabilities for callers that don't need the full
    NumericalCDF machinery.

    Terra maps a sampler output value v to a slot index:
        index = clamp(int(((v + 1) / 2) * arraySize), 0, arraySize - 1)
    """

    _UNIFORM_TAG  = "uniform"
    _CONSTANT_TAG = "constant"

    def __init__(self):
        self._distributions: Dict[str, Any] = {}

    @classmethod
    def load(cls, path: Path) -> "SamplerDistribution":
        instance = cls()
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            dist_map = data.get("distributions", {}) if data else {}
            for k, v in dist_map.items():
                instance._distributions[k] = v
        except Exception as e:
            print(f"Warning: Could not load sampler distributions from {path}: {e}",
                  file=sys.stderr)
        return instance

    def cdf(self, sampler_type: str, v: float) -> float:
        dist = self._distributions.get(sampler_type)
        if dist is None or dist == self._UNIFORM_TAG:
            return max(0.0, min(1.0, (v + 1.0) / 2.0))
        if dist == self._CONSTANT_TAG:
            return 0.0 if v < 0.0 else 1.0
        if not isinstance(dist, list) or len(dist) < 2:
            return max(0.0, min(1.0, (v + 1.0) / 2.0))

        v0, c0 = dist[0]
        vn, cn = dist[-1]
        if v <= v0:
            return float(c0)
        if v >= vn:
            return float(cn)

        lo, hi = 0, len(dist) - 2
        while lo < hi:
            mid = (lo + hi) // 2
            if dist[mid + 1][0] <= v:
                lo = mid + 1
            else:
                hi = mid
        va, ca = dist[lo]
        vb, cb = dist[lo + 1]
        if vb == va:
            return float(ca)
        t = (v - va) / (vb - va)
        return float(ca + t * (cb - ca))

    def slot_probabilities(self, sampler_type: str, weights: List[int]) -> List[float]:
        array_size = sum(weights)
        if array_size == 0:
            n = max(1, len(weights))
            return [1.0 / n] * len(weights)

        dist = self._distributions.get(sampler_type)
        is_uniform  = (dist is None or dist == self._UNIFORM_TAG)
        is_constant = (dist == self._CONSTANT_TAG)

        if is_constant:
            mid_slot = array_size // 2
            probs = [0.0] * len(weights)
            cumulative = 0
            for i, w in enumerate(weights):
                if cumulative <= mid_slot < cumulative + w:
                    probs[i] = 1.0
                    break
                cumulative += w
            return probs

        cumulative = 0
        probs = []
        for w in weights:
            v_start = -1.0 + 2.0 * cumulative / array_size
            v_end   = -1.0 + 2.0 * (cumulative + w) / array_size
            if is_uniform:
                p = w / array_size
            else:
                p = self.cdf(sampler_type, v_end) - self.cdf(sampler_type, v_start)
            probs.append(max(0.0, p))
            cumulative += w

        total = sum(probs)
        if total > 0:
            probs = [p / total for p in probs]
        else:
            probs = [1.0 / len(weights)] * len(weights)
        return probs


_sampler_dist_instance: Optional[SamplerDistribution] = None

def get_sampler_dist() -> SamplerDistribution:
    """Lazy singleton — loads sampler_distributions.yml on first use."""
    global _sampler_dist_instance
    if _sampler_dist_instance is None:
        _sampler_dist_instance = SamplerDistribution.load(SAMPLER_DIST_CONFIG)
    return _sampler_dist_instance


# =============================================================================
# NumericalCDF — discretized probability distribution
# =============================================================================

class NumericalCDF:
    """
    Probability distribution as a discretized CDF over [LO, HI].
    cdf[i] = P(X <= LO + i * step)  where step = (HI - LO) / BINS.

    Supports shift, scale, clamp, linear_map, convolution (add), product (mul),
    max, min, conditional_mean, slot_probabilities.
    """

    BINS = 500       # 500 bins → 0.02 resolution over [-5, 5]
    LO   = -5.0
    HI   =  5.0

    __slots__ = ('cdf',)

    def __init__(self, cdf_values: List[float]):
        self.cdf = cdf_values

    @classmethod
    def _step(cls) -> float:
        return (cls.HI - cls.LO) / cls.BINS

    def _val(self, i: int) -> float:
        return self.LO + i * self._step()

    def _frac_index(self, v: float) -> float:
        return (v - self.LO) / self._step()

    # ── evaluate ──

    def eval_cdf(self, v: float) -> float:
        if v <= self.LO:
            return 0.0
        if v >= self.HI:
            return 1.0
        fi = self._frac_index(v)
        i = int(fi)
        t = fi - i
        if i >= self.BINS:
            return 1.0
        return self.cdf[i] * (1.0 - t) + self.cdf[i + 1] * t

    def quantile(self, p: float) -> float:
        """Smallest v with cdf(v) >= p (inverse CDF).  p clamped to [0,1]."""
        p = max(0.0, min(1.0, p))
        if p <= 0.0:
            return self.LO
        if p >= 1.0:
            return self.HI
        for i in range(self.BINS):
            if self.cdf[i + 1] >= p:
                c0, c1 = self.cdf[i], self.cdf[i + 1]
                if c1 <= c0:
                    return self._val(i)
                t = (p - c0) / (c1 - c0)
                return self._val(i) + t * self._step()
        return self.HI

    def condition_range(self, lo: float, hi: float) -> "NumericalCDF":
        """
        Distribution of X conditioned on lo <= X < hi:
            F'(v) = (F(v) - F(lo)) / (F(hi) - F(lo))  on [lo, hi].
        Used to restrict a continental field to its land (or ocean) portion so a
        gate that only runs ``from: land`` sees the correct conditional coverage.
        """
        f_lo = self.eval_cdf(lo)
        f_hi = self.eval_cdf(hi)
        denom = f_hi - f_lo
        step = self._step()
        new_cdf: List[float] = []
        for i in range(self.BINS + 1):
            v = self.LO + i * step
            if v <= lo:
                new_cdf.append(0.0)
            elif v >= hi:
                new_cdf.append(1.0)
            elif denom > 0:
                new_cdf.append(max(0.0, min(1.0, (self.eval_cdf(v) - f_lo) / denom)))
            else:
                new_cdf.append(0.0 if v < hi else 1.0)
        return NumericalCDF(new_cdf)

    def conditional_mean(self, v_lo: float, v_hi: float) -> float:
        """E[V | v_lo <= V < v_hi]."""
        if v_hi <= v_lo:
            return v_lo
        step = self._step()
        total_mass = 0.0
        weighted_sum = 0.0
        for i in range(self.BINS):
            bin_lo = self._val(i)
            bin_hi = self._val(i + 1)
            if bin_hi <= v_lo or bin_lo >= v_hi:
                continue
            overlap_lo = max(v_lo, bin_lo)
            overlap_hi = min(v_hi, bin_hi)
            frac       = (overlap_hi - overlap_lo) / step
            bin_mass   = max(0.0, self.cdf[i + 1] - self.cdf[i]) * frac
            bin_v      = (overlap_lo + overlap_hi) / 2.0
            total_mass   += bin_mass
            weighted_sum += bin_v * bin_mass
        if total_mass > 0:
            return weighted_sum / total_mass
        return (v_lo + v_hi) / 2.0

    def slot_probabilities(self, weights: List[int]) -> List[float]:
        """Probability each weighted-list slot receives (Terra normalizeIndex)."""
        array_size = sum(weights)
        if array_size == 0:
            n = max(1, len(weights))
            return [1.0 / n] * len(weights)

        cumulative = 0
        probs: List[float] = []
        for w in weights:
            v_start = -1.0 + 2.0 * cumulative / array_size
            v_end   = -1.0 + 2.0 * (cumulative + w) / array_size
            p = self.eval_cdf(v_end) - self.eval_cdf(v_start)
            probs.append(max(0.0, p))
            cumulative += w

        probs[0]  += self.eval_cdf(-1.0)
        probs[-1] += 1.0 - self.eval_cdf(1.0)

        total = sum(probs)
        if total > 0:
            probs = [p / total for p in probs]
        else:
            probs = [1.0 / len(weights)] * len(weights)
        return probs

    # ── constructors ──

    @classmethod
    def from_breakpoints(cls, breakpoints: List) -> "NumericalCDF":
        step = cls._step()
        cdf: List[float] = []
        bp = breakpoints
        j = 0
        for i in range(cls.BINS + 1):
            v = cls.LO + i * step
            if v <= bp[0][0]:
                cdf.append(float(bp[0][1]))
            elif v >= bp[-1][0]:
                cdf.append(float(bp[-1][1]))
            else:
                while j < len(bp) - 2 and bp[j + 1][0] < v:
                    j += 1
                va, ca = bp[j]
                vb, cb = bp[j + 1]
                t = (v - va) / (vb - va) if vb != va else 0.0
                cdf.append(float(ca + t * (cb - ca)))
        return cls(cdf)

    @classmethod
    def uniform(cls, lo: float = -1.0, hi: float = 1.0) -> "NumericalCDF":
        step = cls._step()
        cdf = []
        for i in range(cls.BINS + 1):
            v = cls.LO + i * step
            if v <= lo:
                cdf.append(0.0)
            elif v >= hi:
                cdf.append(1.0)
            else:
                cdf.append((v - lo) / (hi - lo))
        return cls(cdf)

    @classmethod
    def constant(cls, c: float = 0.0) -> "NumericalCDF":
        step = cls._step()
        cdf = [0.0 if (cls.LO + i * step) < c else 1.0
               for i in range(cls.BINS + 1)]
        return cls(cdf)

    @classmethod
    def gaussian(cls, mean: float = 0.0, std: float = 1.0) -> "NumericalCDF":
        step = cls._step()
        sqrt2 = _math.sqrt(2.0)
        cdf = [0.5 * (1.0 + _math.erf((cls.LO + i * step - mean) / (std * sqrt2)))
               for i in range(cls.BINS + 1)]
        return cls(cdf)

    @classmethod
    def binary(cls, val_lo: float, val_hi: float, p_lo: float) -> "NumericalCDF":
        """Two-point distribution: mass p_lo at val_lo, mass (1−p_lo) at val_hi."""
        p_lo = max(0.0, min(1.0, p_lo))
        step = cls._step()
        cdf_values: List[float] = []
        for i in range(cls.BINS + 1):
            v = cls.LO + i * step
            if v < val_lo:
                cdf_values.append(0.0)
            elif v < val_hi:
                cdf_values.append(p_lo)
            else:
                cdf_values.append(1.0)
        return cls(cdf_values)

    @classmethod
    def from_point_masses(cls, points: List[Tuple[float, float]]) -> "NumericalCDF":
        """
        Discrete distribution from ``(value, probability)`` point masses.

        Builds a right-continuous step CDF where ``cdf(v) = Σ p_i for value_i <= v``.
        Probabilities are normalised to sum to 1.  Used to encode the real output
        distribution of a spatial gate sampler (e.g. ``riverSampler`` returns its
        river-trigger value on only a small fraction of cells) that the generic
        resolver would otherwise treat as uniform.  Place values strictly inside
        their target slot ranges (avoid exact slot boundaries) so the slot integral
        attributes each mass unambiguously.
        """
        total = sum(max(0.0, p) for _, p in points)
        if total <= 0:
            return cls.uniform()
        pts = sorted((v, max(0.0, p) / total) for v, p in points)
        step = cls._step()
        cdf: List[float] = []
        for i in range(cls.BINS + 1):
            v = cls.LO + i * step
            cdf.append(sum(p for val, p in pts if val <= v))
        return cls(cdf)

    @classmethod
    def mixture(cls, cdfs: List["NumericalCDF"],
                weights: List[float]) -> "NumericalCDF":
        """
        Mixture distribution: F(v) = Σ wᵢ · Fᵢ(v) with weights normalised to 1.
        Used to model conditional outputs like ``if(cond, branch_then, branch_else)``
        where each branch may itself be a non-trivial CDF.
        """
        if not cdfs:
            return cls.uniform()
        total = sum(max(0.0, w) for w in weights)
        if total <= 0:
            return cls.uniform()
        norm = [max(0.0, w) / total for w in weights]
        new_cdf: List[float] = []
        for i in range(cls.BINS + 1):
            new_cdf.append(sum(w * c.cdf[i] for c, w in zip(cdfs, norm)))
        return cls(new_cdf)

    # ── transformations ──

    def shift(self, c: float) -> "NumericalCDF":
        if c == 0:
            return self
        new_cdf = [self.eval_cdf(self._val(i) - c) for i in range(self.BINS + 1)]
        return NumericalCDF(new_cdf)

    def scale(self, c: float) -> "NumericalCDF":
        if c == 1.0:
            return self
        if c == 0.0:
            return NumericalCDF.constant(0.0)
        if c > 0:
            new_cdf = [self.eval_cdf(self._val(i) / c) for i in range(self.BINS + 1)]
        else:
            new_cdf = [max(0.0, 1.0 - self.eval_cdf(self._val(i) / c))
                       for i in range(self.BINS + 1)]
        return NumericalCDF(new_cdf)

    def clamp_dist(self, lo: float, hi: float) -> "NumericalCDF":
        step = self._step()
        new_cdf: List[float] = []
        for i in range(self.BINS + 1):
            v = self.LO + i * step
            if v < lo:
                new_cdf.append(0.0)
            elif v >= hi:
                new_cdf.append(1.0)
            else:
                new_cdf.append(self.eval_cdf(v))
        return NumericalCDF(new_cdf)

    def linear_map(self, in_lo: float, in_hi: float,
                   out_lo: float, out_hi: float) -> "NumericalCDF":
        clamped = self.clamp_dist(in_lo, in_hi)
        if in_hi == in_lo:
            return NumericalCDF.constant(out_lo)
        s = (out_hi - out_lo) / (in_hi - in_lo)
        d = out_lo - s * in_lo
        return clamped.scale(s).shift(d)

    def abs_dist(self) -> "NumericalCDF":
        """Distribution of |X|: fold negative half onto positive."""
        new_cdf: List[float] = []
        for i in range(self.BINS + 1):
            v = self._val(i)
            if v < 0:
                new_cdf.append(0.0)
            else:
                new_cdf.append(max(0.0, self.eval_cdf(v) - self.eval_cdf(-v)))
        return NumericalCDF(new_cdf)

    # ── binary ops (independence assumption) ──

    def _get_pdf(self) -> List[float]:
        return [max(0.0, self.cdf[i + 1] - self.cdf[i]) for i in range(self.BINS)]

    @classmethod
    def _from_pdf(cls, pdf: List[float]) -> "NumericalCDF":
        cdf = [0.0]
        for p in pdf:
            cdf.append(cdf[-1] + max(0.0, p))
        total = cdf[-1]
        if total > 0:
            cdf = [c / total for c in cdf]
        else:
            return cls.uniform()
        return cls(cdf)

    def add(self, other: "NumericalCDF") -> "NumericalCDF":
        """Distribution of X + Y (convolution)."""
        pa = self._get_pdf()
        pb = other._get_pdf()
        n = self.BINS
        conv = [0.0] * (2 * n - 1)
        for i in range(n):
            if pa[i] == 0:
                continue
            for j in range(n):
                conv[i + j] += pa[i] * pb[j]
        conv_lo = 2.0 * self.LO
        conv_range = 2.0 * (self.HI - self.LO)
        conv_step = conv_range / len(conv)
        cum = [0.0]
        for c in conv:
            cum.append(cum[-1] + max(0.0, c))
        total = cum[-1]
        if total <= 0:
            return NumericalCDF.uniform()
        cum = [c / total for c in cum]
        step = self._step()
        new_cdf: List[float] = []
        for i in range(n + 1):
            v = self.LO + i * step
            fi = (v - conv_lo) / conv_step
            idx = int(fi)
            if idx < 0:
                new_cdf.append(0.0)
            elif idx >= len(cum) - 1:
                new_cdf.append(1.0)
            else:
                t = fi - idx
                new_cdf.append(cum[idx] * (1.0 - t) + cum[idx + 1] * t)
        return NumericalCDF(new_cdf)

    def subtract(self, other: "NumericalCDF") -> "NumericalCDF":
        """Distribution of X - Y."""
        return self.add(other.scale(-1.0))

    def max_with(self, other: "NumericalCDF") -> "NumericalCDF":
        new_cdf = [self.cdf[i] * other.cdf[i] for i in range(self.BINS + 1)]
        return NumericalCDF(new_cdf)

    def min_with(self, other: "NumericalCDF") -> "NumericalCDF":
        new_cdf = [1.0 - (1.0 - self.cdf[i]) * (1.0 - other.cdf[i])
                   for i in range(self.BINS + 1)]
        return NumericalCDF(new_cdf)

    def __repr__(self):
        mean = sum((self.cdf[i+1] - self.cdf[i]) * self._val(i)
                   for i in range(self.BINS))
        return f"NumericalCDF(mean≈{mean:.3f}, P[-1,1]≈{self.eval_cdf(1)-self.eval_cdf(-1):.3f})"


# =============================================================================
# PackSamplerRegistry — loads resolved pack samplers
# =============================================================================

# =============================================================================
# Named-sampler coverage overrides
# =============================================================================
# Some pack samplers gate a biome on a spatial field whose true output
# distribution the generic resolver cannot derive: DENDRY river networks,
# cellular rift/spot zone fields, coast/island distance fields.  Left to the
# uniform fallback, the resolver assigns ~weight/total of each gated biome's
# source to the special biome — vastly over-counting coverage (e.g. rivers
# predicted 29% vs 4.6% measured, MESA_MONUMENTS 4.7% vs 0.8%).
#
# Each entry maps a sampler NAME to a list of ``(value, probability)`` point
# masses approximating that sampler's real output distribution.  When a stage
# sampler resolves to one of these names, the point-mass CDF is used instead of
# the derived/uniform one, so the slot integral reflects true coverage.
#
# These are PACK-SPECIFIC and calibrated against benchmark_CHIMERA.csv.  The map
# is populated by calculate_biome_percentages.py at import; keep it empty here so
# sampler_cdf stays pack-agnostic.
NAMED_SAMPLER_POINT_MASSES: Dict[str, List[Tuple[float, float]]] = {}


def register_sampler_point_masses(name: str, points: List[Tuple[float, float]]) -> None:
    """Register a coverage override for a named pack sampler (see NAMED_SAMPLER_POINT_MASSES)."""
    NAMED_SAMPLER_POINT_MASSES[name] = points


# =============================================================================
# Region-conditional leaf overrides (spatial-correlation modelling)
# =============================================================================
# A pipeline gate such as ``if(mesaMask(x,z)>1/8, …)`` or the coast band runs
# only on the LAND (or OCEAN) region, yet its gating field is the continental
# family that *defines* that region — so the marginal distribution over the whole
# map massively over-counts coverage (mesa 44%, island 8%).  To model the
# correlation, while resolving a gate we temporarily replace the continental
# leaf samplers by their region-conditional CDFs (continents restricted to its
# land/ocean portion).  ``_LEAF_OVERRIDES`` maps sampler-name → CDF; when set,
# ``_lookup_sampler_cdf`` returns the override and ``PackSamplerRegistry.get_cdf``
# bypasses its cache so the override propagates through the dependency tree.
_LEAF_OVERRIDES: Dict[str, "NumericalCDF"] = {}


class leaf_overrides:
    """Context manager: temporarily resolve the given leaf sampler names to the
    supplied CDFs (e.g. region-conditional continental fields)."""

    def __init__(self, overrides: Dict[str, "NumericalCDF"]):
        self._overrides = overrides or {}
        self._saved: Dict[str, "NumericalCDF"] = {}

    def __enter__(self):
        global _LEAF_OVERRIDES
        self._saved = _LEAF_OVERRIDES
        _LEAF_OVERRIDES = self._overrides
        return self

    def __exit__(self, *exc):
        global _LEAF_OVERRIDES
        _LEAF_OVERRIDES = self._saved
        return False


class PackSamplerRegistry:
    """Loads .artifacts/resolved_samplers.yml and resolves CDFs by name."""

    def __init__(self):
        self._configs: Dict[str, Any] = {}
        self._cdf_cache: Dict[str, NumericalCDF] = {}

    @classmethod
    def load(cls, path: Path = RESOLVED_SAMPLERS_PATH) -> "PackSamplerRegistry":
        reg = cls()
        if not path.exists():
            print(f"Warning: {path} not found — pack sampler CDF resolution unavailable",
                  file=sys.stderr)
            return reg
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            samplers = data.get("samplers", {}) if data else {}
            for name, cfg in samplers.items():
                if isinstance(cfg, dict):
                    reg._configs[name] = cfg
            print(f"Loaded {len(reg._configs)} pack samplers from {path}", file=sys.stderr)
        except yaml.YAMLError:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                cleaned = re.sub(r'^.*\*[A-Z][a-zA-Z]+.*$', '', content, flags=re.MULTILINE)
                data = yaml.safe_load(cleaned)
                samplers = data.get("samplers", {}) if data else {}
                for name, cfg in samplers.items():
                    if isinstance(cfg, dict):
                        reg._configs[name] = cfg
                print(f"Loaded {len(reg._configs)} pack samplers from {path} (with alias cleanup)",
                      file=sys.stderr)
            except Exception as e2:
                print(f"Warning: Could not load pack samplers from {path}: {e2}",
                      file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not load pack samplers from {path}: {e}", file=sys.stderr)
        return reg

    def get_config(self, name: str) -> Optional[Dict]:
        return self._configs.get(name)

    def get_cdf(self, name: str) -> Optional[NumericalCDF]:
        # When region-conditional leaf overrides are active we must NOT use or
        # populate the global cache — the same sampler resolves differently per
        # region, and dependents must re-resolve so the override propagates.
        conditioning = bool(_LEAF_OVERRIDES)
        if name in _LEAF_OVERRIDES:
            return _LEAF_OVERRIDES[name]
        if not conditioning and name in self._cdf_cache:
            return self._cdf_cache[name]
        # Coverage override takes precedence over derived resolution.
        override = NAMED_SAMPLER_POINT_MASSES.get(name)
        if override is not None:
            cdf = NumericalCDF.from_point_masses(override)
            if not conditioning:
                self._cdf_cache[name] = cdf
            return cdf
        cfg = self._configs.get(name)
        if cfg is None:
            return None
        cdf = resolve_sampler_cdf(cfg, get_sampler_dist(), self)
        if not conditioning:
            self._cdf_cache[name] = cdf
        return cdf


_pack_registry_instance: Optional[PackSamplerRegistry] = None

def get_pack_registry() -> PackSamplerRegistry:
    """Lazy singleton — loads resolved_samplers.yml on first use."""
    global _pack_registry_instance
    if _pack_registry_instance is None:
        _pack_registry_instance = PackSamplerRegistry.load()
    return _pack_registry_instance


def reset_pack_registry() -> None:
    """Force re-load on next get_pack_registry() call (for testing)."""
    global _pack_registry_instance
    _pack_registry_instance = None


# =============================================================================
# Expression-text parsers (variables, arithmetic, conditional, compound)
# =============================================================================

_NUM_RE = r'[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?'


def _eval_constant_expr(expr: str, variables: Optional[Dict[str, Any]] = None) -> Optional[float]:
    """
    Try to evaluate an expression string as a pure numeric constant, substituting
    variables.  Used for thresholds like ``(island_threshold+land_threshold)/2``.
    Returns None if the expression contains anything beyond +, -, *, /, parens,
    numbers, and named variable references.
    """
    s = expr.strip()
    if not s:
        return None
    # Substitute variables first
    if variables:
        for name, val in variables.items():
            if isinstance(val, (int, float)):
                s = re.sub(r'(?<![a-zA-Z0-9_])' + re.escape(name) + r'(?![a-zA-Z0-9_])',
                           f'({val})', s)
    # Reject anything that isn't a constant arithmetic expression
    if not re.match(r'^[\s+\-*/().0-9eE]+$', s):
        return None
    try:
        result = eval(s, {"__builtins__": {}}, {})
        if isinstance(result, (int, float)):
            return float(result)
    except Exception:
        pass
    return None


def _parse_affine_expression(expr: str) -> Optional[Tuple[float, float]]:
    """
    Parse an EXPRESSION_NORMALIZER expression as affine in 'in'.
    Returns (scale, shift) or None.
    """
    s = expr.strip()
    if any(op in s for op in ['^', '**', 'if(', 'if (', 'max(', 'min(', 'herp(', 'lerp(']):
        return None
    if 'in' not in s:
        return None
    try:
        s_clean = s.replace('\n', ' ').strip()
        val_at_0    = eval(s_clean.replace('in', '(0.0)'), {"__builtins__": {}}, {})
        val_at_1    = eval(s_clean.replace('in', '(1.0)'), {"__builtins__": {}}, {})
        val_at_half = eval(s_clean.replace('in', '(0.5)'), {"__builtins__": {}}, {})
        expected_half = (val_at_0 + val_at_1) / 2.0
        if abs(val_at_half - expected_half) < 1e-6:
            return (val_at_1 - val_at_0, val_at_0)
    except Exception:
        pass
    return None


def _lookup_sampler_cdf(name: str,
                       local_samplers: Dict,
                       sd: SamplerDistribution,
                       pack_reg: Optional[PackSamplerRegistry],
                       _depth: int) -> Optional[NumericalCDF]:
    """Look up a sampler by name in local samplers or pack registry."""
    # Region-conditional override wins over any local/pack definition.
    if name in _LEAF_OVERRIDES:
        return _LEAF_OVERRIDES[name]
    if isinstance(local_samplers, dict) and name in local_samplers:
        cfg = local_samplers[name]
        if isinstance(cfg, dict):
            return resolve_sampler_cdf(cfg, sd, pack_reg, _depth + 1)
    if pack_reg is not None:
        return pack_reg.get_cdf(name)
    return None


def _try_pattern_arithmetic(expr: str,
                            local_samplers: Dict,
                            variables: Dict[str, Any],
                            sd: SamplerDistribution,
                            pack_reg: Optional[PackSamplerRegistry],
                            _depth: int) -> Optional[NumericalCDF]:
    """
    Try to resolve simple-arithmetic expression patterns.  Returns None if no
    pattern matches.  Patterns tried (in order):

        funcCall                      → lookup
        funcCall * k       (+/- c)    → scale (+ shift)
        funcCall + c      / funcCall - c  → shift
        funcCall / c                  → scale by 1/c
        (funcCall - a) / b            → linear (shift then scale)
        max(funcA, funcB)             → max_with
        min(funcA, funcB)             → min_with

    'funcCall' here means ``name(x[, ...], z[, ...])``; both arguments must
    reference x and z.  ``c``/``k``/``a``/``b`` may be numeric literals or
    constant-arithmetic over the sampler's ``variables:``.
    """
    s = ' '.join(expr.split())   # collapse whitespace

    # ── 0. Bare function call: funcName(x,z) ──
    m = re.match(rf'^([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*$', s)
    if m:
        return _lookup_sampler_cdf(m.group(1), local_samplers, sd, pack_reg, _depth)

    # ── 1. (funcCall - a) / b OR (funcCall + a) / b ──
    m = re.match(
        rf'^\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*([+-])\s*(.+?)\s*\)'
        rf'\s*/\s*(.+?)\s*$',
        s
    )
    if m:
        func_name = m.group(1)
        sign      = 1.0 if m.group(2) == '+' else -1.0
        a_const   = _eval_constant_expr(m.group(3), variables)
        b_const   = _eval_constant_expr(m.group(4), variables)
        if a_const is not None and b_const is not None and b_const != 0:
            inner = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
            if inner is not None:
                return inner.shift(sign * a_const).scale(1.0 / b_const)

    # ── 2. funcCall + c, funcCall - c ──
    m = re.match(
        rf'^([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*([+-])\s*(.+?)\s*$',
        s
    )
    if m:
        func_name = m.group(1)
        sign      = 1.0 if m.group(2) == '+' else -1.0
        c         = _eval_constant_expr(m.group(3), variables)
        if c is not None:
            inner = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
            if inner is not None:
                return inner.shift(sign * c)

    # ── 3. funcCall * k or funcCall / k (optionally  +/- c) ──
    m = re.match(
        rf'^([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*([*/])\s*({_NUM_RE})'
        rf'(?:\s*([+-])\s*({_NUM_RE}))?\s*$',
        s
    )
    if m:
        func_name = m.group(1)
        op        = m.group(2)
        k         = float(m.group(3))
        try:
            scale_v = k if op == '*' else (1.0 / k if k != 0 else 0.0)
            inner = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
            if inner is not None:
                out = inner.scale(scale_v)
                if m.group(4) and m.group(5):
                    sign  = 1.0 if m.group(4) == '+' else -1.0
                    shift = sign * float(m.group(5))
                    out = out.shift(shift)
                return out
        except ValueError:
            pass

    # ── 4. max(funcA(x,z), funcB(x,z)) ──
    m = re.match(
        rf'^max\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*,\s*'
        rf'([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*\)\s*$',
        s
    )
    if m:
        a = _lookup_sampler_cdf(m.group(1), local_samplers, sd, pack_reg, _depth)
        b = _lookup_sampler_cdf(m.group(2), local_samplers, sd, pack_reg, _depth)
        if a is not None and b is not None:
            return a.max_with(b)

    # ── 5. min(funcA(x,z), funcB(x,z)) ──
    m = re.match(
        rf'^min\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*,\s*'
        rf'([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*\)\s*$',
        s
    )
    if m:
        a = _lookup_sampler_cdf(m.group(1), local_samplers, sd, pack_reg, _depth)
        b = _lookup_sampler_cdf(m.group(2), local_samplers, sd, pack_reg, _depth)
        if a is not None and b is not None:
            return a.min_with(b)

    # ── 6. abs(funcCall(x,z)) ──
    m = re.match(
        rf'^abs\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*\)\s*$',
        s
    )
    if m:
        inner = _lookup_sampler_cdf(m.group(1), local_samplers, sd, pack_reg, _depth)
        if inner is not None:
            return inner.abs_dist()

    # ── 7. min(funcCall(x,z), k)  or  min(k, funcCall(x,z)) ──
    for cap_pat in (
        rf'^min\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*,\s*(.+?)\s*\)\s*$',
        rf'^min\(\s*(.+?)\s*,\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*\)\s*$',
    ):
        m = re.match(cap_pat, s)
        if m:
            func_first = cap_pat.startswith(r'^min\(\s*([a-zA-Z_]')
            func_name = m.group(1 if func_first else 2)
            k_raw     = m.group(2 if func_first else 1)
            k = _eval_constant_expr(k_raw, variables)
            if k is None:
                try: k = float(k_raw)
                except ValueError: k = None
            if k is not None:
                inner = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
                if inner is not None:
                    return inner.clamp_dist(NumericalCDF.LO, k)
            break

    # ── 8. max(funcCall(x,z), k)  or  max(k, funcCall(x,z)) ──
    for cap_pat in (
        rf'^max\(\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*,\s*(.+?)\s*\)\s*$',
        rf'^max\(\s*(.+?)\s*,\s*([a-zA-Z_]\w*)\s*\(\s*x[^,)]*,\s*z[^,)]*\)\s*\)\s*$',
    ):
        m = re.match(cap_pat, s)
        if m:
            func_first = cap_pat.startswith(r'^max\(\s*([a-zA-Z_]')
            func_name = m.group(1 if func_first else 2)
            k_raw     = m.group(2 if func_first else 1)
            k = _eval_constant_expr(k_raw, variables)
            if k is None:
                try: k = float(k_raw)
                except ValueError: k = None
            if k is not None:
                inner = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
                if inner is not None:
                    return inner.clamp_dist(k, NumericalCDF.HI)
            break

    return None


# =============================================================================
# Generic if-expression / clause / branch resolution
# =============================================================================

def _split_top_level(expr: str, sep: str) -> List[str]:
    """
    Split ``expr`` on ``sep`` at top level (depth-0 parens only).  ``sep`` may
    be multi-character (e.g. ``'&&'``).  Returns a list of stripped parts.
    """
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    i, n, sep_len = 0, len(expr), len(sep)
    while i < n:
        ch = expr[i]
        if ch == '(':
            depth += 1
            current.append(ch)
            i += 1
        elif ch == ')':
            depth -= 1
            current.append(ch)
            i += 1
        elif depth == 0 and expr[i:i + sep_len] == sep:
            parts.append(''.join(current).strip())
            current = []
            i += sep_len
        else:
            current.append(ch)
            i += 1
    parts.append(''.join(current).strip())
    return parts


def _split_if_args(expr: str) -> Optional[Tuple[str, str, str]]:
    """
    Parse ``if(cond, then, else)`` → (cond, then, else), respecting paren depth
    when splitting the comma-separated args.  Returns None if ``expr`` is not an
    exact ``if(...)`` form consuming the whole string.
    """
    s = expr.strip()
    m = re.match(r'^if\s*\(', s)
    if not m:
        return None
    paren_start = m.end() - 1
    depth, end = 0, -1
    for i in range(paren_start, len(s)):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0 or s[end + 1:].strip():
        return None
    parts = _split_top_level(s[paren_start + 1:end], ',')
    if len(parts) != 3:
        return None
    return (parts[0], parts[1], parts[2])


def _try_func_call(s: str) -> Optional[str]:
    """Return func_name if ``s`` is exactly ``name(...)`` (paren-balanced), else None."""
    s_strip = s.strip()
    m = re.match(r'^([a-zA-Z_]\w*)\s*\(', s_strip)
    if not m:
        return None
    paren_start = m.end() - 1
    depth, end = 0, -1
    for i in range(paren_start, len(s_strip)):
        if s_strip[i] == '(':
            depth += 1
        elif s_strip[i] == ')':
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0 or s_strip[end + 1:].strip():
        return None
    return m.group(1)


_COMPARE_OPS = ('>=', '<=', '==', '!=', '>', '<')


def _split_comparison(clause: str) -> Optional[Tuple[str, str, str]]:
    """Split a clause into (lhs, op, rhs) on the first top-level comparison op."""
    depth, i, n = 0, 0, len(clause)
    while i < n:
        ch = clause[i]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0:
            for op in _COMPARE_OPS:
                if clause[i:i + len(op)] == op:
                    lhs = clause[:i].strip()
                    rhs = clause[i + len(op):].strip()
                    if lhs and rhs:
                        return (lhs, op, rhs)
        i += 1
    return None


def _resolve_clause_side(side: str,
                         local_samplers: Dict,
                         variables: Dict[str, Any],
                         sd: SamplerDistribution,
                         pack_reg: Optional[PackSamplerRegistry],
                         _depth: int
                         ) -> Tuple[Optional[NumericalCDF], Optional[float]]:
    """
    Resolve one side of a comparison.  Returns ``(cdf, scalar)`` with exactly
    one non-None entry on success, or ``(None, None)`` if unresolved.
    """
    s = side.strip()
    val = _eval_constant_expr(s, variables)
    if val is not None:
        return None, val
    fname = _try_func_call(s)
    if fname:
        cdf = _lookup_sampler_cdf(fname, local_samplers, sd, pack_reg, _depth)
        if cdf is not None:
            return cdf, None
    return None, None


def _clause_probability(clause: str,
                        local_samplers: Dict,
                        variables: Dict[str, Any],
                        sd: SamplerDistribution,
                        pack_reg: Optional[PackSamplerRegistry],
                        _depth: int) -> Optional[float]:
    """Return P(clause) for a single comparison ``side OP side``."""
    parts = _split_comparison(clause)
    if parts is None:
        return None
    lhs, op, rhs = parts
    lhs_cdf, lhs_val = _resolve_clause_side(
        lhs, local_samplers, variables, sd, pack_reg, _depth)
    rhs_cdf, rhs_val = _resolve_clause_side(
        rhs, local_samplers, variables, sd, pack_reg, _depth)

    # funcCall OP constant
    if lhs_cdf is not None and rhs_val is not None:
        cdf_at = lhs_cdf.eval_cdf(rhs_val)
        if op in ('>', '>='):
            return max(0.0, min(1.0, 1.0 - cdf_at))
        if op in ('<', '<='):
            return max(0.0, min(1.0, cdf_at))
        return 0.5

    # constant OP funcCall  →  flip the comparison
    if lhs_val is not None and rhs_cdf is not None:
        cdf_at = rhs_cdf.eval_cdf(lhs_val)
        if op in ('<', '<='):
            return max(0.0, min(1.0, 1.0 - cdf_at))
        if op in ('>', '>='):
            return max(0.0, min(1.0, cdf_at))
        return 0.5

    # funcA OP funcB (independence assumption via difference CDF)
    if lhs_cdf is not None and rhs_cdf is not None:
        diff = lhs_cdf.subtract(rhs_cdf)
        zero_p = diff.eval_cdf(0.0)
        if op in ('>', '>='):
            return max(0.0, min(1.0, 1.0 - zero_p))
        if op in ('<', '<='):
            return max(0.0, min(1.0, zero_p))
        return 0.5

    return None


def _resolve_branch_cdf(branch: str,
                        local_samplers: Dict,
                        variables: Dict[str, Any],
                        sd: SamplerDistribution,
                        pack_reg: Optional[PackSamplerRegistry],
                        _depth: int) -> Optional[NumericalCDF]:
    """
    Resolve a then-/else-branch of an if-expression to a NumericalCDF.

    Supports: numeric literal / constant expr in ``variables``, bare function
    call ``f(x,z)``, arithmetic over a function call (via
    ``_try_pattern_arithmetic``), or a recursive ``if(...)`` expression.
    """
    s = branch.strip()
    if not s:
        return None

    # Recursive if
    if re.match(r'^if\s*\(', s):
        cdf = _resolve_binary_if_cdf(s, local_samplers, variables, sd, pack_reg, _depth)
        if cdf is not None:
            return cdf

    # Pure constant / variable expression
    val = _eval_constant_expr(s, variables)
    if val is not None:
        return NumericalCDF.constant(val)

    # Bare function call
    fname = _try_func_call(s)
    if fname:
        cdf = _lookup_sampler_cdf(fname, local_samplers, sd, pack_reg, _depth)
        if cdf is not None:
            return cdf

    # Arithmetic patterns over a function call (shift / scale / linear)
    cdf = _try_pattern_arithmetic(s, local_samplers, variables, sd, pack_reg, _depth)
    if cdf is not None:
        return cdf

    return None


def _strip_outer_parens(s: str) -> str:
    """Remove redundant matched outer parentheses wrapping the whole expression."""
    s = s.strip()
    while s.startswith('(') and s.endswith(')'):
        depth = 0
        ok = True
        for i, ch in enumerate(s):
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    ok = False
                    break
        if ok:
            s = s[1:-1].strip()
        else:
            break
    return s


def _split_additive(s: str) -> Optional[List[Tuple[str, str]]]:
    """
    Split a top-level additive expression into [(sign, term), ...] where sign is
    '+' or '-'.  Returns None if there is no top-level +/- (so the caller can try
    multiplicative).  Respects parens and does not split unary signs, exponent
    signs (1e-5), or a leading sign.
    """
    terms: List[Tuple[str, str]] = []
    depth = 0
    last = 0
    sign = '+'
    found = False
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch in '+-' and i > 0:
            prev = s[i - 1]
            if prev in '+-*/(eE,' or s[:i].strip() == '':
                continue  # unary / exponent / operator-adjacent
            terms.append((sign, s[last:i].strip()))
            sign = ch
            last = i + 1
            found = True
    if not found:
        return None
    terms.append((sign, s[last:].strip()))
    return terms


def _split_multiplicative(s: str) -> Optional[List[Tuple[str, str]]]:
    """Split a top-level multiplicative expression into [(op, factor), ...]."""
    factors: List[Tuple[str, str]] = []
    depth = 0
    last = 0
    op = '*'
    found = False
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth == 0 and ch in '*/':
            factors.append((op, s[last:i].strip()))
            op = ch
            last = i + 1
            found = True
    if not found:
        return None
    factors.append((op, s[last:].strip()))
    return factors


def _eval_value_cdf(expr: str,
                    local_samplers: Dict,
                    variables: Dict[str, Any],
                    sd: SamplerDistribution,
                    pack_reg: Optional[PackSamplerRegistry],
                    _depth: int
                    ) -> Optional[Tuple[Optional["NumericalCDF"], Optional[float]]]:
    """
    Recursive-descent evaluator for a scalar sampler expression, returning a
    ``(cdf, scalar)`` pair with exactly one entry set, or ``None`` if it cannot be
    resolved.  Handles constants/variables, bare sampler calls, parenthesised
    sub-expressions, ``+ - * /`` (with scalar/CDF mixing), ``min``/``max``/``abs``,
    and nested ``if(...)`` — so compound gate fields like
    ``max(min((mesaMaskRaw(x,z)-t)/k, continents(x,z)), 0)`` resolve down to their
    leaf samplers (and therefore honour region-conditional leaf overrides).
    """
    if _depth > MAX_DEPTH:
        return None
    s = _strip_outer_parens(expr)
    if not s:
        return None

    # Pure constant / variable arithmetic.
    val = _eval_constant_expr(s, variables)
    if val is not None:
        return (None, val)

    # Additive split (lowest precedence).
    add_terms = _split_additive(s)
    if add_terms is not None:
        acc_cdf: Optional[NumericalCDF] = None
        acc_scalar = 0.0
        for sign, term in add_terms:
            sub = _eval_value_cdf(term, local_samplers, variables, sd, pack_reg, _depth + 1)
            if sub is None:
                return None
            cdf, sc = sub
            if cdf is None:
                acc_scalar += sc if sign == '+' else -sc
            else:
                signed = cdf if sign == '+' else cdf.scale(-1.0)
                acc_cdf = signed if acc_cdf is None else acc_cdf.add(signed)
        if acc_cdf is None:
            return (None, acc_scalar)
        if acc_scalar != 0.0:
            acc_cdf = acc_cdf.shift(acc_scalar)
        return (acc_cdf, None)

    # Multiplicative split.
    mul_factors = _split_multiplicative(s)
    if mul_factors is not None:
        acc_cdf = None
        acc_scalar = 1.0
        for op, factor in mul_factors:
            sub = _eval_value_cdf(factor, local_samplers, variables, sd, pack_reg, _depth + 1)
            if sub is None:
                return None
            cdf, sc = sub
            if cdf is None:
                if op == '*':
                    acc_scalar *= sc
                else:
                    if sc == 0:
                        return None
                    acc_scalar /= sc
            else:
                if op == '/':
                    return None  # dividing by a distribution — unsupported
                if acc_cdf is None:
                    acc_cdf = cdf
                else:
                    return None  # product of two distributions — unsupported here
        if acc_cdf is None:
            return (None, acc_scalar)
        return (acc_cdf.scale(acc_scalar), None)

    # min(a, b) / max(a, b)
    for fname in ('min', 'max'):
        m = re.match(rf'^{fname}\s*\(', s)
        if m and _try_func_call(s) == fname:
            inner = s[s.index('(') + 1:s.rindex(')')]
            args = _split_top_level(inner, ',')
            if len(args) == 2:
                a = _eval_value_cdf(args[0], local_samplers, variables, sd, pack_reg, _depth + 1)
                b = _eval_value_cdf(args[1], local_samplers, variables, sd, pack_reg, _depth + 1)
                if a is None or b is None:
                    return None
                (a_cdf, a_sc), (b_cdf, b_sc) = a, b
                if a_cdf is not None and b_cdf is not None:
                    return (a_cdf.max_with(b_cdf) if fname == 'max'
                            else a_cdf.min_with(b_cdf), None)
                # one side scalar → clamp
                cdf = a_cdf if a_cdf is not None else b_cdf
                k = b_sc if a_cdf is not None else a_sc
                if cdf is not None and k is not None:
                    if fname == 'max':
                        return (cdf.clamp_dist(k, NumericalCDF.HI), None)
                    return (cdf.clamp_dist(NumericalCDF.LO, k), None)
                if a_sc is not None and b_sc is not None:
                    return (None, max(a_sc, b_sc) if fname == 'max' else min(a_sc, b_sc))
            return None

    # abs(a)
    if _try_func_call(s) == 'abs':
        inner = s[s.index('(') + 1:s.rindex(')')]
        sub = _eval_value_cdf(inner, local_samplers, variables, sd, pack_reg, _depth + 1)
        if sub and sub[0] is not None:
            return (sub[0].abs_dist(), None)
        return None

    # Nested if(...)
    if re.match(r'^if\s*\(', s) and _try_func_call(s) == 'if':
        cdf = _resolve_binary_if_cdf(s, local_samplers, variables, sd, pack_reg, _depth)
        if cdf is not None:
            return (cdf, None)
        return None

    # Bare sampler call name(args...).
    fname = _try_func_call(s)
    if fname:
        cdf = _lookup_sampler_cdf(fname, local_samplers, sd, pack_reg, _depth)
        if cdf is not None:
            return (cdf, None)
    return None


def _resolve_binary_if_cdf(expr: str,
                          local_samplers: Dict,
                          variables: Dict[str, Any],
                          sd: SamplerDistribution,
                          pack_reg: Optional[PackSamplerRegistry],
                          _depth: int) -> Optional[NumericalCDF]:
    """
    Resolve an ``if(cond, then, else)`` expression to a NumericalCDF.

    Supports:
      - **cond**: N-clause boolean joined by ``&&`` at top level; each clause
        is a comparison ``side OP side`` where each side is a function call or
        a constant/variable expression.
      - **then / else**: numeric literal, function call, simple arithmetic
        over a function call, or a recursive ``if(...)``.

    P(cond) is computed under independence (product of clause probabilities).
    The output is a mixture CDF over the resolved then/else branches.

    Returns None if the structure cannot be parsed.
    """
    parts = _split_if_args(expr)
    if parts is None:
        return None
    cond_str, then_str, else_str = parts

    clauses = _split_top_level(cond_str, '&&')
    p_then = 1.0
    for clause in clauses:
        if not clause:
            return None
        p = _clause_probability(
            clause, local_samplers, variables, sd, pack_reg, _depth)
        if p is None:
            return None
        p_then *= p
    p_then = max(0.0, min(1.0, p_then))

    then_cdf = _resolve_branch_cdf(
        then_str, local_samplers, variables, sd, pack_reg, _depth)
    else_cdf = _resolve_branch_cdf(
        else_str, local_samplers, variables, sd, pack_reg, _depth)
    if then_cdf is None or else_cdf is None:
        return None

    return NumericalCDF.mixture(
        [then_cdf, else_cdf], [p_then, 1.0 - p_then])


def _resolve_expression_cdf(sampler: Dict,
                           sd: SamplerDistribution,
                           pack_reg: Optional[PackSamplerRegistry],
                           _depth: int) -> Optional[NumericalCDF]:
    """
    Resolve an EXPRESSION sampler's distribution.  Tries the following in order:

      1. Bare function call ``funcName(x, z)``
      2. Affine wrapper ``funcCall(x,z) * k + c``
      3. Simple arithmetic patterns (shift, scale, max, min, linear map)
      4. Binary if-expression (with proper CDF-based P(condition))
      5. Generic nested-if fallback (uniform [-1, 1])
    """
    expr = str(sampler.get("expression", ""))
    if not expr.strip():
        return None

    local_samplers = sampler.get("samplers", {}) or {}
    variables      = sampler.get("variables", {}) or {}

    # Try arithmetic patterns first (covers bare call, shift, scale, max, min, linear)
    cdf = _try_pattern_arithmetic(expr, local_samplers, variables, sd, pack_reg, _depth)
    if cdf is not None:
        _explain('arith', expr, cdf)
        return cdf

    # Affine wrapper "f(x, z) * k + c" (kept for legacy paths even though _try_pattern covers it)
    _NUM = _NUM_RE
    affine_pattern = re.match(
        r'^\s*([a-zA-Z_]\w*)\s*\(\s*x\s*(?:/[^,)]+)?\s*,\s*z\s*(?:/[^,)]+)?\s*\)\s*'
        r'\*\s*(' + _NUM + r')\s*'
        r'(?:([+-])\s*(' + _NUM + r'))?\s*$',
        expr.strip()
    )
    if affine_pattern:
        func_name = affine_pattern.group(1)
        try:
            scale_val = float(affine_pattern.group(2))
            shift_val = 0.0
            if affine_pattern.group(3) and affine_pattern.group(4):
                sign = 1.0 if affine_pattern.group(3) == '+' else -1.0
                shift_val = sign * float(affine_pattern.group(4))
            cdf = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
            if cdf is not None:
                out = cdf.scale(scale_val).shift(shift_val)
                _explain('affine', expr, out)
                return out
        except ValueError:
            pass

    # Binary if patterns
    cdf = _resolve_binary_if_cdf(expr, local_samplers, variables, sd, pack_reg, _depth)
    if cdf is not None:
        _explain('if', expr, cdf)
        return cdf

    # General recursive evaluator (nested min/max/abs/arithmetic over sampler
    # calls) — resolves compound gate fields down to their leaf samplers.
    val = _eval_value_cdf(expr, local_samplers, variables, sd, pack_reg, _depth)
    if val is not None and val[0] is not None:
        _explain('value', expr, val[0])
        return val[0]

    # Generic nested-if fallback — assume 50/50 split between two outputs ∈ {-1, 1}
    if re.search(r'\bif\b', expr) and \
       set(re.findall(r'(?<![a-zA-Z0-9_])(-?1)(?!\.\d)', expr)) <= {'-1', '1'}:
        out = NumericalCDF.uniform(-1.0, 1.0)
        _explain('FALLBACK-binary', expr, out)
        return out

    _explain('UNRESOLVED', expr)
    return None


# =============================================================================
# Sampler-config resolver
# =============================================================================

MAX_DEPTH = 20

def resolve_sampler_cdf(sampler: Any,
                       sd: SamplerDistribution,
                       pack_reg: Optional[PackSamplerRegistry] = None,
                       _depth: int = 0) -> NumericalCDF:
    """
    Recursively resolve a sampler config dict into a NumericalCDF.

    Handles:
      - CONSTANT, leaf noise types (via empirical CDFs)
      - CACHE / TRANSLATE / DOMAIN_WARP → transparent wrappers
      - FBM / RIDGED / PINGPONG → convolution-based composition
      - CLAMP / LINEAR / LINEAR_MAP → CDF transformations
      - NORMALIZER / EXPRESSION_NORMALIZER → affine over inner
      - ADD / SUB / MUL / DIV / MAX / MIN → binary composition
      - CELLULAR (default Distance / CellValue / NoiseLookup)
      - EXPRESSION → text-pattern resolution
    """
    if _depth > MAX_DEPTH:
        return NumericalCDF.uniform()
    if not isinstance(sampler, dict):
        return NumericalCDF.uniform()

    t = sampler.get("type", "")

    if t == "CONSTANT":
        val = sampler.get("value", 0.0)
        if isinstance(val, (int, float)):
            return NumericalCDF.constant(float(val))
        return NumericalCDF.constant(0.0)

    if t == "CELLULAR" and sampler.get("return") == "CellValue":
        return NumericalCDF.uniform(-1.0, 1.0)

    if t == "CELLULAR" and sampler.get("return") == "NoiseLookup":
        lookup = sampler.get("lookup")
        if lookup:
            return resolve_sampler_cdf(lookup, sd, pack_reg, _depth + 1)
        dist_data = sd._distributions.get("CELLULAR")
        if isinstance(dist_data, list) and len(dist_data) >= 2:
            return NumericalCDF.from_breakpoints(dist_data)
        return NumericalCDF.uniform()

    if t in ("CACHE", "DOMAIN_WARP", "TRANSLATE"):
        inner = sampler.get("sampler")
        if inner:
            return resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1)
        return NumericalCDF.uniform()

    if t in ("FBM", "RIDGED", "PINGPONG"):
        inner   = sampler.get("sampler")
        octaves = max(1, int(sampler.get("octaves", 3)))
        gain    = float(sampler.get("gain", 0.5))

        inner_cdf = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else NumericalCDF.uniform()

        if abs(gain - 1.0) < 1e-9:
            amp_sum = float(octaves)
        else:
            amp_sum = (1.0 - gain ** octaves) / (1.0 - gain)
        fractal_bounding = 1.0 / amp_sum if amp_sum > 0 else 1.0

        # Convolution of scaled inner CDFs
        acc = inner_cdf.scale(1.0 * fractal_bounding)
        scale_i = gain * fractal_bounding
        for _ in range(1, octaves):
            acc = acc.add(inner_cdf.scale(scale_i))
            scale_i *= gain

        if t == "RIDGED":
            pdf = acc._get_pdf()
            total_p = sum(pdf) or 1.0
            mean = sum(pdf[i] * acc._val(i) for i in range(acc.BINS)) / total_p
            var  = sum(pdf[i] * (acc._val(i) - mean) ** 2 for i in range(acc.BINS)) / total_p
            return NumericalCDF.gaussian(0.0, max(0.01, _math.sqrt(var)) * 0.7)

        return acc

    if t == "PSEUDOEROSION":
        inner   = sampler.get("sampler")
        octaves = sampler.get("octaves", 3)
        gain    = sampler.get("gain", 0.5)
        _ = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else None
        g2 = gain * gain
        inner_var = 1.0 / 3.0
        var_sum = inner_var * (1.0 - g2 ** octaves) / max(1e-9, 1.0 - g2)
        return NumericalCDF.gaussian(0.0, max(0.01, _math.sqrt(var_sum)))

    if t == "CLAMP":
        inner = sampler.get("sampler")
        lo = sampler.get("min", -1.0)
        hi = sampler.get("max",  1.0)
        inner_cdf = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else NumericalCDF.uniform()
        return inner_cdf.clamp_dist(float(lo), float(hi))

    if t == "LINEAR":
        inner   = sampler.get("sampler")
        in_min  = sampler.get("min", -1.0)
        in_max  = sampler.get("max",  1.0)
        inner_cdf = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else NumericalCDF.uniform()
        # LinearNormalizer.normalize: output = (input - min) * 2 / (max - min) - 1
        return inner_cdf.linear_map(float(in_min), float(in_max), -1.0, 1.0)

    if t == "LINEAR_MAP":
        inner = sampler.get("sampler")
        in_min = float(sampler.get("min", -1.0))
        in_max = float(sampler.get("max",  1.0))
        out_min = float(sampler.get("to-min", 0.0))
        out_max = float(sampler.get("to-max", 1.0))
        inner_cdf = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else NumericalCDF.uniform()
        return inner_cdf.linear_map(in_min, in_max, out_min, out_max)

    if t in ("NORMALIZER", "EXPRESSION_NORMALIZER"):
        inner = sampler.get("sampler")
        inner_cdf = resolve_sampler_cdf(inner, sd, pack_reg, _depth + 1) if inner else NumericalCDF.uniform()
        expr = str(sampler.get("expression", "in"))
        affine = _parse_affine_expression(expr)
        if affine is not None:
            scale_val, shift_val = affine
            return inner_cdf.scale(scale_val).shift(shift_val)
        return inner_cdf

    if t in ("ADD", "SUB", "MUL", "DIV", "MAX", "MIN"):
        left  = sampler.get("left")
        right = sampler.get("right")
        left_cdf  = resolve_sampler_cdf(left,  sd, pack_reg, _depth + 1) if left  else NumericalCDF.uniform()
        right_cdf = resolve_sampler_cdf(right, sd, pack_reg, _depth + 1) if right else NumericalCDF.uniform()

        if t == "ADD":
            return left_cdf.add(right_cdf)
        elif t == "SUB":
            return left_cdf.subtract(right_cdf)
        elif t == "MUL":
            if isinstance(right, dict) and right.get("type") == "CONSTANT":
                return left_cdf.scale(float(right.get("value", 1.0)))
            if isinstance(left, dict) and left.get("type") == "CONSTANT":
                return right_cdf.scale(float(left.get("value", 1.0)))
            # Moment-matched Gaussian for product of two RVs
            pdf_l = left_cdf._get_pdf()
            pdf_r = right_cdf._get_pdf()
            tl = sum(pdf_l) or 1.0
            tr = sum(pdf_r) or 1.0
            ml = sum(pdf_l[i] * left_cdf._val(i) for i in range(left_cdf.BINS)) / tl
            mr = sum(pdf_r[i] * right_cdf._val(i) for i in range(right_cdf.BINS)) / tr
            vl = sum(pdf_l[i] * left_cdf._val(i)**2 for i in range(left_cdf.BINS)) / tl - ml**2
            vr = sum(pdf_r[i] * right_cdf._val(i)**2 for i in range(right_cdf.BINS)) / tr - mr**2
            mean_prod = ml * mr
            var_prod  = ml**2 * max(0, vr) + mr**2 * max(0, vl) + max(0, vl) * max(0, vr)
            return NumericalCDF.gaussian(mean_prod, max(0.01, _math.sqrt(var_prod)))
        elif t == "DIV":
            if isinstance(right, dict) and right.get("type") == "CONSTANT":
                c = float(right.get("value", 1.0))
                if c != 0:
                    return left_cdf.scale(1.0 / c)
            return left_cdf
        elif t == "MAX":
            return left_cdf.max_with(right_cdf)
        elif t == "MIN":
            return left_cdf.min_with(right_cdf)

    if t == "EXPRESSION":
        cdf = _resolve_expression_cdf(sampler, sd, pack_reg, _depth)
        if cdf is not None:
            return cdf
        return NumericalCDF.uniform()

    if t == "PROBABILITY":
        return NumericalCDF.uniform()

    # Leaf noise types — look up empirical CDF
    dist_data = sd._distributions.get(t)
    if isinstance(dist_data, list) and len(dist_data) >= 2:
        return NumericalCDF.from_breakpoints(dist_data)
    if dist_data == SamplerDistribution._CONSTANT_TAG:
        return NumericalCDF.constant(0.0)

    return NumericalCDF.uniform()


# =============================================================================
# Public entrypoint
# =============================================================================

def compute_slot_probabilities(sampler_config: Any, weights: List[int]) -> List[float]:
    """
    Resolve a sampler config to a NumericalCDF and produce per-slot probabilities
    for a weighted list.  Convenience wrapper around resolve_sampler_cdf +
    NumericalCDF.slot_probabilities.
    """
    sd = get_sampler_dist()
    pack_reg = get_pack_registry()
    cdf = resolve_sampler_cdf(sampler_config, sd, pack_reg)
    return cdf.slot_probabilities(weights)
