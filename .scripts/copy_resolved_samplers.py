#!/usr/bin/env python3
"""
Copy matching samplers from RESOLVED section to INSERT section in resolved_samplers.yml.

This script reads the resolved_samplers.yml file and:
1. Finds ALL empty/placeholder sampler entries in the INSERT section
   (after '--- INSERT COPIES OF MATCHING SAMPLERS HERE ---')
2. Finds ALL samplers with existing content in the INSERT section that have a match
   in the RESOLVED section
3. Finds matching samplers anywhere in the RESOLVED section
   (after '--- RESOLVED SAMPLERS BELOW ---')
4. Copies/updates the resolved sampler content into the INSERT section, adjusting indentation
"""

import re
import argparse
from pathlib import Path


def find_section_markers(lines: list[str]) -> tuple[int, int]:
    """Find the line numbers of INSERT and RESOLVED markers."""
    insert_line = None
    resolved_line = None

    for i, line in enumerate(lines):
        if '--- INSERT COPIES OF MATCHING SAMPLERS HERE ---' in line:
            insert_line = i
        elif '--- RESOLVED SAMPLERS BELOW ---' in line:
            resolved_line = i

    if insert_line is None:
        raise ValueError("Could not find INSERT marker in file")
    if resolved_line is None:
        raise ValueError("Could not find RESOLVED marker in file")

    return insert_line, resolved_line


def get_indent_level(line: str) -> int:
    """Get the number of leading spaces in a line."""
    return len(line) - len(line.lstrip())


def is_empty_sampler(lines: list[str], line_idx: int, indent: int) -> bool:
    """
    Check if a sampler definition is empty or just a placeholder.
    A sampler is empty if the next non-empty line is at same or lower indent,
    or if it only contains the key with no value.
    """
    # Check if this line is just "name:" with nothing after
    line = lines[line_idx]
    stripped = line.strip()

    # If there's content after the colon (other than comment), not empty
    after_colon = stripped.split(':', 1)[1].strip() if ':' in stripped else ''
    if after_colon and not after_colon.startswith('#'):
        return False

    # Look at next non-empty line
    for i in range(line_idx + 1, len(lines)):
        next_line = lines[i]
        next_stripped = next_line.strip()

        if not next_stripped or next_stripped.startswith('#'):
            continue

        next_indent = get_indent_level(next_line)

        # If next content is at same or lower indent, this sampler is empty
        if next_indent <= indent:
            return True
        # If next content is indented more, sampler has content
        return False

    # Reached end of file - empty
    return True


def find_sampler_end(lines: list[str], start_line: int, indent: int) -> int:
    """
    Find the end line of a sampler definition starting at start_line with given indent.
    Returns the line index where this sampler ends (exclusive).
    """
    for j in range(start_line + 1, len(lines)):
        line = lines[j]
        stripped = line.strip()

        if not stripped or stripped.startswith('#'):
            continue

        line_indent = get_indent_level(line)
        if line_indent <= indent:
            return j

    return len(lines)


def find_empty_samplers_in_insert(lines: list[str], insert_line: int, resolved_line: int) -> list[tuple[str, int, int]]:
    """
    Find all TOP-LEVEL empty sampler placeholders in the INSERT section.
    Returns list of (sampler_name, line_index, indent_level).

    Only matches samplers at the expected top-level indent (typically 2 spaces for
    samplers directly under the 'samplers:' key). This avoids matching nested
    samplers inside other sampler definitions.
    """
    empty_samplers = []

    # Pattern to match sampler names (word followed by colon)
    sampler_pattern = re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*):\s*(#.*)?$')

    # First, find the expected indent level for top-level samplers
    # Look for the 'samplers:' key after INSERT marker
    expected_indent = None
    for i in range(insert_line + 1, resolved_line):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('samplers:'):
            # Top-level samplers should be indented one level more than 'samplers:'
            samplers_indent = get_indent_level(line)
            expected_indent = samplers_indent + 2  # Assuming 2-space indentation
            break

    if expected_indent is None:
        # Fallback: assume top-level samplers are at indent 2
        expected_indent = 2

    for i in range(insert_line + 1, resolved_line):
        line = lines[i]
        match = sampler_pattern.match(line)

        if match:
            indent = len(match.group(1))
            name = match.group(2)

            # Only match top-level samplers at the expected indent
            if indent != expected_indent:
                continue

            # Skip certain keywords that aren't samplers
            if name in ('type', 'dimensions', 'expression', 'variables', 'functions',
                       'samplers', 'sampler', 'arguments', 'salt', 'frequency',
                       'octaves', 'gain', 'lacunarity', 'amplitude', 'warp',
                       'x', 'y', 'z', 'return', 'jitter', 'distance'):
                continue

            if is_empty_sampler(lines, i, indent):
                empty_samplers.append((name, i, indent))

    return empty_samplers


def find_existing_samplers_in_insert(lines: list[str], insert_line: int, resolved_line: int) -> list[tuple[str, int, int, int]]:
    """
    Find all TOP-LEVEL samplers with existing content in the INSERT section.
    Returns list of (sampler_name, start_line_index, end_line_index, indent_level).

    Only matches samplers at the expected top-level indent (typically 2 spaces for
    samplers directly under the 'samplers:' key). This avoids matching nested
    samplers inside other sampler definitions.
    """
    existing_samplers = []

    # Pattern to match sampler names (word followed by colon)
    sampler_pattern = re.compile(r'^(\s*)([a-zA-Z_][a-zA-Z0-9_]*):\s*(#.*)?$')

    # First, find the expected indent level for top-level samplers
    # Look for the 'samplers:' key after INSERT marker
    expected_indent = None
    for i in range(insert_line + 1, resolved_line):
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith('samplers:'):
            # Top-level samplers should be indented one level more than 'samplers:'
            samplers_indent = get_indent_level(line)
            expected_indent = samplers_indent + 2  # Assuming 2-space indentation
            break

    if expected_indent is None:
        # Fallback: assume top-level samplers are at indent 2
        expected_indent = 2

    # Track which lines are "owned" by already-found samplers to avoid nested matches
    skip_until_line = -1

    for i in range(insert_line + 1, resolved_line):
        # Skip lines that are part of an already-found sampler
        if i < skip_until_line:
            continue

        line = lines[i]
        match = sampler_pattern.match(line)

        if match:
            indent = len(match.group(1))
            name = match.group(2)

            # Only match top-level samplers at the expected indent
            if indent != expected_indent:
                continue

            # Skip certain keywords that aren't samplers
            if name in ('type', 'dimensions', 'expression', 'variables', 'functions',
                       'samplers', 'sampler', 'arguments', 'salt', 'frequency',
                       'octaves', 'gain', 'lacunarity', 'amplitude', 'warp',
                       'x', 'y', 'z', 'return', 'jitter', 'distance'):
                continue

            # Only include samplers that have content (not empty)
            if not is_empty_sampler(lines, i, indent):
                end_line = find_sampler_end(lines, i, indent)
                # Make sure end_line doesn't exceed the resolved section marker
                end_line = min(end_line, resolved_line)
                existing_samplers.append((name, i, end_line, indent))
                # Skip all lines within this sampler to avoid matching nested content
                skip_until_line = end_line

    return existing_samplers


def find_resolved_sampler_any_indent(lines: list[str], sampler_name: str, resolved_line: int) -> tuple[int, int, int] | None:
    """
    Find a sampler in the RESOLVED section at any indent level.
    Returns (start_line, end_line, source_indent) or None if not found.
    Searches for the sampler as a direct child of any 'samplers:' section.
    """
    # Look for the sampler name as a key
    target_pattern = re.compile(rf'^(\s*){re.escape(sampler_name)}:\s*(#.*)?$')

    for i in range(resolved_line + 1, len(lines)):
        match = target_pattern.match(lines[i])
        if match:
            source_indent = len(match.group(1))
            start_line = i

            # Find end of this sampler (next line at same or lower indent with content)
            for j in range(start_line + 1, len(lines)):
                line = lines[j]
                stripped = line.strip()

                if not stripped or stripped.startswith('#'):
                    continue

                line_indent = get_indent_level(line)
                if line_indent <= source_indent:
                    return start_line, j, source_indent

            return start_line, len(lines), source_indent

    return None


def get_sampler_content(lines: list[str], start_line: int, end_line: int) -> list[str]:
    """Extract sampler content lines."""
    return lines[start_line:end_line]


def adjust_indentation(content_lines: list[str], source_indent: int, target_indent: int) -> list[str]:
    """Adjust indentation of content lines from source to target level."""
    indent_diff = target_indent - source_indent
    result = []

    for line in content_lines:
        if not line.strip():  # Empty or whitespace-only line
            result.append(line)
        else:
            current_indent = get_indent_level(line)
            new_indent = max(0, current_indent + indent_diff)
            result.append(' ' * new_indent + line.lstrip())

    return result


def copy_resolved_samplers(input_path: str, output_path: str = None, dry_run: bool = False) -> dict[str, str]:
    """
    Main function to copy resolved samplers into the INSERT section.

    Args:
        input_path: Path to resolved_samplers.yml
        output_path: Path to write output (defaults to input_path)
        dry_run: If True, just report what would be done without writing

    Returns:
        Dict mapping sampler names to status ('copied', 'updated', 'not_found', 'no_match')
    """
    if output_path is None:
        output_path = input_path

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find markers
    insert_line, resolved_line = find_section_markers(lines)
    print(f"INSERT marker at line {insert_line + 1}")
    print(f"RESOLVED marker at line {resolved_line + 1}")

    # Find all empty samplers in the INSERT section
    empty_samplers = find_empty_samplers_in_insert(lines, insert_line, resolved_line)

    print(f"\nFound {len(empty_samplers)} empty sampler placeholders in INSERT section:")
    for name, line_idx, indent in empty_samplers:
        print(f"  - {name} (line {line_idx + 1}, indent {indent})")

    # Find all existing (non-empty) samplers in the INSERT section
    existing_samplers = find_existing_samplers_in_insert(lines, insert_line, resolved_line)

    print(f"\nFound {len(existing_samplers)} existing samplers in INSERT section:")
    for name, start_idx, end_idx, indent in existing_samplers:
        print(f"  - {name} (lines {start_idx + 1}-{end_idx}, indent {indent})")

    results = {}
    replacements = []

    # Process empty samplers (copy from RESOLVED)
    for sampler_name, line_idx, target_indent in empty_samplers:
        resolved = find_resolved_sampler_any_indent(lines, sampler_name, resolved_line)

        if resolved is None:
            print(f"\n  {sampler_name}: NOT FOUND in RESOLVED section")
            results[sampler_name] = 'not_found'
            continue

        resolved_start, resolved_end, source_indent = resolved
        print(f"\n  {sampler_name}: found at lines {resolved_start + 1}-{resolved_end} (indent {source_indent})")

        # Get resolved content
        resolved_content = get_sampler_content(lines, resolved_start, resolved_end)

        # Adjust indentation from source to target
        adjusted_content = adjust_indentation(resolved_content, source_indent, target_indent)

        # Replace just the single placeholder line with full content
        replacements.append((line_idx, line_idx + 1, adjusted_content))
        results[sampler_name] = 'copied'

    # Process existing samplers (update from RESOLVED if match found)
    for sampler_name, start_idx, end_idx, target_indent in existing_samplers:
        resolved = find_resolved_sampler_any_indent(lines, sampler_name, resolved_line)

        if resolved is None:
            print(f"\n  {sampler_name}: no match in RESOLVED section (keeping existing)")
            results[sampler_name] = 'no_match'
            continue

        resolved_start, resolved_end, source_indent = resolved
        print(f"\n  {sampler_name}: UPDATING from lines {resolved_start + 1}-{resolved_end} (indent {source_indent})")

        # Get resolved content
        resolved_content = get_sampler_content(lines, resolved_start, resolved_end)

        # Adjust indentation from source to target
        adjusted_content = adjust_indentation(resolved_content, source_indent, target_indent)

        # Replace the existing sampler content with resolved content
        replacements.append((start_idx, end_idx, adjusted_content))
        results[sampler_name] = 'updated'

    if dry_run:
        print("\n--- DRY RUN - No changes written ---")
        return results

    # Apply replacements in reverse order to maintain line numbers
    replacements.sort(key=lambda x: x[0], reverse=True)

    for start, end, content in replacements:
        lines[start:end] = content

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    print(f"\nWrote output to: {output_path}")
    return results


def main():
    parser = argparse.ArgumentParser(
        description='Copy resolved samplers into INSERT section of resolved_samplers.yml'
    )
    parser.add_argument(
        'input_file',
        nargs='?',
        default='.artifacts/resolved_samplers.yml',
        help='Input file path (default: .artifacts/resolved_samplers.yml)'
    )
    parser.add_argument(
        '-o', '--output',
        help='Output file path (default: same as input)'
    )
    parser.add_argument(
        '-n', '--dry-run',
        action='store_true',
        help='Show what would be done without making changes'
    )

    args = parser.parse_args()

    # Resolve paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    input_path = Path(args.input_file)
    if not input_path.is_absolute():
        input_path = project_root / input_path

    output_path = args.output
    if output_path:
        output_path = Path(output_path)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        output_path = str(output_path)

    results = copy_resolved_samplers(str(input_path), output_path, args.dry_run)

    # Summary
    print("\n=== SUMMARY ===")
    copied = sum(1 for v in results.values() if v == 'copied')
    updated = sum(1 for v in results.values() if v == 'updated')
    not_found = sum(1 for v in results.values() if v == 'not_found')
    no_match = sum(1 for v in results.values() if v == 'no_match')
    print(f"Copied: {copied}")
    print(f"Updated: {updated}")
    print(f"Not found (empty placeholders): {not_found}")
    print(f"No match (existing kept): {no_match}")

    if not_found > 0:
        print("\nEmpty samplers not found in RESOLVED section:")
        for name, status in results.items():
            if status == 'not_found':
                print(f"  - {name}")

    if updated > 0:
        print("\nSamplers updated from RESOLVED section:")
        for name, status in results.items():
            if status == 'updated':
                print(f"  - {name}")


if __name__ == '__main__':
    main()
