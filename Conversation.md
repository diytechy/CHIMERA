Perform a deep review of "C:\Projects\ORIGEN2\.scripts\resolve_samplers.py" and create a plan to clean up, simplify, and consolidate functions and code where reasonable.  Also integrate the following changes:
1. The output file ("resolved_samplers.yml") should have repeated samplers defined as anchors, so they can subsequently be referred to using anchors in dependent samplers (not repeating samplers over and over again through different trees.)
2. Completely overwrite the "resolved_samplers.yml" only with samplers that are discovered through the sampler chain processing.

#####################################################

Add 5 parameters to customization.yml related to continental construction that describe:
1. What threshold the continental_sampler must be below for islands to appear.
2. What threshold the continental_sampler must exceed or standard continents to appear.
3. What threshold the continental_sampler must exceed for lakes to appear.
4. The maximum ratio that an island can have compared to the continental maximum (0 to 1)
5. The maximum ratio that a lake can have compared to the continental minimum (0 to 1)

Then in continents.yml, update the "continental_landmass" to incorporate the new parameters and output:
A 0 to 1 value for continents
0 to {maximum island ratio} for islands (when continents sampler value is below the island threshold)
0 to -1 for oceans
0 to -{maximum lake ratio} for lakes (when continents sampler value is above a the lake threshold)

###################################################

Try old constellation sampler:
        This gives interesting sampler bounds, more natural looking coasts and terrain properties.
          sampler:
            type: RIDGED
            lacunarity: 3
            gain: 0.45
            octaves: 4
            sampler:
              type: OPEN_SIMPLEX_2
              salt: 1
              frequency: 0.0002
        
        This gives an interesting distribution of continentals, and is useful for building out large ocean / land masses with internal island / lakes.
          sampler:
            type: FBM
            gain: 0.7
            octaves: 3
            lacunarity: 1.8121866
            sampler:
              type: PERLIN
              frequency: 0.0002

This looks pretty interesting:

type: EXPRESSION
expression: (continents(x, z))
samplers:
  continental_sampler: *continental_sampler
  continental_landmass: *continental_landmass
  spawnIsland: *spawnIsland
  continents: *continents

  ########################################

  Make a plan for a new python script called "OptomizePackSamplers.py" and performs the following actions to optimize pack samplers based  on C:\Projects\ORIGEN2\sampler-optimization-reference.md:
  1. Detects all pack level sampler definition files (from pack.yml, in the samplers section).
  2. Loops through each file, and -for each named sampler (and only named samplers, this should not affect variables) - removed any anchors, and keep the label noted.
  3. Loops through each file and for each alias to a named sampler, remove the alias and instead use the literal direction to the named sampler source (ex: "$math/samplers/elevation.yml:samplers.rawFlatness")
  4. If any pack sampler is used more than 3 times, child the original sampler under a CACHE sampler with an "exp: 2"
        
#######################################################
Finish elevation:
Plains can exist anywhere mountains are not?
Hills blend inversely to mountain mask

########################################################

Now when I have this in the elevation tab:

type: EXPRESSION
Expression: AppliedMountainHeight(x,z)

I see a console error in the NoiseTool:

Caused by: com.dfsek.tectonic.api.exception.ValueMissingException: Failed to load configuration:

	Configuration: Noise Config
	Message: Value "expression" was not found in the provided config: null
	Path: ..expression
	Full Path: 
		From configuration "Noise Config"
		In entry "."
		With type "EXPRESSION"
		In entry "expression"

	at com.dfsek.tectonic.api.loader.ConfigLoader.loadValue(ConfigLoader.java:177)
	at com.dfsek.tectonic.impl.loading.template.ReflectiveTemplateLoader.load(ReflectiveTemplateLoader.java:46)

It appears something broke with the mapped function names?  This is with the content of resolved_samplers.yml loaded into the common tab.

Note looking at resolved_samplers.yml I am seeing a considerable amount of duplicate samplers, instead of just having named samplers directly reused through the sampler chain.  This indicates another issue in resolve_samplers.py

########################################################################

Integrate river width variation
Integrate river boundary distance
  Add 3 parameters to customization.yml
  1. Nominal river boundary. (Value 25)
  2. River boundary variance magnitude (value 17).
  3. river-boundary-variance-period. (Value 50)
  Create a sampler in sampler/river.yml that is an expression sampler of the kind(river-nominal-boundary + Perlin * river-boundary-variance-magnitude), where the perlin sampler would have a frequency of 1/river-boundary-variance-period.
Update river type value based on distance from boundary
  
Update elevation herp function with river distance influence


Consider for mountain sampler:
sampler:
type: PERLIN
frequency: 0.001

Verify mountain mask
Build composite mountain mask A
Build composite mountain mask B
Verify canyon mask

Update elevation sampler with older elevation sampler?  Or do a comparison between the two to see where the details get exposed between the two.
Update mountains to use both kinds of mountains (Using opposite sides of the mountain mask)
Make sure all masks are also weighted / limited by the continental sampler.


################################################################33

Limit mountain / mesa mask based on river distance?

Change Mesa to use herp interpolation instead off current exponential.
Consider giving flat sampler an offset based on continental sampler.
Tune mountain mask for distribution across land-base.
Note also current elevation "Flatness" parameter might need to be removed, as it gives continental distribution very linear spreads, which aren't very natural.
Remove duplicate "lerp" function from applicable files, they should all reference the interpolation file.
Add land tag to all appropriate biomes
Add ocean tag to all appropriate biomes
Rename legacy sinkholes to rifts.
Make sure rifts avoid wide coasts, so form wide coasts near rivers
Make sure deep sinks avoid rivers (Take inner land, and remove anything in boundary range of rivers)
Make sure rifts are 
Add sinkholes?  Or how will those avoid rivers?  Only through border / land type biome filtering?

Now that "resolved_samplers.yml" has been built, make a plan to create another python script that performs the following:

- Detects identical samplers that are used more than 3 times.
that runs against the resolved_samplers.yml

Issues: Should mesas have so much detail on top?  Should they be flatter?


Review "resolved_samplers.yml" and identify all samplers

Terrain construction:
 - Blend plains and continental contribution using... mask?
 - Add mountains and hills.
 - Is flatness really necessary?
 - Overlay mesas


Now let's perform a deep
 
 Current issues:

 Missing rivers entirely
 Mesas are dominating, an issue in distribution with the current mask
 Sinkholes are getting dropped into places they shouldn't :
  - like the ocean.
  - And rifts / wells, it's probably easier for rifts / wells to avoid generation near spots.

  How to get spots to avoid rivers?  Or... viceversa?  Not sure how to.

  Noise potentially is sometimes causing rivers to get lost / scrambled.

How to validate spots are in range of river such that they get suppressed?  Query distance at cell center?  If distance is less than greatest distance, then... I guess switch them back to what they were before?

0. Update pre-river elevation to omit spots.  This means there must be continents / elevation before spots, then river eval, and then spot integration.

Formulate for spots only:
Spots -> continentalRise -> continentalRise(x,z) * (1-flatness(x, z)) -> rawElevation(x, z) * if(factorContinental, herp(continents(x, z), continentZero, 0, continentFull, 1), 1)

Using the sampler blotSpots, update the elevation sampler "elevationFromSpots" to contain the expression:

{Apply continentalRise expression to blotSpots(x,z)}* (1-flatness(x, z))

Then apply the same herp function to this outcome:

 if(factorContinental, herp(continents(x, z), continentZero, 0, continentFull, 1), 1)

Then take max of this elevation compared with current elevation, then lay in rivers.

Note then this is only elevation due to spots.

A. Need to suppress sinkholes when:

Their center is in range of river
Their center is below continental value (because why would you have sinkholes in the middle of the ocean?  Maybe I need to see what these actually look like but it seems very silly to have them there.)

IMPORTANT: Scale appears to be causing issues now, as it is applied inconsistently, and this interferes with resolving spot locations on continents / rivers.  Likely just need to remove entirely.  Can just increase frequency of sampler.

###########################################

Fixes post spot dist:

- Prevent river generation in ocean spots?  (Both biome dist and elevation change)
  If continental < x, river distances should be past herp distance?  Just set to hard-coded value?

  #########################################


- Update wells to use simpler sampler methods instead of concurrent replacements
- Update rifts to use simpler sampler methods instead of concurrent replacements
- Update optimization py script to also cache samplers whose samplers are used in biome dist, also ignore DENDRY type samplers and their users since those are inherently cached.'
- Could set island types according to continental landmass being above the island threshold...



B. Need to make sure rivers can go over all terrain for continuity?  Need to utilize "land" tag?

C. Need to make sure rivers actually flow up using soul-sand?

D. Need to add all original minecraft biome labels?

E. Verify mesa placement for regions, and consider plains region designation.

F. Fix biome table calculator, use distribution at stages to actually assert distribution per stage.  Can utilize resolved samplers?

G. Increase ore spawn rate via standard ore distributions.

H. Don't have direct biome boundaries on temperature / precipitation.  Use cellular evaluation at center to place.

I. 


Ocean is Mesa

Cells for spot regions (already present)


Cells for Mesa region biomes
Cells for large landmass biomes
Cells for Mainland / island biomes
Cells for Highlight biomes
Cells for Ocean biomes

Merge wells to become a spot type?  Or merge them to become something that comes with rifts.
Make sure rifts do have appropriate boundary from spots.

Both wells and rifts should evaluate for distance to river and distance to spot within their cell zone centers before placing, this is on top of replacement filtering.

Then domain warp could be applied to rifts again?

Well should have warp applied.

Note wells also need to be fixed so they are broken apart by temperature region, likely an issue in the distribution using duplicate labels in the YAML.

The can continue with mesa region

Then island region

Then biome dispursement

Then

Create a plan to update the "calculate_biome_percentages.py" in C:\Projects\ORIGEN2\ to correctly calculate final biome distributions from expressions and known starting distributions, as it appears what exists today may be using multiple inferences / estimates.

At the top of this file "calculate_biome_percentages.py" record the requirements to the best of your ability based on this prompt and current implementation of the file.

The may require significant refactoring.

Use C:\Projects\Terra and C:\Projects\Tectonic as necessary to have a good understanding of the biome distribution pipeline when redesigning this script.

The pack that is being computed is currently in "C:\Projects\ORIGEN2"

IMPORTANT: Base sampler distributions can be estimated from picture snapshots in "C:\Projects\NoiseTool\Distribution_Ref", where "p25" indicates the upper range of that particular distribution is 0.25.  Since base sampler distribution is critical for accurate results, it may make sense to have a csv / yml or similar configuration describing the the distribution of each base samplers.  (Ex: Just a 2-d interpolated function that expression percentage of hit as a function of input for each base sampler)

There should be minimal "magic" strings or values in this script, ex: "PRECIPITATION_BANDS = ['desert', 'desertBorder'" is identifying implementation specific breaks in the precipitation stage filter, but that isn't guaranteed to stay consistent.

Make sure all magic / key identifiers that are truly necessary are near the top of the file for clarity that the script is looking for implementation specific identifiers that may cause it not to work with some packs.

There are only 3 "named" samplers that need to be tracked during biome distribution, as those need to be populated finally in the biome table: "temperature", "precipitation", and "elevation".  If a biome is not distributed with these measures, the average value of those individual samplers should be used in the final biome table output.

Each biome distribution refers to an inline or base sampler, and that base sampler has either an inherent distribution, or it's distribution can be computed from the expression.  So for each biome distribution stage, the script should:

1. Calculate the distribution of the sampler or expression from -1 to 1.

2. Based on the number of biomes to distribute to, replicate the calculations of Terra / Tectonic to determine what values between -1 and 1 will be used to map regions of the distribution to their newly mapped biome values.  (Ex: If the "to" section includes 2 biomes (BiomeA and BiomeB), then the -1 to 1 assumed region will be broken into 2 equal parts, from -1 to 0, and 0 to 1.  If the sampler is symmetric, this would result in 50% to BiomeA and 50% to BiomeB.  However, if the sampler were something non-symmetric, like "CELLULAR", that same configuration may result in BiomeA receiving 90% and BiomeB receiving 10%).  Note any returned value beyond the -1 to 1 limits are just clamped.

The "resolved_samplers.yml" already breaks down the individual samplers, and may be useful in the process so that sampler hierarchy and linking chain does not need to be performed as a part of "calculate_biome_percentages.py", it may already be implemented that way.

Note "SMOOTH" and "FRACTAL_EXPAND" samplers I assume will not affect distribution percentages.

Note some distribution evaluations may be very difficult given resolution of some of the sampler expressions.  The 
"BORDER" and "BORDER_LIST" may require special treatment, see if you can find how those distribute a distribution, but for those it may be necessary to track distribution in different categories.  For instance, the river sampler (using DENDRY noise) is a highly complex filter without a clear distribution.  It may be necessary to indicate for certain categories what their distribution is within the category.

I would recommend a category for distribution branch as "SURFACE", "RIVER", "COAST", "SUBSURFACE", which will need special rules / magic values to identify when these distribution stages are occurring.

The initial spot placer in ExploreTest.yml may also be difficult to assess as it is dependent on river sampling.  For this it may be simpler to set that initial distribution according to a special rule (again - defined at the top of the py file for clarity / uniqueness) where the probability of a spot above land is the area of the average spot radius divided by the area of the entire cell (based on frequency config) multiplied by some river survival rate of 70%

Radius based distribution based on cellular noise may also need special consideration.  As the distribution of a value would also be based on the cellular frequency (cell to cell frequency.)
