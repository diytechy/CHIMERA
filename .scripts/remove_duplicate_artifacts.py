"""
Find and remove duplicate artifacts across all YAML config directories.

Scans biomes/, features/, palettes/, and structures/ for YAML files with
duplicate 'id' fields WITHIN the same artifact type. Cross-type duplicates
(e.g., a BIOME and PALETTE sharing an ID) are intentional and ignored.

Usage:
    python remove_duplicate_artifacts.py          # dry run (report only)
    python remove_duplicate_artifacts.py --delete  # actually remove duplicates
"""

import yaml
import sys
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path("C:/Projects/ORIGEN2")

# Each entry: (directory, artifact type label)
# These are scanned independently so cross-type ID sharing is allowed.
ARTIFACT_SOURCES = [
    (PROJECT_ROOT / "biomes",     "BIOME"),
    (PROJECT_ROOT / "features",   "FEATURE"),
    (PROJECT_ROOT / "palettes",   "PALETTE"),
    (PROJECT_ROOT / "structures", "STRUCTURE"),
]

dry_run = "--delete" not in sys.argv


def scan_directory(directory: Path, label: str):
    """Scan a directory tree for YAML files and group by id."""
    by_id = defaultdict(list)
    if not directory.exists():
        return by_id

    for yml_file in directory.rglob("*.yml"):
        try:
            with open(yml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                if data and isinstance(data, dict) and 'id' in data:
                    artifact_id = data['id']
                    file_size = yml_file.stat().st_size
                    by_id[artifact_id].append((yml_file, file_size))
        except Exception:
            pass

    return by_id


def process_duplicates(by_id: dict, label: str) -> int:
    """Find and optionally remove duplicates. Returns count of duplicates."""
    dup_count = 0

    for artifact_id, files in sorted(by_id.items()):
        if len(files) <= 1:
            continue

        # Sort by size descending — keep largest
        files.sort(key=lambda x: x[1], reverse=True)
        dup_count += len(files) - 1
        print(f"\n  {artifact_id}: {len(files)} files")

        for i, (file_path, size) in enumerate(files):
            rel = file_path.relative_to(PROJECT_ROOT)
            if i == 0:
                print(f"    KEEP:   {rel} ({size} bytes)")
            else:
                print(f"    DELETE: {rel} ({size} bytes)")
                if not dry_run:
                    file_path.unlink()

    return dup_count


def main():
    if dry_run:
        print("=== DRY RUN (pass --delete to actually remove files) ===\n")
    else:
        print("=== DELETING DUPLICATES ===\n")

    total_dupes = 0

    for directory, label in ARTIFACT_SOURCES:
        print(f"--- {label} ({directory.relative_to(PROJECT_ROOT)}/) ---")
        by_id = scan_directory(directory, label)
        dupes = process_duplicates(by_id, label)

        if dupes == 0:
            print("  No duplicates found.")
        total_dupes += dupes

    print(f"\n{'=' * 50}")
    print(f"Total duplicates: {total_dupes}")
    if dry_run and total_dupes > 0:
        print("Run with --delete to remove them.")


if __name__ == "__main__":
    main()
