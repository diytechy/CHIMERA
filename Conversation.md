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

type: DOMAIN_WARP
amplitude: 1500
sampler: *continental_landmass
warp: 
  type: RIDGED
  lacunarity: 3
  gain: 0.45
  octaves: 4
  sampler:
    type: OPEN_SIMPLEX_2
    salt: 1
    frequency: 0.0002
        
Integrate river width variation
Integrate river boundary distance
Update river type value based on distance from boundary
Update elevation herp function with river distance influence


Update elevation sampler with older elevation sampler?  Or do a comparison between the two to see where the details get exposed between the two.
Update mountains to use both kinds of mountains (Using opposite sides of the mountain mask)
Make sure all masks are also weighted / limited by the continental sampler.
Change Mesa to use herp interpolation instead off current exponential.
Consider giving flat sampler an offset based on continental sampler.
Tune mountain mask for distribution across land-base.
Note also current elevation "Flatness" parameter might need to be removed, as it gives continental distribution very linear spreads, which aren't very natural.
Remove duplicate "lerp" function from applicable files, they should all reference the interpolation file.
Add land tag to all appropriate biomes
Add ocean tag to all appropriate biomes
Make sure deep sinks avoid rivers
Add sinkholes?  Or how will those avoid rivers?  Only through border / land type biome filtering?



Now that "resolved_samplers.yml" has been built, make a plan to create another python script that performs the following:

- Detects identical samplers that are used more than 3 times.
that runs against the resolved_samplers.yml



Review "resolved_samplers.yml" and identify all samplers

