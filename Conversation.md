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

#####################################################

use single cellular mixture for both rifts and wells.

Use cell value at temperature to break cells into cold / warm cell regions.

Use white noise to break each of those into cold rifts / cold wells / return to land.



- Update wells to use simpler sampler methods instead of concurrent replacements
- Update rifts to use simpler sampler methods instead of concurrent replacements
- Update optimization py script to also cache samplers whose samplers are used in biome dist, also ignore DENDRY type samplers and their users since those are inherently cached.'

###################################################################3

Set islands, mesas, vast forests, deserts.

IMPORTANT - How does desert probability get placed vs forest in terms of precipitation and temperature?  Need to crosscheck climate distribution fields first.  Maybe just select placement first as a large region, and then populate later... but needs to be in the correct region first so that won't work, need to review climate dist first.

Order:
1. Islands
2. Mesa
3. Deserts and Vast Forests

#########################################

Now build out formal climate using biome cells?

New issue: How to handle coasts?

- Could split from biomes - more consistent, but also less variation.

- Probably still the right direction.

- How to split between ocean-like "coast" properties and non-ocean?

- How to prevent artifacts due to FRACTAL_EXPAND, is that even necessary? Maybe that should be done before replacing coastlines with specific biomes?


- Could set island types according to continental landmass being above the island threshold...



########################################3

Sea arches sometimes stop abruptly, can they just be placed using cellular approach to ensure a full "arch"/

It makes sense to fill coasts before rivers since that will be a larger effective change, and coasts don't really need to have a transition to rivers anyways.


F. Fix biome table calculator, use distribution at stages to actually assert distribution per stage.  Can utilize resolved samplers?

########################################

Really - Need to see what sea archs look like.  If they are immersed in water, they should get placed in ocean.  If not, they should get placed as normal coast, but I'm quite sure they are water in nature.


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

Minecraft biome IDs are missing
########################################

Add archipelagos
NOTE: Sea arches do come out from sea... so need to change this sampling.

################################

Script fixes:
Distribution is definitely not working (% wise)

Need to fix spot elevation?  Or maybe this isn't really possible?  This would make it much easier to drop spot related comps from mesa.  How does this affect other spot definitions?  Does it affect them at all?  What about volcano regions?

Now for any equation expressions in the following list (each corresponds to a file, for example a single file "eq_alpha_mountains.yml" contains "id: EQ_ALPHA_MOUNTAINS" which relates to the entry below "EQ_ALPHA_MOUNTAINS").  If they contain the terrain sampler expression "-y + base", and base is set to (terrain-base-y-level or legacy-terrain-base-y-level), change the expression from "-y + base" to "-y+base+BiomeShapeLandmassBaseOffset(x,z)" similar to what has already been done in "eq_alpha_mountains.yml".
 
Biomes:
EQ_ALPHA_MOUNTAINS <- Already modified.
EQ_ERODED_MOUNTAINS
EQ_ERODED_VALLEY_MOUNTAINS
EQ_GLACIAL_OVERHANGS
EQ_HILLS
EQ_LOWLAND_HILLS
EQ_MOUNTAIN_SPOTS
EQ_PILLARS
EQ_SMALL_MOUNTAINS
EQ_SNOWDRIFT_COASTS
EQ_TERRACED_MOUNTAINS
EQ_TERRACE_MOUNTAINS
EQ_TILTED_PLATEAU

Plane-like (Moderate to dry)
EQ_PLAINS 
EQ_FLAT_BUMPY
EQ_FLAT_ERODED
EQ_CRACKED_FLATS
EQ_BUTTES

Wetlands / lowlands / plain-like / coastal (Precipitous)
EQ_BOG
EQ_WARPED_WETLANDS
EQ_SWAMP
EQ_MANGROVE_SWAMP
EQ_CELL_MARSH

Need bump? =>

Now for all wetland like biomes below, add an "ocean" definition with a 
ocean:
  level: $meta.yml:ocean-level
  # Water level varies ±3 blocks with regional terrain elevation so that the river
  # surface follows the landscape gradient rather than sitting at a fixed Y.
  sampler:
    dimensions: 2
    type: EXPRESSION
    variables:
      offset: 3
      ocean_base: $customization:terrain-ocean-base-y-level
    expression: min(BiomeShapeLandmassBaseOffset(x, z) - offset,ocean_base)

######################################3

Outcomme testing:

MUSKEG shows below limit, lift base
FROSTCOATED_BOG
  should likely not allow carving.
  Allow cell elevation based raise
  Double-check ocean level

Given open pond sections, variable water height ponds will look very very strange.  Will now plan to place swamp-like biomes only at the edge of continents, and not dynamically affect water flow.

Thus to-do is:

1. Revert all low-lying biomes that contain water (remove elevation offset).
2. 

positiveWhiteNoise is getting removed incorrectly by OptimizePackSamplers.py

Two things, to evaluate variable water placement:

1. Roll cellular elevation of plain-like biomes up near border?  But this might still give discontinuities at borders?  At least it doesn't give floating water that is blocked by stone which looks very strange.
2. How 

-


No change required:
EQ_BUTTES_ARCHIPELAGO (In water)
EQ_CANYON (Canyon)
EQ_CARVING_OCEAN (Ocean)
EQ_OCEAN_DEEP (Ocean)
EQ_OCEAN_SHALLOW (Ocean)

EQ_CARVING_LAND (Highly complext, would be very hard to mitigate?)
EQ_CHASMS (Purposeful chasm, should be rare?)

RIVER:
EQ_TERRACED_MOUNTAINS_RIVER
EQ_RIVER

#############################################

I would like to prepare to integrate remaining biomes into the CHIMERA pack that are from other packs, but to do this I need to pull respective unplaced biome into an appropriate location.

Create a list of all biomes in the current BiomeTable.csv that are currently 0% in CHIMERA and for each biome make a recommendation for how to insert them into CHIMERA:

1. If they appear to be a generic biome (biome names like "Variant" and "LAND_" and "COAST_") and thus should not be placed.
2. If they are apart of a special biome that hasn't been completed yet (like "sinkhole" or "crater_lake")
3. If they appear to be coastal biome (name like "beach", "coast", or are referenced in fill_coasts.yml.
4. If they appear to be oceanic biomes, which will be addressed later.
5. If they appear to be a biome that would border a river (eg: CHILLY_CREEKS), as they may need special treatment.
5. Otherwise, what category they should go into in "Set_biomes_in_climates_origen.yml", considering their terrain sampler base height (which corresponds to flat or highland regions)

Note: Hydraxia based biomes are always cold-climate.  "C:\Projects\origen" contains the original origen pack, "C:\Projects\Hydraxia2" contains the updated Hydraxia pack, and "C:\Projects\TerraOverworldConfig" contains the current Terra overworld config, these  may all be useful references.

######## Will need to remove all coastal definitions from set, since that should be done as a part of a replacement stage.  Probably best to do it at the same time as the rivers?

1. Remove all coastal definitions, 


For flat biomes / those that aren't influenced by elevation, could just herp in river elevation for continuity.  By far the easiest option.

##############

Now create a list of all biomes in BiomeTable.csv that have the following properties:
 1. that are of a land type (origin)
 2. are not rivers (indicated in extends or river column)
 3. That are not wetland types (extends includes BOG, WETLANDS, SWAMP, MARSH)
 
And for each biome, determine what sort of coast they should have and list both the biome and the corresponding coast in a separate document for review:

If they have a direct coastal match (Usually the biome ID followed by _COAST, ex: ARID_PALE_GARDEN -> ARID_PALE_GARDEN_COAST), that should always be used.

If there is not a direct match, estimate the coastal catagory to assocciate based on how the biome is set in "set_biomes_in_climates_origen.yml", consider averaging if the biome crosses multiple regions, knowing the climate chain that leads to this (temperature -> precipitation -> elevation)
arid-coast-flat
arid-coast-highlands
boreal-coast-flat
boreal-coast-highlands
polar-coast-flat
polar-coast-highlands
temperate-coast-flat
temperate-coast-highlands
tropical-coast-flat
tropical-coast-highlands

Note, the following appear to be biome specific coasts, but there may be others:
- ARID_PALE_GARDEN_COAST
- ORANGE_ARID_PALE_GARDEN_COAST
- PALE_GARDEN_COAST
- POLAR_PALE_GARDEN_COAST
- RED_ARID_PALE_GARDEN_COAST
- POLAR_MUSHROOM_COAST
- MUSHROOM_COAST
- POLAR_MUSHROOM_COAST


######################################################


Now create a list of all biomes in BiomeTable.csv that have the following properties:
 1. that are of a land type (origin) or archipelago
 2. are not rivers (indicated in extends or river column)
 3. That don't already have a river replacement tag defined (Can be determined by seeing a field / text in the "river" column of the csv table)
 
And for each biome, determine what river biome or river tag they should have and list both the biome and the corresponding river in a separate document for review:

If they have a direct river match (Usually the biome ID followed by _RIVER, ex: ARID_PALE_GARDEN -> ARID_PALE_GARDEN_RIVER), that should always be used.

If there is not a direct match, estimate the river tag to associate based on how the biome is set in "set_biomes_in_climates_origen.yml", consider averaging if the biome crosses multiple regions, knowing the climate chain that leads to this (temperature -> precipitation -> elevation)

Putting a high preference on temperature

River  tags can be referenced in "add_rivers.yml"

I will review this final list of Biomes and their prospective river biomes / river tags for accuracy before updating the respective files.


Make sure vanilla ID types (ocean / land) correctly correlate to CHIMERA biome type.

Fix Mesas  - Need to have a non-spot biome definition for mesa?  Or just make sure they all follow the same elevation definition?  Could just fix elevation composition here.

Marshes / Plains
  - Plains should follow the plain definition format - Maybe this should be based on flatness parameter.
  - 
  - Important - Elevation is used to build a filtered value, compared to sampler 3d.  However, since they are additive, elevation still lifts the sampler 3d.
  - Marshes should also be permitted to be elevated, and contain a higher water edge value.

Should all base elevation come from core elevation function?  Need to update all biomes to have the same base elevation.  In theory should not need to blend.

  - Update all land biomes to have a relevant river replacement tag.
  - Update all land biomes to have a base elevation from... real life elevation?
  - Update all water biomes to have base elevation from lowest maybe but this doesn't matter as much.

RIVERS:
ADD "ocean.sampler" definition to biome to propagate water height down-push.
ADD "decoration" to perform soul-sand placement at elevation changes?
How to push sampling up for palette as elevation changes?  To ensure expected basin fill.


1. Change sea arches to be cellular only near coast but replace from ocean.
2. Update for river replacement to include coast-line replacement first.

Note: Still need to investigate.... something.

B. Need to make sure rivers can go over all terrain for continuity?  Need to utilize "land" tag?



Then island region

Then biome dispursement

Then

---

# CHIMERA Pack - 0% Biomes Integration Analysis (March 3, 2026)

## Summary
Analyzed all **138 biomes** currently at 0% distribution in CHIMERA and categorized them by integration strategy.

**Analysis Documents Created:**
1. [CHIMERA_UNPLACED_BIOMES_ANALYSIS.md](CHIMERA_UNPLACED_BIOMES_ANALYSIS.md) - High-level categorization and strategy
2. [CHIMERA_UNPLACED_BIOMES_DETAILED_REFERENCE.md](CHIMERA_UNPLACED_BIOMES_DETAILED_REFERENCE.md) - Complete biome-by-biome reference table

## Distribution by Category

| Category | Count | Action |
|----------|-------|--------|
| Generic Placeholders (do not place) | 29 | Skip entirely |
| Special Features (incomplete) | 7 | Wait for crater lake/sinkhole system |
| Coastal Biomes | 19 | Add to `fill_coasts.yml` |
| Oceanic (trenches/vents) | 21 | Add to ocean sections in `set_biomes_in_climates_origen.yml` |
| River-Bordering (mostly Hydraxia) | 34 | Integrate Hydraxia to cold climates + river variants |
| Subsurface/Caverns | 12 | Already handled in subsurface config |
| Other/Specialized | 28 | Add to appropriate climate categories |

## Key Findings

### 1. Hydraxia Biomes (18 unique biomes)
All Hydraxia-based biomes (marked by `BASE_HYDRAXIA` in Extends field) are **COLD CLIMATE** and should be placed in:
- boreal-snowy-flat/highlands
- boreal-cold-flat/highlands  
- boreal-warm-dry (some variants)

Examples: BIRCH_WOODLANDS, MAPLE_WOODLANDS, SAKURA_WOODLANDS, etc.

### 2. Pale Garden Variants (6 biomes)
Special vast-forest placeholders that need integration:
- ARID_PALE_GARDEN (hot/warm climate)
- ORANGE_ARID_PALE_GARDEN (hot/warm climate)
- POLAR_PALE_GARDEN (cold/polar climate)
- RED_ARID_PALE_GARDEN (hot/warm climate)
- PALE_GARDEN (boreal/temperate)
- Plus 3 coast variants

### 3. Subtropical Open Water (9 biomes)
NEW ocean temperature zone not yet present:
- SUBTROPICAL_OCEAN (and variants: overhangs, slopes, trenches)
- SUBTROPICAL_DEEP_OCEAN (and vents/trenches)
- SUBTROPICAL_DEEP_DEPTHS
- These may require adding new subtropical ocean categories to `set_biomes_in_climates_origen.yml`

### 4. River-Bordering Complications
34 biomes have river connections or dependencies:
- Many are Hydraxia woodlands that border rivers
- Some are special river features (CHILLY_CREEKS, DRAFTY_STREAMS)
- Some are pale garden river variants
- Some need integration into existing river systems

## Integration Priority

### HIGH (Implement First)
1. Coastal biomes → `fill_coasts.yml` (straightforward temperature-based)
2. Hydraxia biomes → `set_biomes_in_climates_origen.yml` cold sections

### MEDIUM (Implement Second)
1. Ocean biomes → Ocean sections in `set_biomes_in_climates_origen.yml`
2. River variants → River biome sections
3. Specialized biomes → Appropriate climate regions

### LOW (Later)
1. Special features → Revisit when crater lake/sinkhole systems complete
2. Generic placeholders → Ignore entirely

## Notes for Implementation

1. **Elevation Always 0.5** - All 138 biomes have elevation=0.5, suggesting they all fit in "flat" regions of their climates. Verify this assumption against actual biome definitions.

2. **Source Distribution** - Most are "surface" source; 13 are "extrusion" (subsurface). Extrusion biomes should not appear in this analysis (likely already handled).

3. **Temperature Clues** - Biome names provide climate hints:
   - COLD/FROZEN/SNOWY/BOREAL/ARCTIC/POLAR → Cold climate
   - HOT/TROPICAL/WARM/DESERT → Hot/warm climate
   - TEMPERATE/FOREST → Temperate climate

4. **Hydraxia Override** - If Extends contains `BASE_HYDRAXIA`, biome is ALWAYS cold, regardless of name.

5. **River Values** - Biomes with non-empty "River" column or river-related names need special handling similar to existing river biomes in CHIMERA.

#########################################################
NEXT:

A: Make sure all bogs / wetlands do not have land carving enabled.

Remove "EQ_CARVING_LAND" from all biomes that also have any properties that appear to be wetlands / lowlands / plain-like / coastal, which can be identified by any biome having any of the following extends:
EQ_BOG
EQ_WARPED_WETLANDS
EQ_SWAMP
EQ_MANGROVE_SWAMP
EQ_CELL_MARSH

B. Need to make sure river support builds out under variable height river.

#Drafted under continentalRiverSupportDensity

- Reduce support / contain water funciton by 1.
- Somehow need to perform errosion much closer to river, but not clear what's currently causing errosion.  Detailed elevation function?  Filtering on top of it?
- 

C. Need to make sure rivers actually flow up using soul-sand?

ocean:
  level: $meta.yml:ocean-level
  # Water level varies ±3 blocks with regional terrain elevation so that the river
  # surface follows the landscape gradient rather than sitting at a fixed Y.
  sampler:
    dimensions: 2
    type: EXPRESSION
    variables:
      base: $meta.yml:ocean-level
    expression: base + elevation(x, z) * 3


Land carving still seems aggressive

Definitely not getting consistent river gen... not seeing any branches, not seeing interconnected lvl 0,  Maybe issue with tags not replacing for river biomes?

Rivers go in and then just... stop.  Might be issue with density override function, issue with river branching computations, or issue with something else????

Theory:
1. MinDensity function isn't raising terrain because the sampler is not actually multiplied by the terrain scaler (effectively always 0)
2. River erosion... might be working for L0, but not clear why it's not working for L1+, maybe a different function getting referenced?

D. Need to add all original minecraft biome labels?

E. Verify mesa placement for regions, and consider plains region designation.


G. Increase ore spawn rate via standard ore distributions.

H. Don't have direct biome boundaries on temperature / precipitation.  Use cellular evaluation at center to place.

I. 