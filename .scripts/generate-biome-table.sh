#!/bin/bash

# ============================================================================
# generate-biome-table.sh
# Generates BiomeTable.csv from biome configuration files
#
# Output columns:
#   BiomeID, Extends, Color, Precipitation, Temperature, Elevation
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/BiomeTable.csv"

# Climate config files
PRECIPITATION_FILE="biome-distribution/stages/climate/precipitation.yml"
TEMPERATURE_FILE="biome-distribution/stages/climate/temperature.yml"
ELEVATION_FILE="biome-distribution/stages/climate/elevation.yml"

# Find all biome files (excluding abstract biomes)
biome_files=$(find biomes -name "*.yml" -not -path "biomes/abstract/*" -not -name "colors.yml" | sort)

# Initialize output with header
echo "BiomeID,Extends,Color,Precipitation,Temperature,Elevation" > "$OUTPUT_FILE"

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

    # Write row to CSV
    echo "${biome_id},${extends},${color},${precipitation},${temperature},${elevation}" >> "$OUTPUT_FILE"
done

# Count results
total_biomes=$(tail -n +2 "$OUTPUT_FILE" | wc -l)

echo "BiomeTable.csv generated successfully!"
echo "  Location: $OUTPUT_FILE"
echo "  Total biomes: $total_biomes"
