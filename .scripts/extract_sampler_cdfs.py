#!/usr/bin/env python3
"""
extract_sampler_cdfs.py

Reads histogram PNG images from NoiseTool/Distribution_Ref/ and extracts
piecewise-linear CDF breakpoints for each sampler type.

Filename convention (used by NoiseTool when saving distribution reference images):
    TYPE_MIN_to_MAX.png
    Where 'p' is used as the decimal-point prefix for positive fractions:
        p25 → 0.25,  -1 → -1.0,  5 → 5.0

Image format:
    - Dark gray background (~60-70 brightness)
    - Light gray histogram bars (~200-220 brightness), filling from the bottom up
    - Number label in the top-left corner (skipped during analysis)

Output:
    sampler_distributions.yml  (same directory as this script)
    Format: distributions.<TYPE>: [[value, cdf_probability], ...]
    Interpolate linearly between points; clamp outside range to 0.0/1.0.

Sampler types with no PNG reference (EXPRESSION, DOMAIN_WARP, FBM, etc.) are
written with the string "uniform" as a fallback; "constant" for CONSTANT type.

Re-run this script whenever new reference images are added to Distribution_Ref/.
"""
from ensure_module import ensure_module

ensure_module("PIL", "Pillow")
ensure_module("yaml", "PyYAML")

from PIL import Image
import yaml
from pathlib import Path
import re
import bisect

# =============================================================================
# CONFIGURATION
# =============================================================================

DIST_REF_DIR = Path("C:/Projects/NoiseTool/Distribution_Ref")
OUTPUT_PATH  = Path(__file__).parent / "sampler_distributions.yml"

# Pixels brighter than this are counted as histogram bar (not background).
# Background is ~60-70 brightness; bars are ~200-220.
BRIGHTNESS_THRESHOLD = 128

# Rows to skip at the top of each image (avoids the text label in the corner).
N_HEADER_ROWS = 40

# Number of CDF breakpoints to output per sampler type.
# Breakpoints are placed adaptively: more points where the CDF changes fastest.
N_OUTPUT_POINTS = 30

# Decimal places for output values and CDF probabilities.
VALUE_DECIMALS = 5
CDF_DECIMALS   = 5

# Sampler types with no PNG reference image.
# "uniform"  → treat as linearly uniform across [-1, 1] in the main script.
# "constant" → always outputs 0.0; picks the midpoint slot.
SYNTHETIC_ENTRIES = {
    "FBM":         "uniform",
    "DOMAIN_WARP": "uniform",
    "EXPRESSION":  "uniform",
    "CACHE":       "uniform",
    "LINEAR":      "uniform",
    "LINEAR_MAP":  "uniform",
    "CLAMP":       "uniform",
    "NORMALIZER":  "uniform",
    "CONSTANT":    "constant",
}


# =============================================================================
# FILENAME PARSING
# =============================================================================

def _parse_range_value(s: str) -> float:
    """
    Parse a range component from a NoiseTool filename.

    Positive fractions use 'p' as the decimal separator:
        "p25"  → 0.25
        "p125" → 0.125
    Plain integers and negative floats are parsed normally:
        "1"   → 1.0
        "-1"  → -1.0
        "5"   → 5.0
    """
    if s.startswith("p"):
        return float("0." + s[1:])
    return float(s)


def parse_filename(stem: str):
    """
    Parse a NoiseTool histogram filename stem into (sampler_type, min_val, max_val).

    Examples:
        "CELLULAR_-1_to_p25"         → ("CELLULAR", -1.0, 0.25)
        "OPEN_SIMPLEX_2_-1_to_1"     → ("OPEN_SIMPLEX_2", -1.0, 1.0)
        "GAUSSIAN_-5_to_5"           → ("GAUSSIAN", -5.0, 5.0)
        "VALUE_CUBIC_-1_to_1"        → ("VALUE_CUBIC", -1.0, 1.0)

    Returns None if the filename doesn't match the expected pattern.
    """
    # Pattern: TYPE (may contain underscores) _ NEGATIVE_OR_POS_NUMBER _to_ NUMBER
    # We locate '_to_' first, then peel off the min value from the right of the prefix.
    m = re.match(r"^(.+)_(-?\d+(?:\.\d+)?)_to_([p]?\d+(?:\.\d+)?)$", stem)
    if not m:
        return None
    sampler_type = m.group(1)
    min_val      = float(m.group(2))
    max_val      = _parse_range_value(m.group(3))
    return sampler_type, min_val, max_val


# =============================================================================
# CDF EXTRACTION
# =============================================================================

def extract_cdf(img_path: Path, min_val: float, max_val: float,
                n_points: int) -> list:
    """
    Extract a piecewise-linear CDF from a NoiseTool histogram PNG.

    Algorithm:
      1. Load image as grayscale.
      2. For each pixel column, count rows with brightness > BRIGHTNESS_THRESHOLD
         (skipping the top N_HEADER_ROWS to avoid the text label).
         This count is proportional to the probability density at that x position.
      3. Compute the cumulative sum → CDF at each column index.
      4. Normalise CDF to [0, 1].
      5. Sample N_OUTPUT_POINTS breakpoints by evenly spacing target CDF values
         (0.0, 1/(n-1), 2/(n-1), …, 1.0) and finding the corresponding x via
         binary search. This places more breakpoints where the PDF is densest.
      6. Map each x back to a noise value using the known range.

    Returns:
        List of [value, cdf_probability] pairs, sorted by value.
        First pair is always [min_val, 0.0]; last is [max_val, 1.0].
    """
    img = Image.open(img_path).convert("L")   # grayscale uint8
    width, height = img.size
    pixels = img.load()

    # --- Step 1: count bright pixels per column ---
    heights = []
    for x in range(width):
        count = sum(
            1 for y in range(N_HEADER_ROWS, height)
            if pixels[x, y] > BRIGHTNESS_THRESHOLD
        )
        heights.append(count)

    total = sum(heights)
    if total == 0:
        # Fallback: perfectly uniform
        return [[round(min_val, VALUE_DECIMALS), 0.0],
                [round(max_val, VALUE_DECIMALS), 1.0]]

    # --- Step 2: cumulative distribution at each column ---
    cum = []
    running = 0
    for h in heights:
        running += h
        cum.append(running / total)   # normalised CDF at column x

    # --- Step 3: adaptive breakpoint sampling ---
    # For each evenly-spaced target CDF value, find the leftmost x where
    # cum[x] >= target.  This clusters breakpoints in high-density regions.
    breakpoints = []
    for i in range(n_points):
        target_cdf = i / (n_points - 1)  # 0.0 … 1.0
        # bisect_left gives the insertion point (≡ first index where cum[x] >= target)
        x = bisect.bisect_left(cum, target_cdf)
        x = min(x, width - 1)
        v = min_val + (x / (width - 1)) * (max_val - min_val)
        c = cum[x]
        breakpoints.append([round(v, VALUE_DECIMALS), round(c, CDF_DECIMALS)])

    # --- Step 4: enforce exact endpoints and remove duplicates ---
    breakpoints[0]  = [round(min_val, VALUE_DECIMALS), 0.0]
    breakpoints[-1] = [round(max_val, VALUE_DECIMALS), 1.0]

    # Remove consecutive duplicates (can happen when many columns have zero height)
    deduped = [breakpoints[0]]
    for bp in breakpoints[1:]:
        if bp[0] != deduped[-1][0]:   # keep if value changed
            deduped.append(bp)
    deduped[-1] = [round(max_val, VALUE_DECIMALS), 1.0]

    return deduped


# =============================================================================
# YAML OUTPUT
# =============================================================================

def _format_breakpoints(bps) -> str:
    """Format a list of [value, cdf] pairs as a compact YAML flow sequence."""
    inner = ", ".join(f"[{v}, {c}]" for v, c in bps)
    return f"[{inner}]"


def write_output(distributions: dict) -> None:
    """Write sampler_distributions.yml with header comment and formatted entries."""
    lines = [
        "# Sampler output CDFs extracted from NoiseTool/Distribution_Ref/ images.",
        "# Each entry is a list of [value, cumulative_probability] breakpoints.",
        "# Interpolate linearly between points; clamp outside range to 0.0/1.0.",
        "# Entries with value 'uniform' are treated as perfectly uniform on [-1, 1].",
        "# Entries with value 'constant' always pick the midpoint slot.",
        "#",
        "# Re-generate by running:  python .scripts/extract_sampler_cdfs.py",
        "",
        "distributions:",
    ]

    # Sort: image-derived types first (they have list values), then synthetic
    image_types    = {k: v for k, v in distributions.items() if isinstance(v, list)}
    synthetic_types = {k: v for k, v in distributions.items() if isinstance(v, str)}

    for name in sorted(image_types):
        formatted = _format_breakpoints(image_types[name])
        lines.append(f"  {name}: {formatted}")

    if synthetic_types:
        lines.append("")
        lines.append("  # Fallback entries (no reference image available):")
        for name in sorted(synthetic_types):
            lines.append(f"  {name}: {synthetic_types[name]!r}")

    lines.append("")  # trailing newline
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    png_files = sorted(DIST_REF_DIR.glob("*.png"))
    if not png_files:
        print(f"No PNG files found in {DIST_REF_DIR}")
        return

    distributions = {}

    for png in png_files:
        result = parse_filename(png.stem)
        if result is None:
            print(f"WARNING: unrecognised filename format: {png.name}")
            continue

        sampler_type, min_val, max_val = result
        print(f"  {sampler_type:20s}  range [{min_val}, {max_val}]  ...", end=" ", flush=True)
        try:
            cdf = extract_cdf(png, min_val, max_val, N_OUTPUT_POINTS)
            distributions[sampler_type] = cdf
            print(f"{len(cdf)} breakpoints")
        except Exception as e:
            print(f"ERROR: {e}")

    # Add synthetic fallbacks for types without reference images
    for key, val in SYNTHETIC_ENTRIES.items():
        if key not in distributions:
            distributions[key] = val

    write_output(distributions)
    print(f"\nWrote {OUTPUT_PATH}")
    print(f"  {sum(1 for v in distributions.values() if isinstance(v, list))} image-derived types")
    print(f"  {sum(1 for v in distributions.values() if isinstance(v, str))} synthetic fallbacks")


if __name__ == "__main__":
    main()
