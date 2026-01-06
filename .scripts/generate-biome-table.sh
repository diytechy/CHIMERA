#!/bin/bash

# ============================================================================
# generate-biome-table.sh
# Generates BiomeTable.csv from biome configuration files
#
# Output columns:
#   BiomeID, Extends, Color, Precipitation, Temperature, Elevation, [Preset columns...]
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/BiomeTable.csv"

# Climate config files
PRECIPITATION_FILE="biome-distribution/stages/climate/precipitation.yml"
TEMPERATURE_FILE="biome-distribution/stages/climate/temperature.yml"
ELEVATION_FILE="biome-distribution/stages/climate/elevation.yml"

# Preset directory
PRESET_DIR="biome-distribution/presets"

# Temporary file for caching biome lists per preset
TEMP_PRESET_CACHE="/tmp/preset_biomes_$$"

# Find all biome files (excluding abstract biomes)
biome_files=$(find biomes -name "*.yml" -not -path "biomes/abstract/*" -not -name "colors.yml" | sort)

# Function to normalize biome ID (converts between formats)
# UPPERCASE_UNDERSCORE <-> lowercase-hyphen
normalize_biome_id() {
    local id="$1"
    echo "$id" | tr '[:upper:]' '[:lower:]' | tr '_' '-'
}

# Function to extract biome IDs from a YAML file
# This handles direct references, lists, and weighted entries
extract_biomes_from_yaml() {
    local file="$1"

    if [ ! -f "$file" ]; then
        return
    fi

    # Extract biome IDs - looks for patterns like:
    # - BIOME_NAME: 1
    # - BIOME_NAME
    # biome-name: value
    # Also handles "to:" sections in REPLACE operations
    grep -E '^\s*-?\s*[A-Z_a-z-]+\s*:' "$file" 2>/dev/null | \
        grep -vE '(type|from|sampler|range|min|max|frequency|salt|return|variables|functions|expression|biomes|stages|extrusions|provider|pipeline|source|blend|amplitude|default-from|default-to|<<)' | \
        sed -E 's/^\s*-?\s*([A-Z_a-z-]+)\s*:.*/\1/' | \
        grep -vE '^(to|SELF)$' | \
        sort -u
}

# Function to recursively extract biomes from a preset by following stage/extrusion includes
extract_biomes_from_preset() {
    local preset_file="$1"
    local visited_file="$2"
    local depth="${3:-0}"

    # Prevent infinite recursion
    if [ $depth -gt 20 ]; then
        return
    fi

    if [ ! -f "$preset_file" ]; then
        return
    fi

    # Track visited files to avoid loops
    if grep -q "^$preset_file$" "$visited_file" 2>/dev/null; then
        return
    fi
    echo "$preset_file" >> "$visited_file"

    # Extract biomes directly from this file
    extract_biomes_from_yaml "$preset_file"

    # Find and follow << include references
    # Format: << path/to/file.yml:key
    local includes=$(grep -oE '<<\s+[^:]+\.yml' "$preset_file" 2>/dev/null | sed 's/<<\s*//')

    for include in $includes; do
        if [ -f "$include" ]; then
            extract_biomes_from_preset "$include" "$visited_file" $((depth + 1))
        fi
    done
}

# Function to build preset biome cache
# Creates temporary files listing all biomes for each preset
build_preset_cache() {
    mkdir -p "$TEMP_PRESET_CACHE"

    for preset_file in "$PRESET_DIR"/*.yml; do
        if [ ! -f "$preset_file" ]; then
            continue
        fi

        local preset_name=$(basename "$preset_file" .yml)
        local visited_file="$TEMP_PRESET_CACHE/${preset_name}_visited.tmp"
        local output_file="$TEMP_PRESET_CACHE/${preset_name}.biomes"

        # Extract all biomes for this preset
        extract_biomes_from_preset "$preset_file" "$visited_file" 0 | sort -u > "$output_file"

        # Clean up visited tracking file
        rm -f "$visited_file"
    done
}

# Function to check if a biome is in a preset
check_preset() {
    local biome_id="$1"
    local preset_name="$2"
    local cache_file="$TEMP_PRESET_CACHE/${preset_name}.biomes"

    if [ ! -f "$cache_file" ]; then
        echo "N"
        return
    fi

    # Normalize the biome ID for comparison
    local search_id=$(normalize_biome_id "$biome_id")

    # Check both formats in the cache file
    if grep -qi "^${biome_id}$" "$cache_file" 2>/dev/null || \
       grep -qi "^${search_id}$" "$cache_file" 2>/dev/null; then
        echo "Y"
    else
        echo "N"
    fi
}

# Function to check if a biome-style ID appears in a climate file
# Converts UPPERCASE_UNDERSCORE to lowercase-hyphen format for matching
check_climate_file() {
    local biome_id="$1"
    local climate_file="$2"

    # Convert ID: MAPLE_GROVE -> maple-grove
    local search_id=$(echo "$biome_id" | tr '[:upper:]' '[:lower:]' | tr '_' '-')

    if grep -qi "$search_id" "$climate_file" 2>/dev/null; then
        echo "Y"
    else
        echo "N"
    fi
}

# Build preset cache
echo "Building preset cache..."
build_preset_cache

# Get list of preset names (sorted)
preset_names=()
for preset_file in "$PRESET_DIR"/*.yml; do
    if [ -f "$preset_file" ]; then
        preset_names+=("$(basename "$preset_file" .yml)")
    fi
done
preset_names=($(printf '%s\n' "${preset_names[@]}" | sort))

# Initialize output with header
header="BiomeID,Extends,Color,Precipitation,Temperature,Elevation"
for preset in "${preset_names[@]}"; do
    header="${header},${preset}"
done
echo "$header" > "$OUTPUT_FILE"

# Process each biome file
for biome_file in $biome_files; do
    # Check if this is actually a biome file (contains "type: BIOME")
    if ! grep -q "type: BIOME" "$biome_file" 2>/dev/null; then
        continue
    fi

    # Extract BiomeID
    biome_id=$(grep -m1 "^id:" "$biome_file" | sed 's/id:[[:space:]]*//' | tr -d '\r')

    if [ -z "$biome_id" ]; then
        continue
    fi

    # Extract Extends (may be single value or list)
    extends=""
    if grep -q "^extends:" "$biome_file"; then
        # Check if extends is a list (next line starts with -)
        extends_line=$(grep -n "^extends:" "$biome_file" | head -1 | cut -d: -f1)
        next_line=$((extends_line + 1))
        next_content=$(sed -n "${next_line}p" "$biome_file" | tr -d '\r')

        if [[ "$next_content" == *"- "* ]]; then
            # It's a list - extract all items until next key
            extends=$(awk '/^extends:/{found=1; next} found && /^[[:space:]]*-/{gsub(/^[[:space:]]*-[[:space:]]*/, ""); items = items (items ? "; " : "") $0} found && /^[a-z]/{exit} END{print items}' "$biome_file" | tr -d '\r')
        else
            # Single value on same line
            extends=$(grep "^extends:" "$biome_file" | sed 's/extends:[[:space:]]*//' | tr -d '\r')
        fi
    fi

    # Extract Color
    color=$(grep -m1 "^color:" "$biome_file" | sed 's/color:[[:space:]]*//' | tr -d '\r')

    # Check climate flags
    precipitation=$(check_climate_file "$biome_id" "$PRECIPITATION_FILE")
    temperature=$(check_climate_file "$biome_id" "$TEMPERATURE_FILE")
    elevation=$(check_climate_file "$biome_id" "$ELEVATION_FILE")

    # Escape any commas in extends field and wrap in quotes if needed
    if [[ "$extends" == *","* ]] || [[ "$extends" == *";"* ]]; then
        extends="\"$extends\""
    fi

    # Check preset flags
    preset_flags=""
    for preset in "${preset_names[@]}"; do
        preset_flag=$(check_preset "$biome_id" "$preset")
        preset_flags="${preset_flags},${preset_flag}"
    done

    # Write row to CSV
    echo "${biome_id},${extends},${color},${precipitation},${temperature},${elevation}${preset_flags}" >> "$OUTPUT_FILE"
done

# Clean up temporary cache
rm -rf "$TEMP_PRESET_CACHE"

# Count results
total_biomes=$(tail -n +2 "$OUTPUT_FILE" | wc -l)

echo "BiomeTable.csv generated successfully!"
echo "  Location: $OUTPUT_FILE"
echo "  Total biomes: $total_biomes"
echo "  Presets analyzed: ${#preset_names[@]} (${preset_names[*]})"
