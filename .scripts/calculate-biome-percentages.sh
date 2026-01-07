#!/bin/bash

# ============================================================================
# calculate-biome-percentages.sh
# Calculates actual biome percentages by tracing through preset pipelines
#
# This script properly simulates Terra's biome generation pipeline:
# 1. Starts with source distribution (ocean: 1, land: 1)
# 2. Traces through each stage in order
# 3. Calculates cascading probabilities
# 4. Outputs percentage for each biome in each preset
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_FILE="$SCRIPT_DIR/BiomeTable.csv"
PRESET_DIR="biome-distribution/presets"

# Temporary files for probability tracking
TEMP_DIR="/tmp/biome_calc_$$"
mkdir -p "$TEMP_DIR"

# Associative arrays to track biome probabilities
# Format: biome_name -> probability (0.0 to 1.0)

# ============================================================================
# YAML Parsing Functions
# ============================================================================

# Extract source biomes and their weights from a preset file
extract_source_biomes() {
    local preset_file="$1"
    local output_file="$2"

    # Extract biomes: section under pipeline: -> source:
    awk '
        /^[[:space:]]*source:/ { in_source=1; next }
        in_source && /^[[:space:]]*biomes:/ { in_biomes=1; next }
        in_biomes && /^[[:space:]]{6,}[a-z-]+:/ {
            match($0, /^[[:space:]]*([a-z-]+):[[:space:]]*([0-9]+)/, arr)
            if (arr[1] != "") print arr[1] "|" arr[2]
        }
        in_biomes && /^[[:space:]]{0,4}[a-z]+:/ && !/biomes:/ { exit }
    ' "$preset_file" > "$output_file"
}

# Extract stage file references from preset
extract_stage_files() {
    local preset_file="$1"
    local output_file="$2"

    # Extract << file.yml:stages references
    grep -oE '<<[[:space:]]+[^:]+\.yml:stages' "$preset_file" | \
        sed 's/<<[[:space:]]*\([^:]*\)\.yml:stages/\1.yml/' > "$output_file" || true

    # Also extract inline stages (type: REPLACE, etc.)
    awk '
        /^[[:space:]]*stages:/ { in_stages=1; next }
        in_stages && /^[[:space:]]{8,}-[[:space:]]*type:[[:space:]]*REPLACE/ {
            print "INLINE_REPLACE"
        }
        in_stages && /^[[:space:]]{8,}-[[:space:]]*<</ { next }
        in_stages && /^[[:space:]]{0,6}[a-z]+:/ && !/stages:/ { in_stages=0 }
    ' "$preset_file" >> "$output_file"
}

# Parse a REPLACE_LIST stage to extract transformations
# Returns: from_biome|to_biome_1:weight_1,to_biome_2:weight_2,...
parse_replace_list_stage() {
    local stage_file="$1"
    local output_file="$2"

    awk '
        BEGIN { current_from = ""; in_to = 0 }

        # Match default-from
        /^[[:space:]]*default-from:/ {
            match($0, /default-from:[[:space:]]*([a-z-]+)/, arr)
            current_from = arr[1]
            next
        }

        # Match from in "to:" section
        /^[[:space:]]{6}[a-z-]+:$/ {
            match($0, /^[[:space:]]*([a-z-]+):/, arr)
            current_from = arr[1]
            in_to = 1
            to_list = ""
            next
        }

        # Match biome weights under current from
        in_to && /^[[:space:]]{8}-[[:space:]]*[A-Za-z_-]+:[[:space:]]*[0-9]/ {
            match($0, /-[[:space:]]*([A-Za-z_-]+):[[:space:]]*([0-9]+)/, arr)
            if (arr[1] != "" && arr[1] != "SELF") {
                if (to_list != "") to_list = to_list ","
                to_list = to_list arr[1] ":" arr[2]
            }
        }

        # End of current from section
        in_to && /^[[:space:]]{0,6}[a-z]/ && !/^[[:space:]]{8}/ {
            if (current_from != "" && to_list != "") {
                print current_from "|" to_list
            }
            current_from = ""
            to_list = ""
            in_to = 0
        }

        END {
            if (current_from != "" && to_list != "") {
                print current_from "|" to_list
            }
        }
    ' "$stage_file" > "$output_file"
}

# ============================================================================
# Probability Calculation Functions
# ============================================================================

# Initialize probability distribution from source biomes
# Input: file with "biome|weight" per line
# Output: file with "biome|probability" per line
initialize_distribution() {
    local source_file="$1"
    local output_file="$2"

    # Calculate total weight
    local total_weight=0
    while IFS='|' read -r biome weight; do
        total_weight=$((total_weight + weight))
    done < "$source_file"

    # Calculate probabilities
    while IFS='|' read -r biome weight; do
        if [ $total_weight -gt 0 ]; then
            local prob=$(awk "BEGIN {printf \"%.6f\", $weight / $total_weight}")
            echo "${biome}|${prob}"
        fi
    done < "$source_file" > "$output_file"
}

# Apply a REPLACE_LIST transformation to current distribution
# For each "from" biome, split its probability among "to" biomes by weight
apply_replace_list() {
    local current_dist="$1"
    local transformations="$2"
    local output_dist="$3"

    # Create temporary distribution
    local temp_dist="${TEMP_DIR}/dist_temp_$$"
    cp "$current_dist" "$temp_dist"

    # Process each transformation
    while IFS='|' read -r from_biome to_list; do
        # Get current probability of from_biome
        local from_prob=$(grep "^${from_biome}|" "$temp_dist" 2>/dev/null | cut -d'|' -f2)

        if [ -z "$from_prob" ]; then
            continue
        fi

        # Remove from_biome from distribution
        grep -v "^${from_biome}|" "$temp_dist" > "${temp_dist}.new" || true
        mv "${temp_dist}.new" "$temp_dist"

        # Calculate total weight of to_biomes
        local total_weight=0
        IFS=',' read -ra TO_ITEMS <<< "$to_list"
        for item in "${TO_ITEMS[@]}"; do
            local weight=$(echo "$item" | cut -d':' -f2)
            total_weight=$((total_weight + weight))
        done

        # Distribute probability to to_biomes
        for item in "${TO_ITEMS[@]}"; do
            local to_biome=$(echo "$item" | cut -d':' -f1)
            local weight=$(echo "$item" | cut -d':' -f2)

            if [ $total_weight -gt 0 ]; then
                local new_prob=$(awk "BEGIN {printf \"%.6f\", $from_prob * $weight / $total_weight}")

                # Add or accumulate probability
                if grep -q "^${to_biome}|" "$temp_dist" 2>/dev/null; then
                    local existing_prob=$(grep "^${to_biome}|" "$temp_dist" | cut -d'|' -f2)
                    local combined_prob=$(awk "BEGIN {printf \"%.6f\", $existing_prob + $new_prob}")
                    grep -v "^${to_biome}|" "$temp_dist" > "${temp_dist}.new"
                    echo "${to_biome}|${combined_prob}" >> "${temp_dist}.new"
                    mv "${temp_dist}.new" "$temp_dist"
                else
                    echo "${to_biome}|${new_prob}" >> "$temp_dist"
                fi
            fi
        done

    done < "$transformations"

    # Output final distribution
    cp "$temp_dist" "$output_dist"
    rm -f "$temp_dist" "${temp_dist}.new"
}

# Process a stage file and update distribution
process_stage() {
    local stage_file="$1"
    local current_dist="$2"
    local output_dist="$3"

    echo "Processing stage: $stage_file" >&2

    if [ ! -f "$stage_file" ]; then
        echo "  Warning: Stage file not found, skipping" >&2
        cp "$current_dist" "$output_dist"
        return
    fi

    # Check stage type
    if grep -q "type: REPLACE_LIST" "$stage_file"; then
        echo "  Type: REPLACE_LIST" >&2
        local transforms="${TEMP_DIR}/transforms_$$"
        parse_replace_list_stage "$stage_file" "$transforms"
        apply_replace_list "$current_dist" "$transforms" "$output_dist"
        rm -f "$transforms"
    elif grep -q "type: REPLACE" "$stage_file"; then
        echo "  Type: REPLACE (simple)" >&2
        # Simple REPLACE not implemented yet, just pass through
        cp "$current_dist" "$output_dist"
    else
        echo "  Type: Other (pass through)" >&2
        cp "$current_dist" "$output_dist"
    fi
}

# ============================================================================
# Main Processing
# ============================================================================

echo "Calculating biome percentages for each preset..."
echo

# Find all preset files
for preset_file in "$PRESET_DIR"/*.yml; do
    if [ ! -f "$preset_file" ]; then
        continue
    fi

    preset_name=$(basename "$preset_file" .yml)
    echo "Processing preset: $preset_name"

    # Extract source biomes
    source_biomes="${TEMP_DIR}/${preset_name}_source"
    extract_source_biomes "$preset_file" "$source_biomes"

    if [ ! -s "$source_biomes" ]; then
        echo "  No source biomes found, skipping"
        continue
    fi

    # Initialize distribution
    current_dist="${TEMP_DIR}/${preset_name}_dist"
    initialize_distribution "$source_biomes" "$current_dist"

    echo "  Initial distribution:"
    cat "$current_dist" | head -5

    # Extract and process stages
    stage_files="${TEMP_DIR}/${preset_name}_stages"
    extract_stage_files "$preset_file" "$stage_files"

    stage_num=0
    while IFS= read -r stage_file; do
        if [ "$stage_file" = "INLINE_REPLACE" ]; then
            echo "  Skipping inline stage"
            continue
        fi

        stage_num=$((stage_num + 1))
        next_dist="${TEMP_DIR}/${preset_name}_dist_${stage_num}"

        process_stage "$stage_file" "$current_dist" "$next_dist"

        current_dist="$next_dist"
    done < "$stage_files"

    # Save final distribution
    final_dist="${TEMP_DIR}/${preset_name}_final"
    cp "$current_dist" "$final_dist"

    echo "  Final distribution (top 10 biomes):"
    sort -t'|' -k2 -rn "$final_dist" | head -10
    echo
done

echo "Percentage calculation complete!"
echo "Results stored in: $TEMP_DIR"

# Clean up
# rm -rf "$TEMP_DIR"
