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

It looks like there are still some land biomes that do not have coastal tags.  Create a list of all biomes in BiomeTable.csv that have the following properties:
 1. that are of a land type (origin)
 2. are not rivers (indicated in extends or river column)
 3. That are not wetland types (extends includes BOG, WETLANDS, SWAMP, MARSH)
 4. Are not themselves coasts (Set in a "to" section of "add_coasts.yml")
 
And for each biome, determine what sort of coast they should have and list both the biome and the corresponding coast in a separate document for review:

If they have a direct coastal match (Usually the biome ID followed by _COAST, ex: ARID_PALE_GARDEN -> ARID_PALE_GARDEN_COAST), that should always be used.

If there is not a direct match, estimate the coastal category to associate based on how the biome is set in "set_biomes_in_climates_origen.yml", consider averaging if the biome crosses multiple regions, knowing the climate chain that leads to this (temperature -> precipitation -> elevation)
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

Note any biomes including "PALE_GARDEN" and "MUSHROOM" can be ignored since they have biome specific replacement in "add_coast.yml"

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

Sinkholes don't appear to be working?  Don't go down far enough to fill?

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

#########################

Latest test:
Rivers are rising better / more tightly, but two issues:
1. Coast is not smooth compared to previous appearance (transition issues), might need to put max on target height density, it might be herping up to max elev due to river sampler response?
2. Rivers are intersecting ocean, might be due to previous filtering.

Misc:
3. Oak Forest / Broadleaf Forest / Timberland... none appear to have coastal replacement?

Sakura Streams

Next:
Complete features\world_features\river_soulsand.yml
Fix river sampler to give more smooth transition, maybe expands size.
Rivers should allow all subsurface caves
Still confused about that vine fault showing up.
Icy incision didn't seem to work?

B. Need to make sure river support builds out under variable height river.


###########################

Correct Hydraxia related:

Replace the current river tags with USE_FROSTBITE_RIVERS for the following biomes:
	FROZEN_SPIRES
	SEARING_TORS
	ARCTIC_MESA
	PERMAFROST_CLIFFS
	
Replace the current river tags with USE_CHILLY_CREEK_RIVER for the following biomes:
	SUGAR_PINE_WOODLANDS
	REDWOOD_WOODLANDS
	ICEBOUND_JUNGLE

All other biomes with BASE_HYDRAXIA in name and already has a river tag that is not USE_CHILLY_CREEK_RIVER or USE_FROSTBITE_RIVERS, replace the current river tag with:
USE_DRAFTY_STREAM_RIVER

##########################################################

I want to merge all the extrusion stages into a single large stage 

SOULSAND placement is broken?  <- Need to see if this is due to distributor?



Create a script that for each river biome (biome extends "EQ_GLOBAL_RIVER") if it does not have a "features" section, copy it into the respective biome file from the first "extends" entry that does have a "features" section, and then add postprocessor (or add to the existing postprocessor field) with the following information:
  postprocessors:
  - RIVER_SOULSAND

  ################################################

Note that "eq_rivers_global.ymlo" has the original river equation the sets river height.  I have attempted to modify this in "biomes\abstract\terrain\land\eq_global_river.yml", and while the general average height does appear to increase near the outside of the river terrain heigght, the bed height is NOT increasing (I would expect them to increase together), and the elevation near the edge where the river actually is present (river distance = 0) there is a very aggressive drop off instead of a smooth roll into the river and down to the riverbed.  Using "C:\Projects\Terra\TerrainGenerationPipeline.md" for reference, can you design updates to the current eq_global_river.yml file so that it is more smooth rolling to the edge of the river edge (which is achieved in the original river equation), but also so that the river height raises (continentalRiverBlockElevChange is the raise in river height), and that the river is more narrow (Restricted with continentalRiverBlockDist).

It might make sense to just set elevation to the river height offset to get the terrain height to the right position and then carve the actual river bed after that.

#Drafted under continentalRiverSupportDensity

- Reduce support / contain water funciton by 1.
- Somehow need to perform errosion much closer to river, but not clear what's currently causing errosion.  Detailed elevation function?  Filtering on top of it?


Plan some more refactoring here.

1. The ceiling erosion looks okay.
2. Erosion to the river bed is still needed, it should not have been removed.  The delta height gives the distance down to the river bank, but further erosion is necessary no matter what to erode empty space for the river to flow in.
3. Break the expression further apart, erosion should occur in two different ways based on if the river is enclosed or not:
A. Determine if the river is enclosed based on it's delta.  If delta>(20-20*River Dist {so a range from 20 to 40}), then the river can be considered enclosed.  (There is a lot of material above the river that can be retained in a ceiling)
B. When enclosed, the erode function should work the same way it does today for the ceiling, but only up until the rivers edge (RiverDist<0>), and the river bed should have an elliptical-like rolloff that rolls up to the edge off the enclosed cave wall.  (1 - (RiverDist+1)^2)*MaxBedDepth
C. When not enclosed, the ceiling wouldn't exist at all, and instead all blocks above the bed height should be herped from some river distance (RiverDist = -0.6) to the river edge (RiverDist = -0.2), and continue to create cavities down to the river bank through the entire height.
D. There should be no magic numbers in the functions or expressions, they should all be named variables for easy tuning, but comments should be substantial to relay context given the complexity of this sampler.

Theory:
1. MinDensity function isn't raising terrain because the sampler is not actually multiplied by the terrain scaler (effectively always 0)
2. River erosion... might be working for L0, but not clear why it's not working for L1+, maybe a different function getting referenced?


#################################################

Strange artifacts at VERDANT_RIVER <- Likely due to a different river equation.
  - Need to update all rivers to use global river equation.

-873, -7 <- Floating amethyst in sky
	CRYSTALLINE_CAVERNS is causing this artifact
  - Need to see what is driving creation of these structures.

Need to resolve subsurface biomes mixing?  Not clear why this... likely due to sampler lookup issue.
  - Check cellular lookup, can be verified without rerunning mc.

Might need to do some smoothing to mitigate some artifacts, but rivers are starting to look solid.
  - 


D. Need to add all original minecraft biome labels?

E. Verify mesa placement for regions, and consider plains region designation.


G. Increase ore spawn rate via standard ore distributions.

H. Need to update river samplers to use global eq or reference parent func with new global.... or redesign global.  Haven't confirmed it's functionality yet.

I. 

Coordinates to check:

-95, -218 <- Appears to be river, but is just sand... river not eroded enough?
-250, -270 <- Edge of river in ocean, why wasn't elevation dropped to 0?

-463, -444 <- What's happening here that's causing floating part above river?
caverns:

Issue is verdent river?

#########################

What's happening at -1119, 27?  It looks like land mass is covering the river.
What's happening at -1076, 145?  Rivers banks are vertical?

3 fixes:

Make sure height above bank is knocked out?  Might not be occurring?
Add 4 bit level to river dendry output.
Add 4 bit distance to increase in quantized elevation.

##############################################

Break out 3 cavities to named sampler:
  River bed - Include bed height as function of river level.
  Enclosed river - Include river distance as a driver of total arc height.
  Unenclosed river - Should just be straight down to elevation?  Or maybe herp the outside to the elevation profile?
Still no grow litchen
Still reduce shroomlight freq
Should I remove frozen fungi from standard dist?  Isn't that just for islands?
Sakura streams shouldn't be in colder regions

In eq_global_river take the high level sampler (terrain.sampler) out to make it a pack samplers in math\samplers\rivers.yml.  Variables should be moved as needed so that they are all sourced from rivers.yml.

The intent is to break this large expression up into smaller more manageable pieces.

Move out the following functions / samplers to instead be pack level samplers:

erosionStrengthVariation
openings
ceilingSpikes
depthVariation
cavity
enclosedCavity
caveCeiling
surfaceOpenings
bedDepth
terrain.sampler should then exist in rivers.yml as an expression that is using the other broken out pack samplers.

It looks like some of the functions are still embedded into large hard-to-read samplers.  Please make sure all the following are base level samplers, this will likely require variables to all be at the top of rivers.yml, and referenced wither as a whole structure, or individual parameters as needed via anchoring, refactor other samplers as needed:

erosionStrengthVariation
openings
ceilingSpikes
depthVariation
cavity
enclosedCavity
caveCeiling
surfaceOpenings
bedDepth

#############################

Create a plan to reorganize the river sampler equation (riverTerrainSampler) into upper and lower portions, similar to the structure in RiverSamplerAlt.ymlo.  This is basically already complete, I just want it to be explicit in the sampler.

This way any y above bank level can evaluate the upper half computation, and anything else should evaluate as the riverbed erosion.

I would expect the final riverTerrainSampler to be built of effectively 3 components:
  - If y is less than or equal to the river bank height, use erosion based on the river bed.
  - If y is more than the river bank height and the river is enclosed, use the sampler / function for the enclosed river.
  - If y is more than the river bank height and the river is not enclosed, formulate the sampler to give a final density that generates blocks that herp from the detailed elevation at the riverBiomeActivationThreshold down to the bank height at riverBiomeActivationThreshold/2.

3 Fixes:

1. Transition distance and setting soulsand
2. Soulsand getting laid in strips, should be diamond pattern
3. Banks of river going to heaven... not intended.

###################################

How can I stop water blocks from merging but allow user to pass through?
Make forests smaller
Reduce bed height and variability at lower levels.

CORE PROBLEM: Blue Concrete identifies locations with a single block above?  What if neighboring blocks have two higher level water blocks that combine?  Those won't be detected?  Or is the likelihood of this basically non-existent?

Make sure rivers only rise in highlands (not lowland regions?)

#########################

For the next update, I want to prevent water from flowing at the water surface above soul sand or blue concrete (if soulsand has not been placed yet.)  I think the trigger can work similarly for newly generated chunks as well as loading chunks that already exist:

Upon chunk generation, replace both the blue concrete with soul-sand, but also place a barrier block below it, this way the pattern will be uniquely identifiable in future chunk loads compared to user placed soul-sand blocks.  When the blue concrete is found, this can also be identified as a column where a bubble column exists (x,z coordinates) when a chunk is freshly created.

Upon chunk loading, also search using the same pattern as used in chunk generation, but now look for a barrier block first, followed by soulsand above.  This identifies the column where the bubble column exists (x,z coordinates) when a chunk already existed but was just loaded.

Then for each column location, find the surface level (the block above water that is either air, or is is a non-source water block), and take necessary action to makes sure that specific location (x/y/z coordinate) is blocked from water flowing and blocked from new water source blocks being created.

This will prevent water from flowing past the soul-sand barrier, which can create issues with rivers growing.

The key piece is that this must be performed fast enough to prevent any water from flowing after the chunk loads, or else it will get past the barrier.

#############################

I have attempted to update the rivers.yml sampler sets for terrain generation near samples, but I am getting unclear errors around the formatting of some expressions.

1. Can you find where the expression error is?  Is a parenthesis missing?  Is an "if" statement lacking 3 arguments?

Perform some other updates around individual samplers:

A. Please update the riverbed sampler to also reduce magnitude around spike locations (so terrain lifts up in these spots) on level 0 rivers.  (Refer to "spikes" from "RiverSamplerAlt.ymlo").

B. Update "elevationDetailedWithHoles" to decrease in elevation where hole sections are found.  Holes should form only around the river bed (River distance 0)

C. Update "caveCeilingMinimumWithSpikes" to also include cave spikes (where spikes should start low and come up, but no closer than 2 blocks from the river height), and also to smoothly increase in height around the same hole sections in "elevationDetailedWithHoles", this way when holes form in the ceiling they are smoothly breaking away the surface of  the cave ceiling and the above terrain.

D. Do a full review of all the samplers that are now being used, especially in terrain generation (Building up riverTerrainSampler), the sampler should give full support for:

D1. River bed erosion that changes depth per river level (appears operational already.)
D2. Spikes in the riverbed that go up to but don't exceed the river surface, and only exist in level 0 rivers.
D3. Slanting up around river beds to surrounding terrain when not enclosed.
D4. Continued surface when river is enclosed.
D5. Support for spikes that go down from the cave ceiling no further than blocks fromm the water height.
D6. Support for holes in the cave ceiling that punch through the surface above.
D7. Clean up unused variables, or consolidate where possible.

#################################

Level 0 river spikes look... okay, not sure if I like them or not, they might be more annnoying than anyhing.

Water flow is still occuring past soulsand, but soul sand is not spanning the river, and it is getting located improperly.  Need to check elevation.

##############################

I need help to understand why rivers appear to have huge terrain spikes near the outside of rivers without any sufficient blend with surrounding terrain.

#######################

Confirm rivers are fixed (L3 contains water?) or just need to drop to L2 only.

Confirm river caves (nice to have)

Confirm glow around river caves / overhangs

Add new biomes into mix



In the file "Calculate_Biome_Percentages.py", one of the tasks is to compute the percentage distribution of biomes as a function of their sampler distributions and expressions.  This appears today to take multiple shortcuts.  I would like you to do a deep review of this python script compared to the way biome distribution is actually computed (Refer to C:\Projects\Terra).  Since the intent of this is to find the percentage of distribution across an infinite map, it must estimate the distribution of each base sampler (ex: white-noise sampler returns a near flat distribution), and then compute how that distribution changes as it is affected through each expression, to yield a final distribution for each sampler and ultimately used to replace another biome.  Accuracy here is important, so full evaluation from the distribution within reasonable ranges, multipliers due to expressions, and ultimate final replacement percentage of a combined expression.

The script should also use the distribution assessment of special named samplers (precipitation / temperature / elevation)


Convert bubble plugin to Terra plugin?

Update Terra apis to latest available?  This should support new paper version?

##########################

In the BiomeTable, I see precipitation / temperature / elevation all span from 0 to 1, but don't the sampler values span from -1 to 1?  Or is there a normalizer occurring somewhere in the chain?

########################

I see there are 2 files with equation ids "EQ_TERRACE_MOUNTAINS", can you build a script that also finds and removes duplicate equations like "remove_duplicate_biomes.py"?  Are there other artifacts that need to be checked for duplicates?

########################

Verify in elevation.yml, non of the 

########################

In "VanillaJavaBiomes.csv" there are a list of vanilla biomes that are available, with a few listed as "no" for "Used In BiomeTable".

Ideally, every non-end or non-nether vanilla biome has at least one if not multiple CHIMERA biomes with that vanilla biome property.  Using "VanillaJavaBiomes.csv" that are not allocated, please use available descriptions and infer from the table properties which CHIMERA biomes should have their vanilla biome definition updated to the currently unallocated vanilla biomes.

#############
BADLAND_BALCOONIES has terraces staggered not using elevation (id: EQ_ROCKY_BUTTES), are these allocated to the correct elevation region?

#################333

Some flat designated / distributed biomes actually have terrain defined by elevation, so are they really flat and / or should they be attributed to flat zones?

Some biomes are NOT defined for flat distribution but they do not use the elevation, so they may have strange river artifacts as the river attempts to climb the standard elevation equation, but the biome does not actually raise with elevation.

#######################

In the latest river terrain sampler (riverTerrainSampler) I am seeing correct enclosed rivers and correct open rivers, but above the enclosed rivers there is a huge discontinuity in elevation.  

I need a deep analysis of this problem to root cause.  It may be simple, but I am unable to identify.

If necessary, go through the terrain sampler and emulate (or design a script to emulate) a terrain that returns a constant elevationDetailed of 105, knowing the terrain generation pipeline is described at C:\Projects\Terra\TerrainGenerationPipeline.md.  What happens when this terrain intersects a river whose width in the generated world whose width is about 20 blocks wide?  If emulating, make sure to use variables that are already a part of this script.  The river can be emulated as going straight through the biome.  All parts of the calculation should be emulated, if making any assumptions / estimations, ask for confirmation, knowing the river sets it's biome on top of the original biome according to add_rivers.yml (riverSampler, which outputs -1 when outside the border region of a river, -0.25 when outside the border activation threshold but closer to the river edge, and 1 when within the activation threshold where the river biome should take control)

################################

Actually the discontinuity might just be due to differing elevation samplers coming into contact.

I see EQ_MULTI_TERRACED_LAND is relying heavily on the 3d sampler which does not have any true blending with the 2d sampler.  This is in contrast with "EQ_LAND


###############################

The discontinuity appears to be fixed, but this exposes a new issue, where the eq_global_river elevation sampler is not always compatible with a biome (such as a biome that does not use the elevation height).  I want to create a plan to investigate how many of these land surface biomes exist (that don't generate terrain from elevation, this should already be documented in BiomeTable.csv), and a recommendation for how they might be repaired.  For instance, "FOLIAGE_FORTRESS" biome IDs have a slow surfaceOffset(x,z) that should probably just be entirely removed, and then a 2-d sampler could be added with a respective elevationDetailed which would shift it in line with other samplers.

Yes please proceed with the "FOLIAGE_FORTRESS" biomes.

Just note that biomes in the "ElevationFlat" designation likely do not need any update because the flatness zeros out the elevation in those locations.  EQ_MULTI_TERRACED also likely does not need an update, since it generally will be higher than the detailed elevation.

##############################################

An issue with this Terra pack is that in very dry regions, a hot very dry region type will border a cold very dry region, which is jarring and nonsensical (cold / snowy region next to a desert / mesa region)

This is due to the way biomes are distributed in the staging sequence, such that a temperature swing from very hot to very cold across a very dry location will cause this discontinuity.

Please ideate alternatives to prevent this discontinuity.

One ideas:

Map moderate temperature very dry biomes to a moderate temperature moderate / low precipitation region instead of a direct jump from cold-desert to hot-desert, potentially just mapping the dry regions of the following regions to something that is not strictly dry to give more of a transition across the dry definition temperature gradient:

boreal-warm
boreal-hot
temperate-cold
temperate-warm

What other alternatives would smooth out the user experience to be less jarring in very dry regions?

#####################################

When creating terrain, rivers are rarely not bounded correctly on either side, resulting in water that is able to flow outward instead of contained by banks.

The sampler "RiverSupportDensity" is intended to ensure land at the bank of the river fully raise up to contain the river water (where the river distance = 0 at the rivers edge).

A positive density return should force block placement to contain river water.  Can you review the expression and corresponding samplers to verify if there is an issue with the way the expression is formulated?

##########################################

To prepare for larger terrain changes, I want to make sure all terrain definitions  directly in biome files are moved to extended properties of the biome with a new or existing eq_* file describing the terrain.  If the terrain sampler expression is identical between two biomes, it should be reused.  Please go through all terrain definitions of biomes, and make sure they are extended from a file instead of a definition inside the biome file itself, and rectify duplicate terrain definitions, and finally create recommendations that may allow biomes to share the same sampler if their sampler definitions are similar.

Now perform the same exercise for all other biome files (not just rearth) if not already complete to pull their terrain definitions out into an extended property file eq_*, and perform the same analysis for any remaining and add it to the TERRAIN_SHARING_RECOMMENDATIONS which I have pulled to the root of the project folder.

##################################################

Now apply fixes for all non-ocean equations.

List all eq_* files that reference customization.cellDistance, as these likely use old biome spread references that are no longer valid.

#########################################

The biome sampler currently uses the following expression for the elevation related distribution:
expression: if(elevation > highlands, 0.75, if(elevation > lowlands, 0.25, if(flatness < 1, -0.25, -0.75)))

In all cases, the midlands and lowlands are leading to the same placeholder biome.

Remove the midlands / lowlands duplicate, and update the expression to the following:
expression: if(elevation > highlands, if(flatness < flatness-factor, 0, -1)))

Then update the distributions to remove the duplicate, example:

        - tundra-flat: 1
        - tundra: 1
        - tundra: 1
        - tundra-highlands: 1
		
		would become:
		
        - tundra-flat: 1
        - tundra: 1
        - tundra-highlands: 1

#############################################

1. Update the biomeInfluence sampler to increase from 0 to 1 as distance into biome grows, derive from:
  - rivers increase (ContinentalRiverDist goes from distance threshold to 1)
  - distance from cell border increases (Convert cell biome distance, BiomeShapeLandmassDist2Center, which goes to 0 as it approaches center)
  - distance from mesa border increases. (mesaFootDist, 0 at mesa foot, grows to 1 into mesa, negative value away from mesa)
  - distance from coast?  (dist2Coast, gets larger the further away from shore, can be normalized using the continents distance?)
  - The biomeInfluence sampler should increase to 1 at the real world block distance of distAtFullInfluence, while 0 when at the border of the above artifacts.

*. Make sure all surface / land biomes respect these borders, this means mesa sub-biome replacements must also use this biome replacement (small biome), not a secondary sampler.

*. Any vast-forest subreplacement must also follow the same restrictive replacement set.

G. Make sure biome distribution for elevation uses cell center instead of pure elevation.

H. Consider updating elevation with influence from river which is not done today.  This would drag elevation down to rivers in most locations for crossing and more natural erosion, but leave some places where elevation doesn't care and the river-specific sampler itself is responsible for determining through it's sampler if it should tunnel through the terrain or ramp.  This creates more variation at river zones.

2. Create a new sampler that indicates biomeInfluence3D, which will also ramp down scaler influence as y height above the detailed elevation plane increases.  This will prevent floating artifacts at biome borders.



###########################################
Goal: Update all "eq_*" related terrain samplers that are used for land biomes to share a common expression and detail ramping method for consistent elevation at biome borders:

sampler-2d shall always return 0.

The current elevation at sampler-2d shall instead be added into the standard sampler where the -y+base or base-y part of the expression exists.

Any 2d noise added into the -y+base apart from the additional elevation shall be multiplied by the biomeInfluence(x,z) to ramp any biome specific 2-d noise.

Refer to the following changes where this was already performed:

Latest commit, where changes have already been made and verified: 12b6a1f0c693c7d91be8de27b9b53263fc0aaf79
Previous commit, where files had older definition:
bdeb91eef5066e68bc78cd4270f080a68827ff75

Files modified for reference, to apply the same pattern to all other "eq_*" files that are used for land biomes:

eq_pillars
eq_land
eq_alpha_mountains

Be sure to only adjust "eq_" files that are used for land biomes.  The biometable may be useful context to verify the eq file is related to land terrain (as opposed to ocean terrain)


#####################################

Make sure all frozen river variants have packed ice for icecles?
Check rivers now that min-density has been commented.
Check rivers for bubble columns.
Check distribution of biomes, dry/warm regions seem prolific.  Might need some variety here?   Might need to augment precipitation?





Update the following biomes to use a updated biomeInfluence sampler instead of the current cell distance reference:

eq_tilted_plateau.yml	3 (lines 8, 43, 55)  (Is just a very jagged sampler anyways.)
eq_terrace_mountain.yml	1 (line 43)
eq_sakura_streams.yml	4 (lines 32, 38, 67, 78)
eq_pillars.yml	1 (line 64)
eq_bamboo_basin.yml	3 (lines 42, 59, 70)
eq_arid_arboretum.yml	1 (line 58)

Need ALL  land biomes with terrain features to follow the same small biome distribution pattern instead of the current hard-cutoff that is being used.
Investigate:
Are terraced elevations (elevationTerraced) larger or smaller than normal elevation?  A: Larger.
Act:

*. Ensure elevation is "0-d" out on approaching coastal threshold except for spots?  However this will wear down coasts where they don't need to wear?

Actions to take in order to better 
1. 

3. Update the above terrain equations above that used cell distance to instead use biome influence for 3d structures.


6. Make changes to all other surface equation files to remove the 2d elevation sampler and instead implant it into the standard 3d sampler.  This is to give fidelity to that sampler and simplify computation.

The change I made to eq_pillars.yml is working to properly isolate the sampling to only the 3d sampling.

I want to make similar changes to the other files 


Come back to in future:

eq_tilted_plateau
river influence on elevation?

##################################################

Changes:
1. Update biome sampler to use mountain mask for highlands biome placement instead of elevation?  This way elevation detailed need not be evaluated for biome placement.

2. Update flatness sampler to not include mountain mask, and then reduce flatness to 0.75 max factor instead of 0.95 so that attributes are not suppressed so significantly on "flat" regions.

Somehow rivers still appear to be branching more in arid regions, maybe the sampler is a removal probability and it just has bad semantics?


3. Update river distance sampler to user lower resolution river distance if x/z coordinates are on 4th block?  This would significantly improve the river sampler speed for sparse biome lookup as long as it's using the correct coordinates.


7. Consider preventing "flat" from overruling mountain range?  But need to be sure mountain ranges are not so aggressive...


Issue is with elevation detailed and herping from river elevaiton???
Fix desert not rolling down from detailed elevation?
Why does a normal river have glow lamps that are only for frozen rivers?


Secluded Valley appears to be bugged / not populating with content.
  Issue might be with palette below 65?

  Now working but biome appears deeper than normal biome, how to restrict?  Need intermediate biome before further cave propagation?


Volcanos / Prismatic springs show the same strange artifacts that was seen before with the blending of the 2-d sampler and the 3d sampler across biomes, despite it being configured to be effectively disabled.
foliage fortress has no transition<- May need to linearize on transition.
VERDENT_VALLEYS_OUTER looks like trash
prismatic spring still looks wrong, no crater exists like it does in volcano

Fix some flat areas being too flat? <- Maybe defect in previous sampler set.


Tuff Mountains <- Fix ice replacements? (Was actually spires)


fenlands <- Change to raised biome elevation
Fenlands <- Use new locator <- These look okay, could possibly change to just offset from the cell height, but that might cause new issues.

Consider expanding continent size and mountain mask size, to get larger features in that space.

Carving Creaks <- In flat dry area, confirm rendering <- These are lifted much higher than expected, something wrong with terrain modification, or double lifted from hidden 2d sampler?  (Maxing out around 140 blocks high?)

Need higher glow lichen feature to go higher, probably from about 20 below ocean upwards of 100 blocks, HIGH_GLOW_LICHEN, probably spaced with padded grid and located only under stone.
Marine Monoliths needs glow lichen (Use HIGH_GLOW_LICHEN) <- Still no glow lichen appearing.
Rocky refuge <- Need glow lichen, under refuge area only?  Possible? (Use HIGH_GLOW_LICHEN might be sufficient since refuge area is the only raised / cave-like feature) [GLOW LICHEM MISSING]
COVE_GLOW_LICHEN < - prevent placement in cold regions so they don't melt ice, similar to glowshroom locator restriction
foliage fortress needs glow lichen on mid-bracing (Use HIGH_GLOW_LICHEN) [GLOW LICHEM MISSING]


Secluded sanctuary cap appears to be missing, something missed in sampler offset?
Secluded sanctuary appears to be missing glow lichen above around 40, need to reduce height?
Secluded sanctuary <- Consider feature placement above?  How to place very space trees above?  Or just keep flat
[THIS NEEDS TO BE Cellular flat DUE TO TERRAIN SAMPLER FORM?]  But that breaks other stuff, does it just need to be flat across the board and rely on blending at borders?  That might not work well either...
Secluded sanctuary has many many trees surrounding, consequence of new tree feature or outer ring definition?

############################

STILL IN WORK:

PRISMATIC SPRING IS NOW BUMPING UP AT CENTER, INSTEAD OF TUNNELLING DOWN
THEORY:
Erosion is responsible for drilling into form for prismatic sphere.
Outcomes should be zero.
How is is center radius getting bumped up?  (When crater height is negative value, and max height is 0)
NEXT: Try with a max height with a value, and a crater height of 0?



Move secluded value to smaller pattern in biome.

Make sure bamboo basin actually has water now that it's been shifted down.

Need help:

Prismatic shape not making any sense, draws in from far away.

Update VOLCANO_FLUID so that the max fluid level is a random height between 10% to 90% of the top of the rim from the cell height (spotBaseElevation).

Volcano is maybe okay, is issue with craters actually due to water placement feature?  Or is it just bad sampler?

Arid Arboretum <- Pillars are getting lost, likely due to issue in combining this, need to modify like eq_pillars.  Check for cellular elevation lift similar to eq_pillars.  This might also need to be at a lower level depending on how the palette is restricted? <- How to prevent the blocking?  Drop "max" outside pillar range?



In work:
Confirm extinct craters working - Straight line running through, will need to see if this occurs on standard volcano.  Hole is way smaller than expected - might be due to height and eq method?
Move eq from EQ_EXTINCT_VOLCANO to EQ_VOLCANO and EQ_PRISMATIC_SPRING while retaining height variables of each.

Carefully update the prismatic spring to fix the water related features:

1. Update the water level in the prismatic spring (the "ocean" sampler) is restricted to within the inner ring if not already done, and set the water level similar to the VOLCANO_FLUID locator, but note prismatic springs should be able to go all the way to -max height (so that half the time, no water appears)

2. Make sure the prismatic spring features are restricted to the ring inside the rim times the fluid level in the ring multiplied by the ratio of the water fluid level, so that these features only occur under water.  If there is no water (ocean sampler is below the elevation at the crater), only smoke should rise from the center.

    - PRISMATIC_SPRING_MAGMA
    - PRISMATIC_SPRING_SMOKE

Some of this looks better, but 

Fix lava fluid - should be variable height depending on random interval based on selected max.

Prismatic spring <- Need to fix dist of features

Distribution related changes:

Fix carving

Need coastal biome feature?  Just for carving creek?  It should always be located near ocean to escape?  Need to locate away from rivers and with low continent definition.

Change large region to be a grouping of small biomes instead of current allocation, so that boundaries are respected properly for large biomes (so they share small biome sets)

But how to make sure distance to spots is correct if spot isn't always present?  Need to and with spot presence.

#####################################

Remove water from bamboo basin pallette, let water fill naturally.
Arid is completely broken



5. Consider for valley biomes with centered features to just use an offset from the cell elevation.

6. Consider shifting mesa structure back to "max" instead of "round function?



Many volcano / spring fixes need to be made:
Craters are not working, and they need a wider radius band.
A. Water is going above rim.
B. Still have strang straight band, only ever see this in the crater form.

#######################

How to optimize:

New Dendry method to only query distance to diver instead of full elevation construction.
  - Allow method to create larger / wider cache birth for these samples (special y-value?)
  - This could then be used for the far river distance?

Remove elevation with rivers from temperature propagation
  - This way river elevation is not required for biome pipeline.