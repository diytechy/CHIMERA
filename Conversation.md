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



Review "resolved_samplers.yml" and identify all samplers

Terrain construction:
 - Blend plains and continental contribution using... mask?
 - Add mountains and hills.
 - Is flatness really necessary?
 - Overlay mesas