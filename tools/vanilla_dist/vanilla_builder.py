"""Port of net.minecraft.world.level.biome.OverworldBiomeBuilder (surface biomes).

Produces the list of climate parameter hyperrectangles -> vanilla biome that the
multi-noise biome source uses. Only SURFACE biomes are emitted (depth=0); the
underground/cave biomes are intentionally omitted because we only compare
surface area. Each entry: (t,h,c,e,w, biome) where each coord is an (min,max)
tuple in raw climate units (matching addSurfaceBiome with depth point(0)).
"""

# Climate parameter thresholds (verbatim from OverworldBiomeBuilder)
TEMPS = [(-1.0, -0.45), (-0.45, -0.15), (-0.15, 0.2), (0.2, 0.55), (0.55, 1.0)]
HUMID = [(-1.0, -0.35), (-0.35, -0.1), (-0.1, 0.1), (0.1, 0.3), (0.3, 1.0)]
EROS = [(-1.0, -0.78), (-0.78, -0.375), (-0.375, -0.2225), (-0.2225, 0.05),
        (0.05, 0.45), (0.45, 0.55), (0.55, 1.0)]
FULL = (-1.0, 1.0)

FROZEN_RANGE = TEMPS[0]
UNFROZEN_RANGE = (TEMPS[1][0], TEMPS[4][1])

mushroomFields = (-1.2, -1.05)
deepOcean = (-1.05, -0.455)
ocean = (-0.455, -0.19)
coast = (-0.19, -0.11)
inland = (-0.11, 0.55)
nearInland = (-0.11, 0.03)
midInland = (0.03, 0.3)
farInland = (0.3, 1.0)


def span(a, b):
    return (a[0], b[1])


OCEANS = [
    ["deep_frozen_ocean", "deep_cold_ocean", "deep_ocean", "deep_lukewarm_ocean", "warm_ocean"],
    ["frozen_ocean", "cold_ocean", "ocean", "lukewarm_ocean", "warm_ocean"],
]
MIDDLE_BIOMES = [
    ["snowy_plains", "snowy_plains", "snowy_plains", "snowy_taiga", "taiga"],
    ["plains", "plains", "forest", "taiga", "old_growth_spruce_taiga"],
    ["flower_forest", "plains", "forest", "birch_forest", "dark_forest"],
    ["savanna", "savanna", "forest", "jungle", "jungle"],
    ["desert", "desert", "desert", "desert", "desert"],
]
MIDDLE_BIOMES_VARIANT = [
    ["ice_spikes", None, "snowy_taiga", None, None],
    [None, None, None, None, "old_growth_pine_taiga"],
    ["sunflower_plains", None, None, "old_growth_birch_forest", None],
    [None, None, "plains", "sparse_jungle", "bamboo_jungle"],
    [None, None, None, None, None],
]
PLATEAU_BIOMES = [
    ["snowy_plains", "snowy_plains", "snowy_plains", "snowy_taiga", "snowy_taiga"],
    ["meadow", "meadow", "forest", "taiga", "old_growth_spruce_taiga"],
    ["meadow", "meadow", "meadow", "meadow", "pale_garden"],
    ["savanna_plateau", "savanna_plateau", "forest", "forest", "jungle"],
    ["badlands", "badlands", "badlands", "wooded_badlands", "wooded_badlands"],
]
PLATEAU_BIOMES_VARIANT = [
    ["ice_spikes", None, None, None, None],
    ["cherry_grove", None, "meadow", "meadow", "old_growth_pine_taiga"],
    ["cherry_grove", "cherry_grove", "forest", "birch_forest", None],
    [None, None, None, None, None],
    ["eroded_badlands", "eroded_badlands", None, None, None],
]
SHATTERED_BIOMES = [
    ["windswept_gravelly_hills", "windswept_gravelly_hills", "windswept_hills", "windswept_forest", "windswept_forest"],
    ["windswept_gravelly_hills", "windswept_gravelly_hills", "windswept_hills", "windswept_forest", "windswept_forest"],
    ["windswept_hills", "windswept_hills", "windswept_hills", "windswept_forest", "windswept_forest"],
    [None, None, None, None, None],
    [None, None, None, None, None],
]


def neg(w):
    return w[1] < 0.0  # weirdness.max() < 0L (quantized; max()<0 iff float<0)


class Builder:
    def __init__(self):
        self.out = []  # (t,h,c,e,w,biome)

    def add(self, t, h, c, e, w, biome):
        self.out.append((t, h, c, e, w, biome))

    # ---- pick helpers ----
    def pickMiddle(self, ti, hi, w):
        if neg(w):
            return MIDDLE_BIOMES[ti][hi]
        v = MIDDLE_BIOMES_VARIANT[ti][hi]
        return v if v is not None else MIDDLE_BIOMES[ti][hi]

    def pickBadlands(self, hi, w):
        if hi < 2:
            return "badlands" if neg(w) else "eroded_badlands"
        return "badlands" if hi < 3 else "wooded_badlands"

    def pickMiddleOrBadlandsIfHot(self, ti, hi, w):
        return self.pickBadlands(hi, w) if ti == 4 else self.pickMiddle(ti, hi, w)

    def pickMiddleOrBadlandsIfHotOrSlopeIfCold(self, ti, hi, w):
        return self.pickSlope(ti, hi, w) if ti == 0 else self.pickMiddleOrBadlandsIfHot(ti, hi, w)

    def maybeWindsweptSavanna(self, ti, hi, w, underlying):
        return "windswept_savanna" if (ti > 1 and hi < 4 and not neg(w)) else underlying

    def pickShatteredCoast(self, ti, hi, w):
        base = self.pickMiddle(ti, hi, w) if not neg(w) else self.pickBeach(ti, hi)
        return self.maybeWindsweptSavanna(ti, hi, w, base)

    def pickBeach(self, ti, hi):
        if ti == 0:
            return "snowy_beach"
        return "desert" if ti == 4 else "beach"

    def pickPlateau(self, ti, hi, w):
        if not neg(w):
            v = PLATEAU_BIOMES_VARIANT[ti][hi]
            if v is not None:
                return v
        return PLATEAU_BIOMES[ti][hi]

    def pickPeak(self, ti, hi, w):
        if ti <= 2:
            return "jagged_peaks" if neg(w) else "frozen_peaks"
        return "stony_peaks" if ti == 3 else self.pickBadlands(hi, w)

    def pickSlope(self, ti, hi, w):
        if ti >= 3:
            return self.pickPlateau(ti, hi, w)
        return "snowy_slopes" if hi <= 1 else "grove"

    def pickShattered(self, ti, hi, w):
        b = SHATTERED_BIOMES[ti][hi]
        return b if b is not None else self.pickMiddle(ti, hi, w)

    # ---- region builders ----
    def addOffCoast(self):
        self.add(FULL, FULL, mushroomFields, FULL, FULL, "mushroom_fields")
        for ti, t in enumerate(TEMPS):
            self.add(t, FULL, deepOcean, FULL, FULL, OCEANS[0][ti])
            self.add(t, FULL, ocean, FULL, FULL, OCEANS[1][ti])

    def addPeaks(self, w):
        for ti, t in enumerate(TEMPS):
            for hi, h in enumerate(HUMID):
                mid = self.pickMiddle(ti, hi, w)
                midBadHot = self.pickMiddleOrBadlandsIfHot(ti, hi, w)
                midBadHotSlopeCold = self.pickMiddleOrBadlandsIfHotOrSlopeIfCold(ti, hi, w)
                plateau = self.pickPlateau(ti, hi, w)
                shattered = self.pickShattered(ti, hi, w)
                shatteredWS = self.maybeWindsweptSavanna(ti, hi, w, shattered)
                peak = self.pickPeak(ti, hi, w)
                self.add(t, h, span(coast, farInland), EROS[0], w, peak)
                self.add(t, h, span(coast, nearInland), EROS[1], w, midBadHotSlopeCold)
                self.add(t, h, span(midInland, farInland), EROS[1], w, peak)
                self.add(t, h, span(coast, nearInland), span(EROS[2], EROS[3]), w, mid)
                self.add(t, h, span(midInland, farInland), EROS[2], w, plateau)
                self.add(t, h, midInland, EROS[3], w, midBadHot)
                self.add(t, h, farInland, EROS[3], w, plateau)
                self.add(t, h, span(coast, farInland), EROS[4], w, mid)
                self.add(t, h, span(coast, nearInland), EROS[5], w, shatteredWS)
                self.add(t, h, span(midInland, farInland), EROS[5], w, shattered)
                self.add(t, h, span(coast, farInland), EROS[6], w, mid)

    def addHighSlice(self, w):
        for ti, t in enumerate(TEMPS):
            for hi, h in enumerate(HUMID):
                mid = self.pickMiddle(ti, hi, w)
                midBadHot = self.pickMiddleOrBadlandsIfHot(ti, hi, w)
                midBadHotSlopeCold = self.pickMiddleOrBadlandsIfHotOrSlopeIfCold(ti, hi, w)
                plateau = self.pickPlateau(ti, hi, w)
                shattered = self.pickShattered(ti, hi, w)
                midWS = self.maybeWindsweptSavanna(ti, hi, w, mid)
                slope = self.pickSlope(ti, hi, w)
                peak = self.pickPeak(ti, hi, w)
                self.add(t, h, coast, span(EROS[0], EROS[1]), w, mid)
                self.add(t, h, nearInland, EROS[0], w, slope)
                self.add(t, h, span(midInland, farInland), EROS[0], w, peak)
                self.add(t, h, nearInland, EROS[1], w, midBadHotSlopeCold)
                self.add(t, h, span(midInland, farInland), EROS[1], w, slope)
                self.add(t, h, span(coast, nearInland), span(EROS[2], EROS[3]), w, mid)
                self.add(t, h, span(midInland, farInland), EROS[2], w, plateau)
                self.add(t, h, midInland, EROS[3], w, midBadHot)
                self.add(t, h, farInland, EROS[3], w, plateau)
                self.add(t, h, span(coast, farInland), EROS[4], w, mid)
                self.add(t, h, span(coast, nearInland), EROS[5], w, midWS)
                self.add(t, h, span(midInland, farInland), EROS[5], w, shattered)
                self.add(t, h, span(coast, farInland), EROS[6], w, mid)

    def addMidSlice(self, w):
        self.add(FULL, FULL, coast, span(EROS[0], EROS[2]), w, "stony_shore")
        self.add(span(TEMPS[1], TEMPS[2]), FULL, span(nearInland, farInland), EROS[6], w, "swamp")
        self.add(span(TEMPS[3], TEMPS[4]), FULL, span(nearInland, farInland), EROS[6], w, "mangrove_swamp")
        for ti, t in enumerate(TEMPS):
            for hi, h in enumerate(HUMID):
                mid = self.pickMiddle(ti, hi, w)
                midBadHot = self.pickMiddleOrBadlandsIfHot(ti, hi, w)
                midBadHotSlopeCold = self.pickMiddleOrBadlandsIfHotOrSlopeIfCold(ti, hi, w)
                shattered = self.pickShattered(ti, hi, w)
                plateau = self.pickPlateau(ti, hi, w)
                beach = self.pickBeach(ti, hi)
                midWS = self.maybeWindsweptSavanna(ti, hi, w, mid)
                shatteredCoast = self.pickShatteredCoast(ti, hi, w)
                slope = self.pickSlope(ti, hi, w)
                self.add(t, h, span(nearInland, farInland), EROS[0], w, slope)
                self.add(t, h, span(nearInland, midInland), EROS[1], w, midBadHotSlopeCold)
                self.add(t, h, farInland, EROS[1], w, slope if ti == 0 else plateau)
                self.add(t, h, nearInland, EROS[2], w, mid)
                self.add(t, h, midInland, EROS[2], w, midBadHot)
                self.add(t, h, farInland, EROS[2], w, plateau)
                self.add(t, h, span(coast, nearInland), EROS[3], w, mid)
                self.add(t, h, span(midInland, farInland), EROS[3], w, midBadHot)
                if w[1] < 0.0:
                    self.add(t, h, coast, EROS[4], w, beach)
                    self.add(t, h, span(nearInland, farInland), EROS[4], w, mid)
                else:
                    self.add(t, h, span(coast, farInland), EROS[4], w, mid)
                self.add(t, h, coast, EROS[5], w, shatteredCoast)
                self.add(t, h, nearInland, EROS[5], w, midWS)
                self.add(t, h, span(midInland, farInland), EROS[5], w, shattered)
                if w[1] < 0.0:
                    self.add(t, h, coast, EROS[6], w, beach)
                else:
                    self.add(t, h, coast, EROS[6], w, mid)
                if ti == 0:
                    self.add(t, h, span(nearInland, farInland), EROS[6], w, mid)

    def addLowSlice(self, w):
        self.add(FULL, FULL, coast, span(EROS[0], EROS[2]), w, "stony_shore")
        self.add(span(TEMPS[1], TEMPS[2]), FULL, span(nearInland, farInland), EROS[6], w, "swamp")
        self.add(span(TEMPS[3], TEMPS[4]), FULL, span(nearInland, farInland), EROS[6], w, "mangrove_swamp")
        for ti, t in enumerate(TEMPS):
            for hi, h in enumerate(HUMID):
                mid = self.pickMiddle(ti, hi, w)
                midBadHot = self.pickMiddleOrBadlandsIfHot(ti, hi, w)
                midBadHotSlopeCold = self.pickMiddleOrBadlandsIfHotOrSlopeIfCold(ti, hi, w)
                beach = self.pickBeach(ti, hi)
                midWS = self.maybeWindsweptSavanna(ti, hi, w, mid)
                shatteredCoast = self.pickShatteredCoast(ti, hi, w)
                self.add(t, h, nearInland, span(EROS[0], EROS[1]), w, midBadHot)
                self.add(t, h, span(midInland, farInland), span(EROS[0], EROS[1]), w, midBadHotSlopeCold)
                self.add(t, h, nearInland, span(EROS[2], EROS[3]), w, mid)
                self.add(t, h, span(midInland, farInland), span(EROS[2], EROS[3]), w, midBadHot)
                self.add(t, h, coast, span(EROS[3], EROS[4]), w, beach)
                self.add(t, h, span(nearInland, farInland), EROS[4], w, mid)
                self.add(t, h, coast, EROS[5], w, shatteredCoast)
                self.add(t, h, nearInland, EROS[5], w, midWS)
                self.add(t, h, span(midInland, farInland), EROS[5], w, mid)
                self.add(t, h, coast, EROS[6], w, beach)
                if ti == 0:
                    self.add(t, h, span(nearInland, farInland), EROS[6], w, mid)

    def addValleys(self, w):
        riv = "stony_shore" if w[1] < 0.0 else "frozen_river"
        self.add(FROZEN_RANGE, FULL, coast, span(EROS[0], EROS[1]), w, riv)
        riv2 = "stony_shore" if w[1] < 0.0 else "river"
        self.add(UNFROZEN_RANGE, FULL, coast, span(EROS[0], EROS[1]), w, riv2)
        self.add(FROZEN_RANGE, FULL, nearInland, span(EROS[0], EROS[1]), w, "frozen_river")
        self.add(UNFROZEN_RANGE, FULL, nearInland, span(EROS[0], EROS[1]), w, "river")
        self.add(FROZEN_RANGE, FULL, span(coast, farInland), span(EROS[2], EROS[5]), w, "frozen_river")
        self.add(UNFROZEN_RANGE, FULL, span(coast, farInland), span(EROS[2], EROS[5]), w, "river")
        self.add(FROZEN_RANGE, FULL, coast, EROS[6], w, "frozen_river")
        self.add(UNFROZEN_RANGE, FULL, coast, EROS[6], w, "river")
        self.add(span(TEMPS[1], TEMPS[2]), FULL, span(inland, farInland), EROS[6], w, "swamp")
        self.add(span(TEMPS[3], TEMPS[4]), FULL, span(inland, farInland), EROS[6], w, "mangrove_swamp")
        self.add(FROZEN_RANGE, FULL, span(inland, farInland), EROS[6], w, "frozen_river")
        for ti, t in enumerate(TEMPS):
            for hi, h in enumerate(HUMID):
                midBadHot = self.pickMiddleOrBadlandsIfHot(ti, hi, w)
                self.add(t, h, span(midInland, farInland), span(EROS[0], EROS[1]), w, midBadHot)

    def build(self):
        self.addOffCoast()
        slices = [
            (self.addMidSlice, (-1.0, -0.93333334)),
            (self.addHighSlice, (-0.93333334, -0.7666667)),
            (self.addPeaks, (-0.7666667, -0.56666666)),
            (self.addHighSlice, (-0.56666666, -0.4)),
            (self.addMidSlice, (-0.4, -0.26666668)),
            (self.addLowSlice, (-0.26666668, -0.05)),
            (self.addValleys, (-0.05, 0.05)),
            (self.addLowSlice, (0.05, 0.26666668)),
            (self.addMidSlice, (0.26666668, 0.4)),
            (self.addHighSlice, (0.4, 0.56666666)),
            (self.addPeaks, (0.56666666, 0.7666667)),
            (self.addHighSlice, (0.7666667, 0.93333334)),
            (self.addMidSlice, (0.93333334, 1.0)),
        ]
        for fn, w in slices:
            fn(w)
        return self.out


def build_param_list():
    return Builder().build()


if __name__ == "__main__":
    pts = build_param_list()
    from collections import Counter
    c = Counter(p[5] for p in pts)
    print(f"total param points: {len(pts)}, distinct biomes: {len(c)}")
    for b, n in sorted(c.items()):
        print(f"  {b:28s} {n}")
