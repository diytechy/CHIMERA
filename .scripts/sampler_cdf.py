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
        if name in self._cdf_cache:
            return self._cdf_cache[name]
        cfg = self._configs.get(name)
        if cfg is None:
            return None
        cdf = resolve_sampler_cdf(cfg, get_sampler_dist(), self)
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

    return None


def _resolve_binary_if_cdf(expr: str,
                          local_samplers: Dict,
                          variables: Dict[str, Any],
                          sd: SamplerDistribution,
                          pack_reg: Optional[PackSamplerRegistry],
                          _depth: int) -> Optional[NumericalCDF]:
    """
    Resolve a binary if-expression of one of these forms:

        if(funcCall OP threshold, val_then, val_else)
        if(funcA(args) OP funcB(args), val_then, val_else)
        if(funcCall OP threshold && funcCall2 OP threshold, val_then, val_else)

    where val_then / val_else are numeric literals.  Computes P(condition)
    against the function CDFs and returns a 2-point distribution.

    Returns None if no pattern matches.
    """
    e = ' '.join(expr.split())

    # ── (a) Simple: if(func(args) OP num_or_const, val_then, val_else) ──
    m = re.match(
        rf'^if\s*\(\s*'
        rf'([a-zA-Z_]\w*)\s*\([^)]*\)'
        rf'\s*(>=|<=|>|<|==|!=)\s*'
        rf'((?:{_NUM_RE})|(?:\([^)]+\)))'
        rf'\s*,\s*({_NUM_RE})\s*,\s*({_NUM_RE})\s*\)\s*$',
        e
    )
    if m:
        func_name = m.group(1)
        op        = m.group(2)
        thresh_raw = m.group(3)
        threshold = _eval_constant_expr(thresh_raw, variables)
        if threshold is None:
            try:
                threshold = float(thresh_raw)
            except ValueError:
                threshold = None
        if threshold is not None:
            val_then  = float(m.group(4))
            val_else  = float(m.group(5))
            return _binary_if_result(func_name, op, threshold, val_then, val_else,
                                     local_samplers, sd, pack_reg, _depth)

    # ── (b) func1 OP func2: if(funcA(args) OP funcB(args), val_then, val_else) ──
    m = re.match(
        rf'^if\s*\(\s*'
        rf'([a-zA-Z_]\w*)\s*\([^)]*\)'
        rf'\s*(>=|<=|>|<|==|!=)\s*'
        rf'([a-zA-Z_]\w*)\s*\([^)]*\)'
        rf'\s*,\s*({_NUM_RE})\s*,\s*({_NUM_RE})\s*\)\s*$',
        e
    )
    if m:
        nameA = m.group(1)
        op    = m.group(2)
        nameB = m.group(3)
        val_then = float(m.group(4))
        val_else = float(m.group(5))
        cdfA = _lookup_sampler_cdf(nameA, local_samplers, sd, pack_reg, _depth)
        cdfB = _lookup_sampler_cdf(nameB, local_samplers, sd, pack_reg, _depth)
        if cdfA is not None and cdfB is not None:
            diff = cdfA.subtract(cdfB)
            zero_p = diff.eval_cdf(0.0)
            if op in ('>', '>='):
                p_then = 1.0 - zero_p
            elif op in ('<', '<='):
                p_then = zero_p
            else:
                p_then = 0.5
            return _two_point(val_then, val_else, p_then)

    # ── (c) Compound &&: two AND-joined simple comparisons ──
    m = re.match(
        rf'^if\s*\(\s*'
        rf'([a-zA-Z_]\w*)\s*\([^)]*\)'
        rf'\s*(>=|<=|>|<|==|!=)\s*'
        rf'((?:{_NUM_RE})|(?:\([^)]+\)))'
        rf'\s*&&\s*'
        rf'([a-zA-Z_]\w*)\s*\([^)]*\)'
        rf'\s*(>=|<=|>|<|==|!=)\s*'
        rf'((?:{_NUM_RE})|(?:\([^)]+\)))'
        rf'\s*,\s*'
        rf'((?:{_NUM_RE})|(?:[a-zA-Z_]\w*\s*\([^)]*\)))'
        rf'\s*,\s*({_NUM_RE})\s*\)\s*$',
        e
    )
    if m:
        nA, opA, tA_raw = m.group(1), m.group(2), m.group(3)
        nB, opB, tB_raw = m.group(4), m.group(5), m.group(6)
        val_then_str = m.group(7)
        val_else = float(m.group(8))
        # Both comparison thresholds must be numeric/constant
        tA = _eval_constant_expr(tA_raw, variables)
        if tA is None:
            try: tA = float(tA_raw)
            except ValueError: tA = None
        tB = _eval_constant_expr(tB_raw, variables)
        if tB is None:
            try: tB = float(tB_raw)
            except ValueError: tB = None
        if tA is None or tB is None:
            return None
        # val_then can be a function call or a number — but only handle numeric here
        try:
            val_then = float(val_then_str)
        except ValueError:
            return None
        # Compute P(A_cond AND B_cond) under independence assumption
        cdfA = _lookup_sampler_cdf(nA, local_samplers, sd, pack_reg, _depth)
        cdfB = _lookup_sampler_cdf(nB, local_samplers, sd, pack_reg, _depth)
        if cdfA is None or cdfB is None:
            return None
        pA = (1.0 - cdfA.eval_cdf(tA)) if opA in ('>', '>=') else cdfA.eval_cdf(tA)
        pB = (1.0 - cdfB.eval_cdf(tB)) if opB in ('>', '>=') else cdfB.eval_cdf(tB)
        p_then = max(0.0, min(1.0, pA * pB))
        return _two_point(val_then, val_else, p_then)

    return None


def _binary_if_result(func_name: str, op: str, threshold: float,
                     val_then: float, val_else: float,
                     local_samplers: Dict,
                     sd: SamplerDistribution,
                     pack_reg: Optional[PackSamplerRegistry],
                     _depth: int) -> NumericalCDF:
    """Build the 2-point CDF for if(funcName OP threshold, val_then, val_else)."""
    cond_cdf = _lookup_sampler_cdf(func_name, local_samplers, sd, pack_reg, _depth)
    if cond_cdf is not None:
        cdf_at = cond_cdf.eval_cdf(threshold)
        if op in ('>', '>='):
            p_then = 1.0 - cdf_at
        elif op in ('<', '<='):
            p_then = cdf_at
        else:
            p_then = 0.5
    else:
        # Heuristic by function name when CDF unavailable.
        name_lower = func_name.lower()
        if 'mask' in name_lower or 'mountain' in name_lower or 'spike' in name_lower:
            p_then = 0.10
        elif 'plain' in name_lower or 'flat' in name_lower:
            p_then = 0.30
        else:
            p_then = 0.25
    return _two_point(val_then, val_else, p_then)


def _two_point(val_then: float, val_else: float, p_then: float) -> NumericalCDF:
    """Construct a 2-point CDF: mass p_then at val_then, (1−p_then) at val_else."""
    val_lo, val_hi = min(val_then, val_else), max(val_then, val_else)
    if val_then < val_else:
        p_lo = p_then
    else:
        p_lo = 1.0 - p_then
    return NumericalCDF.binary(val_lo, val_hi, p_lo)


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
                return cdf.scale(scale_val).shift(shift_val)
        except ValueError:
            pass

    # Binary if patterns
    cdf = _resolve_binary_if_cdf(expr, local_samplers, variables, sd, pack_reg, _depth)
    if cdf is not None:
        return cdf

    # Generic nested-if fallback — assume 50/50 split between two outputs ∈ {-1, 1}
    if re.search(r'\bif\b', expr) and \
       set(re.findall(r'(?<![a-zA-Z0-9_])(-?1)(?!\.\d)', expr)) <= {'-1', '1'}:
        return NumericalCDF.uniform(-1.0, 1.0)

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
