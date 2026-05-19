"""
Slant threshold converter: legacy Derivative method → DotProduct method.

Background
----------
Terra originally used only the Derivative slant calculation (gradient magnitude).
In November 2022 the DotProduct method was introduced; CHIMERA adopted it in
December 2022 (pack.yml: calculation-method: DotProduct).

Biomes authored before the switch (e.g. Hydraxia biomes missed in the Aug 2022
rebalancing pass) retain Derivative-era thresholds that are always above the
DotProduct output range of [-1, 1] and therefore always fire.

Maths
-----
Both methods use DERIVATIVE_DIST = 0.55. For a surface tilted at angle θ from
horizontal, with standard 2D heightmap terrain (f = -y + noise2d(x, z)):

    Derivative = 2.0 / cos(θ)       range [2.0, ∞),  fires when slant > threshold
    DotProduct = cos(θ)              range [-1.0, 1.0], fires when slant < threshold

Equivalence condition (same trigger angle θ):
    2.0 / cos(θ) > D_threshold  ↔  cos(θ) < 2.0 / D_threshold

So:  DotProduct_threshold = 2.0 / Derivative_threshold

Note: this is exact for smooth 2D heightmap terrain. FBM/multi-octave noise
adds high-frequency surface variation that lowers effective DotProduct values
even on macroscopically flat ground. Empirically the pack tends to use values
slightly more conservative than the formula predicts — treat formula output as
a starting point and verify in-game for complex terrain equations.
"""

import math


DERIVATIVE_DIST = 0.55     # Terra constant, unchanged throughout history
FLAT_DERIVATIVE = 2.0      # Derivative value on a perfectly flat surface = 2*d/d = 2


def curve_fit(old: float) -> float:
    """
    Curve fit through empirical TOC conversion anchor points:
        2 → 0.6,  4 → 0.4,  8 → 0.2,  16 → 0

    Each doubling of the old threshold drops the result by 0.2, giving:
        new = 0.8 - 0.2 * log2(old)

    This matches TOC's empirical bulk conversion (commit 7d82e1a8) more
    closely than the theoretical 2/x formula for smooth terrain.
    """
    import math
    if old <= 0:
        raise ValueError(f"Threshold must be positive, got {old}")
    return round(0.8 - 0.2 * math.log2(old), 2)


def derivative_to_dotproduct(old: float) -> float:
    """Convert a legacy Derivative threshold to its DotProduct equivalent.

    Args:
        old: Derivative-method threshold (historical range ~2–15).
             Values <= 2.0 would trigger even on flat terrain (result >= 1.0).

    Returns:
        Equivalent DotProduct threshold in (0, 1].
        Values > 1.0 mean the original threshold was below 2.0 (flat-surface trigger).
    """
    if old <= 0:
        raise ValueError(f"Derivative threshold must be positive, got {old}")
    return FLAT_DERIVATIVE / old


def dotproduct_to_derivative(new: float) -> float:
    """Inverse: convert a DotProduct threshold back to a Derivative equivalent."""
    if new <= 0:
        raise ValueError(f"DotProduct threshold must be positive, got {new}")
    return FLAT_DERIVATIVE / new


def trigger_angle(threshold: float, method: str = "dotproduct") -> float:
    """Return the surface angle (degrees from horizontal) at which a threshold fires.

    For DotProduct: fires when cos(θ) < threshold  →  θ > acos(threshold)
    For Derivative: fires when 2/cos(θ) > threshold  →  θ > acos(2/threshold)
    """
    if method.lower() == "dotproduct":
        cos_theta = min(1.0, max(-1.0, threshold))
    elif method.lower() == "derivative":
        cos_theta = FLAT_DERIVATIVE / threshold
        if cos_theta >= 1.0:
            return 0.0  # threshold <= 2.0: fires on flat terrain
        cos_theta = min(1.0, max(-1.0, cos_theta))
    else:
        raise ValueError(f"Unknown method '{method}', use 'dotproduct' or 'derivative'")
    return math.degrees(math.acos(cos_theta))


def convert_slant_list(thresholds):  # list[float] -> list[tuple[float, float, float]]
    """Convert a list of Derivative thresholds, returning (old, new, angle_deg) tuples."""
    return [(t, round(derivative_to_dotproduct(t), 3), round(trigger_angle(t, "derivative"), 1))
            for t in thresholds]


# ---------------------------------------------------------------------------
# Reference table: Hydraxia biomes corrected in BiomeTests branch
# Compares mathematically derived values against what was applied.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"{'Old (Deriv)':>12}  {'Math (DP)':>10}  {'Applied (DP)':>13}  {'Angle °':>8}")
    print("-" * 52)

    cases = [
        # (old_threshold, applied_threshold, biome_note)
        (2.0,  0.30,  "muskeg"),
        (2.5,  0.35,  "icebound/sakura/enchanted/chilly_creek [low]"),
        (2.7,  0.40,  "frozen_spires, frostbite_rivers"),
        (3.0,  0.40,  "oak/redwood/spruce/sugar_pine [low], glacial [low]"),
        (3.5,  0.50,  "autumnal, birch/maple [low], dark_oak [user]"),
        (4.0,  0.55,  "bitter/fir/lavender/permafrost, searing_tors [low]"),
        (5.0,  0.65,  "drafty_stream, glacial [mid]"),
        (6.0,  0.75,  "glacial [high]"),
        (7.0,  0.85,  "arctic_mesa [high] — dead code in original"),
    ]

    for old, applied, note in cases:
        math_val = derivative_to_dotproduct(old)
        angle = trigger_angle(old, "derivative")
        flag = "  <-- diverges" if abs(math_val - applied) > 0.15 else ""
        print(f"{old:>12.1f}  {math_val:>10.3f}  {applied:>13.3f}  {angle:>7.1f}°   {note}{flag}")
