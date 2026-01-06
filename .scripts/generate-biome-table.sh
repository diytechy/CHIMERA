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
SET_BIOMES_FILE="biome-distribution/stages/set_biomes_in_climates.yml"

# Preset directory
PRESET_DIR="biome-distribution/presets"

# Temporary file for caching biome lists per preset
TEMP_PRESET_CACHE="/tmp/preset_biomes_$$"

# Temporary files for climate mapping
TEMP_CLIMATE_DIR="/tmp/climate_maps_$$"
BIOME_ZONE_MAP="$TEMP_CLIMATE_DIR/biome_zones.map"
TEMP_INTERMEDIATE_MAP="$TEMP_CLIMATE_DIR/temperature_intermediate.map"
PRECIP_INTERMEDIATE_MAP="$TEMP_CLIMATE_DIR/precipitation_intermediate.map"
ELEV_INTERMEDIATE_MAP="$TEMP_CLIMATE_DIR/elevation_intermediate.map"

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

    # Temporary array to collect biome IDs
    local biomes=()

    # Method 1: Extract from "from: BIOME_NAME" and "to: BIOME_NAME" (single values)
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*(from|to):[[:space:]]*([A-Z_][A-Z_0-9]*)[[:space:]]*$ ]]; then
            biomes+=("${BASH_REMATCH[2]}")
        fi
    done < "$file"

    # Method 2: Extract biome IDs from weighted lists - looks for patterns like:
    # - BIOME_NAME: 1
    # BIOME_NAME: weight
    # Also filters out YAML keys and common configuration terms
    while IFS= read -r line; do
        biomes+=("$line")
    done < <(grep -E '^\s*-?\s*[A-Z_a-z-]+\s*:' "$file" 2>/dev/null | \
        grep -vE '(type|sampler|range|min|max|frequency|salt|return|variables|functions|expression|biomes|stages|extrusions|provider|pipeline|source|blend|amplitude|default-from|default-to|<<|resolution|jitter|lookup|dimensions)' | \
        sed -E 's/^\s*-?\s*([A-Z_a-z-]+)\s*:.*/\1/' | \
        grep -vE '^(from|to|SELF)$')

    # Method 3: Extract from source biomes section (e.g., "biomes:" followed by list)
    # This catches patterns like:
    #   biomes:
    #     ocean: 1
    #     land: 1
    local in_biomes_section=0
    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*biomes:[[:space:]]*$ ]]; then
            in_biomes_section=1
            continue
        fi

        if [ $in_biomes_section -eq 1 ]; then
            # Check if still in indented section
            if [[ "$line" =~ ^[[:space:]]{2,}([a-z_-]+):[[:space:]]*[0-9] ]]; then
                # Convert to uppercase with underscores for consistency
                local biome=$(echo "${BASH_REMATCH[1]}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
                biomes+=("$biome")
            elif [[ "$line" =~ ^[a-z] ]]; then
                # New top-level key, exit biomes section
                in_biomes_section=0
            fi
        fi
    done < "$file"

    # Output unique biome IDs, sorted
    printf '%s\n' "${biomes[@]}" | sort -u | grep -v '^$'
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

# Function to extract base climate zones from a climate file
# Parses YAML anchors (e.g., &iceCap) from default-to section
extract_base_climate_zones() {
    local climate_file="$1"

    if [ ! -f "$climate_file" ]; then
        return
    fi

    # Extract lines with anchors from default-to section
    # Format: - zone-name: &anchorName weight
    awk '/default-to:/,/^[[:space:]]*to:/ {
        if ($0 ~ /&[a-zA-Z]+/) {
            match($0, /- ([a-z-]+):/, arr)
            if (arr[1] != "") print arr[1]
        }
    }' "$climate_file" | sort -u
}

# Function to build intermediate climate zone mapping
# Maps intermediate zones (e.g., "polar-mesa") to base zones (e.g., "ice-cap")
build_intermediate_zone_map() {
    local climate_file="$1"
    local map_file="$2"

    if [ ! -f "$climate_file" ]; then
        return
    fi

    # First, extract anchor definitions (base zones with their anchor names)
    # Format: - ice-cap: &iceCap 1
    declare -A anchors
    while IFS= read -r line; do
        if [[ "$line" =~ -[[:space:]]*([a-z-]+):[[:space:]]*\&([a-zA-Z]+) ]]; then
            local zone="${BASH_REMATCH[1]}"
            local anchor="${BASH_REMATCH[2]}"
            anchors[$anchor]="$zone"
        fi
    done < "$climate_file"

    # Now extract intermediate zone mappings using aliases
    # Format: - polar-mesa: *iceCap
    local current_intermediate=""
    while IFS= read -r line; do
        # Check if this is an intermediate zone name (indented under "to:")
        if [[ "$line" =~ ^[[:space:]]{6}([a-z-]+):$ ]]; then
            current_intermediate="${BASH_REMATCH[1]}"
        # Check if this is an alias reference
        elif [[ "$line" =~ -[[:space:]]*([a-z-]+):[[:space:]]*\*([a-zA-Z]+) ]]; then
            local intermediate_zone="${BASH_REMATCH[1]}"
            local alias="${BASH_REMATCH[2]}"
            local base_zone="${anchors[$alias]}"

            if [ -n "$base_zone" ]; then
                # Write mapping to file: intermediate_zone -> base_zone
                echo "${intermediate_zone}|${base_zone}" >> "$map_file"
            fi
        # Alternative: alias without zone name (uses current_intermediate)
        elif [[ "$line" =~ ^[[:space:]]{8}-[[:space:]]+\*([a-zA-Z]+) ]] && [ -n "$current_intermediate" ]; then
            local alias="${BASH_REMATCH[1]}"
            local base_zone="${anchors[$alias]}"

            if [ -n "$base_zone" ]; then
                echo "${current_intermediate}|${base_zone}" >> "$map_file"
            fi
        fi
    done < "$climate_file"
}

# Function to extract biome to intermediate zone mappings
# Parses set_biomes_in_climates.yml
extract_biome_zone_mappings() {
    local set_biomes_file="$1"
    local output_file="$2"

    if [ ! -f "$set_biomes_file" ]; then
        return
    fi

    local current_zone=""
    while IFS= read -r line; do
        # Detect intermediate zone (6 spaces indentation)
        if [[ "$line" =~ ^[[:space:]]{6}([a-z-]+):[[:space:]]*$ ]]; then
            current_zone="${BASH_REMATCH[1]}"
        # Detect biome mapping (8+ spaces indentation)
        elif [[ "$line" =~ ^[[:space:]]{8}-[[:space:]]*([A-Z_]+): ]] && [ -n "$current_zone" ]; then
            local biome="${BASH_REMATCH[1]}"
            echo "${biome}|${current_zone}" >> "$output_file"
        fi
    done < "$set_biomes_file"
}

# Function to check if a biome has a climate designation
# Uses the mapping files to trace biome -> intermediate zone -> base zone -> climate file
check_climate_with_mapping() {
    local biome_id="$1"
    local climate_name="$2"  # "temperature", "precipitation", or "elevation"
    local biome_zone_map="$3"
    local intermediate_map="$4"
    local base_zones="$5"

    # Get intermediate zones for this biome
    local intermediate_zones=$(grep "^${biome_id}|" "$biome_zone_map" 2>/dev/null | cut -d'|' -f2 | sort -u)

    if [ -z "$intermediate_zones" ]; then
        echo "N"
        return
    fi

    # Check if any intermediate zone maps to a base zone in this climate file
    while IFS= read -r intermediate_zone; do
        # Get base zones for this intermediate zone
        local base_zone_matches=$(grep "^${intermediate_zone}|" "$intermediate_map" 2>/dev/null | cut -d'|' -f2)

        # Check if any base zone matches the climate file's base zones
        while IFS= read -r base_zone; do
            if echo "$base_zones" | grep -q "^${base_zone}$"; then
                echo "Y"
                return
            fi
        done <<< "$base_zone_matches"

        # Also check if the intermediate zone itself is a base zone
        if echo "$base_zones" | grep -q "^${intermediate_zone}$"; then
            echo "Y"
            return
        fi
    done <<< "$intermediate_zones"

    echo "N"
}

# Build climate mapping cache
echo "Building climate mapping cache..."
mkdir -p "$TEMP_CLIMATE_DIR"

# Extract base climate zones
TEMP_BASE_ZONES=$(extract_base_climate_zones "$TEMPERATURE_FILE")
PRECIP_BASE_ZONES=$(extract_base_climate_zones "$PRECIPITATION_FILE")
ELEV_BASE_ZONES=$(extract_base_climate_zones "$ELEVATION_FILE")

# Build intermediate zone mappings
build_intermediate_zone_map "$TEMPERATURE_FILE" "$TEMP_INTERMEDIATE_MAP"
build_intermediate_zone_map "$PRECIPITATION_FILE" "$PRECIP_INTERMEDIATE_MAP"
build_intermediate_zone_map "$ELEVATION_FILE" "$ELEV_INTERMEDIATE_MAP"

# Extract biome to zone mappings from set_biomes_in_climates.yml
if [ -f "$SET_BIOMES_FILE" ]; then
    extract_biome_zone_mappings "$SET_BIOMES_FILE" "$BIOME_ZONE_MAP"
fi

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

    # Check climate flags using the new mapping-based approach
    precipitation=$(check_climate_with_mapping "$biome_id" "precipitation" "$BIOME_ZONE_MAP" "$PRECIP_INTERMEDIATE_MAP" "$PRECIP_BASE_ZONES")
    temperature=$(check_climate_with_mapping "$biome_id" "temperature" "$BIOME_ZONE_MAP" "$TEMP_INTERMEDIATE_MAP" "$TEMP_BASE_ZONES")
    elevation=$(check_climate_with_mapping "$biome_id" "elevation" "$BIOME_ZONE_MAP" "$ELEV_INTERMEDIATE_MAP" "$ELEV_BASE_ZONES")

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

# Clean up temporary caches
rm -rf "$TEMP_PRESET_CACHE"
rm -rf "$TEMP_CLIMATE_DIR"

# Count results
total_biomes=$(tail -n +2 "$OUTPUT_FILE" | wc -l)

echo "BiomeTable.csv generated successfully!"
echo "  Location: $OUTPUT_FILE"
echo "  Total biomes: $total_biomes"
echo "  Presets analyzed: ${#preset_names[@]} (${preset_names[*]})"
