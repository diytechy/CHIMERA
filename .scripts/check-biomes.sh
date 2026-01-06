#!/bin/bash

# ============================================================================
# check-biomes.sh
# Validates biome configurations and generates SuggestedImprovements.md
#
# Checks performed:
#   1. YAML syntax validation (linting)
#   2. Missing color key validation
#   3. Color reference mismatch validation
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_FILE="$REPO_ROOT/SuggestedImprovements.md"

cd "$REPO_ROOT"

# ============================================================================
# YAML Linting
# ============================================================================

# Arrays to collect YAML syntax errors
declare -a yaml_error_files=()
declare -a yaml_error_messages=()

# Determine which Python command to use
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
fi

# Check if Python with yaml module is available
yaml_lint_available=false
yaml_lint_skip_reason=""

if [[ -z "$PYTHON_CMD" ]]; then
    yaml_lint_skip_reason="Python is not installed"
else
    if $PYTHON_CMD -c "import yaml" 2>/dev/null; then
        yaml_lint_available=true
    else
        # Python exists but PyYAML is missing - offer to install
        echo ""
        echo "[WARNING] PyYAML module is not installed."
        echo ""

        # Check if we're in an interactive terminal
        if [[ -t 0 ]]; then
            read -p "Would you like to install PyYAML now? (y/N): " install_choice
            if [[ "$install_choice" =~ ^[Yy]$ ]]; then
                echo "Installing PyYAML..."
                if $PYTHON_CMD -m pip install pyyaml 2>&1; then
                    echo "PyYAML installed successfully!"
                    yaml_lint_available=true
                else
                    echo "[ERROR] Failed to install PyYAML."
                    echo "  Try manually: $PYTHON_CMD -m pip install pyyaml"
                    yaml_lint_skip_reason="PyYAML installation failed"
                fi
            else
                yaml_lint_skip_reason="PyYAML not installed (user declined)"
            fi
        else
            # Non-interactive mode - just show instructions
            yaml_lint_skip_reason="PyYAML module not installed"
            echo "  To enable YAML linting, run:"
            echo "    $PYTHON_CMD -m pip install pyyaml"
            echo ""
        fi
    fi
fi

if [[ "$yaml_lint_available" == true ]]; then
    echo "Running YAML lint check..."

    # Find all YAML files in the repository (excluding hidden folders)
    all_yaml_files="$(find . -name "*.yml" -not -path "*/.*" | sort)"

    for yaml_file in $all_yaml_files; do
        # Use Python to validate YAML syntax
        error_output=$($PYTHON_CMD -c "
import yaml
import sys
try:
    with open('$yaml_file', 'r') as f:
        yaml.safe_load(f)
except yaml.YAMLError as e:
    # Extract just the error message without the full traceback
    error_msg = str(e).split('\n')[0]
    print(error_msg)
    sys.exit(1)
except Exception as e:
    print(str(e))
    sys.exit(1)
" 2>&1)

        if [[ $? -ne 0 ]]; then
            yaml_error_files+=("$yaml_file")
            # Clean up error message for markdown table
            clean_error=$(echo "$error_output" | tr '\n' ' ' | sed 's/|/\\|/g')
            yaml_error_messages+=("$clean_error")
        fi
    done

    yaml_error_count=${#yaml_error_files[@]}
    echo "  YAML files checked: $(echo "$all_yaml_files" | wc -w)"
    echo "  Syntax errors found: $yaml_error_count"
else
    echo "[WARNING] YAML linting skipped - $yaml_lint_skip_reason"
    yaml_error_count=0
fi

# ============================================================================
# Biome Color Validation
# ============================================================================

biome_config_paths="$(find biomes/*/ -name "*.yml" -not -path "biomes/abstract/*" | sort)"

# Arrays to collect issues
declare -a missing_color_files=()
declare -a mismatch_files=()
declare -a mismatch_ids=()
declare -a mismatch_colors=()

color_key='color: \$biomes/colors.yml:'

for path in $biome_config_paths
do
    # Check if this is actually a biome file
    if ! grep -q "type: BIOME" "$path" 2>/dev/null; then
        continue
    fi

    config_id_line="$(grep -m1 'id: ' "$path")"
    config_id="${config_id_line#id: }"
    config_id="$(echo "$config_id" | tr -d '\r')"

    color_line="$(grep -m1 'color: ' "$path")"
    color_id="${color_line#$color_key}"
    color_id="$(echo "$color_id" | tr -d '\r')"

    if [[ $color_line != *$color_key* ]]; then
        missing_color_files+=("$path")
    elif [[ $color_id != $config_id ]]; then
        mismatch_files+=("$path")
        mismatch_ids+=("$config_id")
        mismatch_colors+=("$color_id")
    fi
done

# Count issues
missing_count=${#missing_color_files[@]}
mismatch_count=${#mismatch_files[@]}
total_count=$((yaml_error_count + missing_count + mismatch_count))

# Generate SuggestedImprovements.md
cat > "$OUTPUT_FILE" << 'HEADER'
# Suggested Improvements

This document lists configuration issues found during the biome validation audit. These should be reviewed and addressed to ensure consistency across all biome definitions.

HEADER

echo "## Summary" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"
echo "| Issue Type | Count |" >> "$OUTPUT_FILE"
echo "|------------|-------|" >> "$OUTPUT_FILE"
echo "| YAML syntax errors | $yaml_error_count |" >> "$OUTPUT_FILE"
echo "| Missing valid color key | $missing_count |" >> "$OUTPUT_FILE"
echo "| Color reference mismatch | $mismatch_count |" >> "$OUTPUT_FILE"
echo "| **Total** | **$total_count** |" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

if [[ $total_count -eq 0 ]]; then
    echo "No issues found. All configurations are valid." >> "$OUTPUT_FILE"
    echo "SuggestedImprovements.md generated: 0 issues found"
    exit 0
fi

echo "---" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# YAML syntax errors section
if [[ $yaml_error_count -gt 0 ]]; then
    echo "## YAML Syntax Errors" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "These files contain YAML syntax errors that must be fixed:" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "| File | Error |" >> "$OUTPUT_FILE"
    echo "|------|-------|" >> "$OUTPUT_FILE"

    for i in "${!yaml_error_files[@]}"; do
        echo "| \`${yaml_error_files[$i]}\` | ${yaml_error_messages[$i]} |" >> "$OUTPUT_FILE"
    done

    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
fi

# Missing color keys section
if [[ $missing_count -gt 0 ]]; then
    echo "## Missing Valid Color Key" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "These biome files do not contain a valid color key (expected format: \`color: \$biomes/colors.yml:BIOME_ID\`):" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "| File | Action Required |" >> "$OUTPUT_FILE"
    echo "|------|-----------------|" >> "$OUTPUT_FILE"

    for file in "${missing_color_files[@]}"; do
        echo "| \`$file\` | Add color key |" >> "$OUTPUT_FILE"
    done

    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
fi

# Color mismatch section
if [[ $mismatch_count -gt 0 ]]; then
    echo "## Color Reference Mismatches" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "These biome files have a color reference that does not match the biome ID:" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "| File | Biome ID | Current Color Reference |" >> "$OUTPUT_FILE"
    echo "|------|----------|------------------------|" >> "$OUTPUT_FILE"

    for i in "${!mismatch_files[@]}"; do
        echo "| \`${mismatch_files[$i]}\` | ${mismatch_ids[$i]} | ${mismatch_colors[$i]} |" >> "$OUTPUT_FILE"
    done

    echo "" >> "$OUTPUT_FILE"
    echo "---" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
fi

# Recommendations
cat >> "$OUTPUT_FILE" << 'RECOMMENDATIONS'
## Recommendations

### For YAML Syntax Errors
Fix the syntax errors in the listed files. Common issues include:
- Incorrect indentation (YAML uses spaces, not tabs)
- Missing colons after keys
- Unquoted special characters
- Duplicate keys

### For Missing Color Keys
Add a color definition to each biome file in the format:
```yaml
color: $biomes/colors.yml:BIOME_ID
```
And ensure the corresponding color is defined in `biomes/colors.yml`.

### For Color Reference Mismatches
Two options:
1. **Option A**: Update the color reference to match the biome ID and add the new color to `biomes/colors.yml`
2. **Option B**: If intentionally reusing another biome's color, this may be acceptable for map visualization

---

*Generated by check-biomes.sh*
RECOMMENDATIONS

# Console output
echo "SuggestedImprovements.md generated: $total_count issues found"
echo "  - YAML syntax errors: $yaml_error_count"
echo "  - Missing color key: $missing_count"
echo "  - Color mismatch: $mismatch_count"

# Exit with warning (0) since issues are documented, not blocking error
exit 0
