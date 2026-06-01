"""Faithful (marginal-only) reimplementation of Minecraft's climate NormalNoise.

For AREA-DISTRIBUTION purposes the world seed is irrelevant: only the marginal
value distribution of each climate field matters, and the 5 climate fields
(temperature, humidity/vegetation, continentalness, erosion, weirdness/ridge)
are independent NormalNoise fields. We therefore reproduce the exact
NormalNoise -> PerlinNoise -> ImprovedNoise value pipeline (matching
Paper sources) with an arbitrary permutation, and sample at random positions to
recover each field's marginal.

Sources (Paper / Mojang mappings):
  ImprovedNoise.java, PerlinNoise.java, NormalNoise.java, SimplexNoise.GRADIENT
"""
import numpy as np

GRADIENT = np.array([
    [1, 1, 0], [-1, 1, 0], [1, -1, 0], [-1, -1, 0],
    [1, 0, 1], [-1, 0, 1], [1, 0, -1], [-1, 0, -1],
    [0, 1, 1], [0, -1, 1], [0, 1, -1], [0, -1, -1],
    [1, 1, 0], [0, -1, 1], [-1, 1, 0], [0, -1, -1],
], dtype=np.float64)

INPUT_FACTOR = 1.0181268882175227


def _smoothstep(t):
    # Mth.smoothstep: t*t*t*(t*(t*6-15)+10)
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


class ImprovedNoise:
    def __init__(self, rng):
        self.xo = rng.random() * 256.0
        self.yo = rng.random() * 256.0
        self.zo = rng.random() * 256.0
        p = list(range(256))
        for i in range(256):
            off = rng.randrange(256 - i)
            p[i], p[i + off] = p[i + off], p[i]
        self.p = np.array(p, dtype=np.int64)

    def _p(self, x):
        return self.p[x & 0xFF].astype(np.int64) & 0xFF

    def noise(self, _x, _y, _z):
        # y = 0 plane is fine for marginals; keep full 3D for fidelity.
        x = _x + self.xo
        y = _y + self.yo
        z = _z + self.zo
        xf = np.floor(x).astype(np.int64)
        yf = np.floor(y).astype(np.int64)
        zf = np.floor(z).astype(np.int64)
        xr = x - xf
        yr = y - yf
        zr = z - zf

        x0 = self._p(xf)
        x1 = self._p(xf + 1)
        xy00 = self._p(x0 + yf)
        xy01 = self._p(x0 + yf + 1)
        xy10 = self._p(x1 + yf)
        xy11 = self._p(x1 + yf + 1)

        def gd(idx, dx, dy, dz):
            g = GRADIENT[(idx & 15)]
            return g[:, 0] * dx + g[:, 1] * dy + g[:, 2] * dz

        d000 = gd(self._p(xy00 + zf), xr, yr, zr)
        d100 = gd(self._p(xy10 + zf), xr - 1.0, yr, zr)
        d010 = gd(self._p(xy01 + zf), xr, yr - 1.0, zr)
        d110 = gd(self._p(xy11 + zf), xr - 1.0, yr - 1.0, zr)
        d001 = gd(self._p(xy00 + zf + 1), xr, yr, zr - 1.0)
        d101 = gd(self._p(xy10 + zf + 1), xr - 1.0, yr, zr - 1.0)
        d011 = gd(self._p(xy01 + zf + 1), xr, yr - 1.0, zr - 1.0)
        d111 = gd(self._p(xy11 + zf + 1), xr - 1.0, yr - 1.0, zr - 1.0)

        xa = _smoothstep(xr)
        ya = _smoothstep(yr)
        za = _smoothstep(zr)

        # trilinear lerp (Mth.lerp3)
        def lerp(a, lo, hi):
            return lo + a * (hi - lo)
        x00 = lerp(xa, d000, d100)
        x10 = lerp(xa, d010, d110)
        x01 = lerp(xa, d001, d101)
        x11 = lerp(xa, d011, d111)
        y0 = lerp(ya, x00, x10)
        y1 = lerp(ya, x01, x11)
        return lerp(za, y0, y1)


class PerlinNoise:
    def __init__(self, rng, first_octave, amplitudes):
        self.first_octave = first_octave
        self.amplitudes = amplitudes
        octaves = len(amplitudes)
        zero_octave_index = -first_octave
        self.levels = [None] * octaves
        for i in range(octaves):
            if amplitudes[i] != 0.0:
                self.levels[i] = ImprovedNoise(rng)
        self.lowest_freq_input_factor = 2.0 ** (-zero_octave_index)
        self.lowest_freq_value_factor = (2.0 ** (octaves - 1)) / (2.0 ** octaves - 1.0)

    def get_value(self, x, y, z):
        value = np.zeros_like(x)
        factor = self.lowest_freq_input_factor
        vfactor = self.lowest_freq_value_factor
        for i, noise in enumerate(self.levels):
            if noise is not None:
                nv = noise.noise(_wrap(x * factor), _wrap(y * factor), _wrap(z * factor))
                value += self.amplitudes[i] * nv * vfactor
            factor *= 2.0
            vfactor /= 2.0
        return value


def _wrap(x):
    return x - np.floor(x / 3.3554432e7 + 0.5) * 3.3554432e7


class NormalNoise:
    def __init__(self, rng, first_octave, amplitudes):
        self.first = PerlinNoise(rng, first_octave, amplitudes)
        self.second = PerlinNoise(rng, first_octave, amplitudes)
        nz = [i for i, a in enumerate(amplitudes) if a != 0.0]
        span = max(nz) - min(nz)
        expected_dev = 0.1 * (1.0 + 1.0 / (span + 1))
        self.value_factor = 0.16666666666666666 / expected_dev

    def get_value(self, x, y, z):
        a = self.first.get_value(x, y, z)
        b = self.second.get_value(x * INPUT_FACTOR, y * INPUT_FACTOR, z * INPUT_FACTOR)
        return (a + b) * self.value_factor


# Exact octave configs from data/minecraft/worldgen/noise/*.json
NOISE_PARAMS = {
    "continentalness": (-9, [1.0, 1.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0]),
    "erosion":         (-9, [1.0, 1.0, 0.0, 1.0, 1.0]),
    "weirdness":       (-7, [1.0, 2.0, 1.0, 0.0, 0.0, 0.0]),   # ridge.json
    "temperature":     (-10, [1.5, 0.0, 1.0, 0.0, 0.0, 0.0]),
    "humidity":        (-8, [1.0, 1.0, 0.0, 0.0, 0.0, 0.0]),   # vegetation.json
}


def sample_marginal(field, n, seed, coord_range=2.0e6):
    """Return n samples of the given climate field's marginal value."""
    import random
    rng = random.Random(seed)
    first_octave, amps = NOISE_PARAMS[field]
    noise = NormalNoise(rng, first_octave, amps)
    pos_rng = np.random.default_rng(seed + 1)
    xs = pos_rng.uniform(-coord_range, coord_range, n)
    zs = pos_rng.uniform(-coord_range, coord_range, n)
    ys = np.zeros(n)
    # batch to limit memory
    out = np.empty(n, dtype=np.float64)
    B = 200000
    for s in range(0, n, B):
        e = min(s + B, n)
        out[s:e] = noise.get_value(xs[s:e], ys[s:e], zs[s:e])
    return out


if __name__ == "__main__":
    for f in NOISE_PARAMS:
        v = sample_marginal(f, 400000, seed=12345)
        print(f"{f:15s} mean={v.mean():+.4f} std={v.std():.4f} "
              f"min={v.min():+.3f} max={v.max():+.3f} "
              f"p01={np.percentile(v,1):+.3f} p99={np.percentile(v,99):+.3f}")
    # continentalness ocean fraction sanity (land = continentalness > -0.19)
    c = sample_marginal("continentalness", 800000, seed=999)
    print(f"\ncontinentalness: P(<-0.455 deepocean)={np.mean(c<-0.455):.3f} "
          f"P(<-0.19 ocean+)={np.mean(c<-0.19):.3f} "
          f"P(<-0.11 coast+)={np.mean(c<-0.11):.3f}")
