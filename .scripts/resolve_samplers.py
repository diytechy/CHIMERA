#!/usr/bin/env python3
"""
resolve_samplers.py

Resolves all sampler definitions from the math/ directory into a single YAML file
with all external references, YAML anchors/aliases, and inline variables resolved.

This creates a self-contained sampler configuration file that can be used for
independent evaluation without any external file dependencies.

Output format:
    type: EXPRESSION
    expression: y
    samplers:
      <all resolved samplers>
"""
from ensure_module import ensure_modules
ensure_modules(["yaml", "re"])

import yaml
import re
import sys
import copy
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple
from collections import OrderedDict


class SamplerResolver:
    """
    Resolves sampler configurations by:
    1. Loading YAML files with anchors/aliases
    2. Resolving $file.yml:key.path references
    3. Resolving ${file.yml:key} inline variable references
    4. Merging all samplers into a single structure
    """

    def __init__(self, base_dir: Path = Path(".")):
        self.base_dir = base_dir
        # Cache of loaded YAML files (raw, with anchors resolved by PyYAML)
        self.file_cache: Dict[str, Dict] = {}
        # Cache of resolved values to avoid infinite recursion
        self.resolution_cache: Dict[str, Any] = {}
        # Track files currently being resolved (for cycle detection)
        self.resolution_stack: Set[str] = set()
        # Collected samplers
        self.all_samplers: Dict[str, Any] = {}
        # Collected functions
        self.all_functions: Dict[str, Any] = {}
        # Errors encountered
        self.errors: List[str] = []
        # Warnings encountered
        self.warnings: List[str] = []

    def load_yaml_file(self, file_path: Path) -> Optional[Dict]:
        """
        Load a YAML file, resolving anchors and aliases.
        Returns the parsed YAML data or None if loading fails.
        """
        cache_key = str(file_path)
        if cache_key in self.file_cache:
            return self.file_cache[cache_key]

        full_path = self.base_dir / file_path
        if not full_path.exists():
            self.errors.append(f"File not found: {full_path}")
            return None

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                # Use safe_load which resolves anchors/aliases automatically
                data = yaml.safe_load(f)
                self.file_cache[cache_key] = data
                return data
        except yaml.YAMLError as e:
            self.errors.append(f"YAML error in {file_path}: {e}")
            return None
        except Exception as e:
            self.errors.append(f"Error reading {file_path}: {e}")
            return None

    def get_value_at_path(self, data: Any, key_path: str) -> Tuple[Any, bool]:
        """
        Navigate to a value in nested dict/list structure using dot-notation path.
        Returns (value, success) tuple.
        """
        if not key_path:
            return data, True

        parts = key_path.split('.')
        current = data

        for part in parts:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    return None, False
            elif isinstance(current, list):
                try:
                    index = int(part)
                    current = current[index]
                except (ValueError, IndexError):
                    return None, False
            else:
                return None, False

        return current, True

    def resolve_file_reference(self, ref: str) -> Tuple[Any, bool]:
        """
        Resolve a file reference like '$math/samplers/elevation.yml:samplers.elevation'
        Returns (resolved_value, success) tuple.
        """
        # Check cache first
        if ref in self.resolution_cache:
            return self.resolution_cache[ref], True

        # Check for cycles
        if ref in self.resolution_stack:
            self.errors.append(f"Circular reference detected: {ref}")
            return None, False

        # Parse the reference
        # Format: $file/path.yml:key.path or file/path.yml:key.path (for << merge)
        ref_clean = ref.lstrip('$')

        if ':' in ref_clean:
            file_part, key_path = ref_clean.split(':', 1)
        else:
            file_part = ref_clean
            key_path = ""

        # Load the file
        file_path = Path(file_part)
        data = self.load_yaml_file(file_path)
        if data is None:
            return None, False

        # Navigate to the key path
        value, success = self.get_value_at_path(data, key_path)
        if not success:
            self.errors.append(f"Key path '{key_path}' not found in {file_part}")
            return None, False

        # Mark as being resolved
        self.resolution_stack.add(ref)

        # Deep resolve the value (recursively resolve any nested references)
        try:
            resolved = self.deep_resolve(value)
            self.resolution_cache[ref] = resolved
            return resolved, True
        finally:
            self.resolution_stack.discard(ref)

    def resolve_inline_variables(self, text: str) -> str:
        """
        Resolve inline variable references like ${customization.yml:global-scale}
        in expression strings.
        """
        # Pattern for ${file.yml:key} or ${file.yml:key-with-dashes}
        pattern = r'\$\{([^}]+)\}'

        def replace_var(match):
            ref = match.group(1)
            value, success = self.resolve_file_reference('$' + ref)
            if success and value is not None:
                # Convert to string representation for embedding in expression
                if isinstance(value, (int, float)):
                    return str(value)
                elif isinstance(value, str):
                    return value
                else:
                    self.warnings.append(f"Complex value for inline reference ${{{ref}}}, using str()")
                    return str(value)
            else:
                self.warnings.append(f"Could not resolve inline reference ${{{ref}}}")
                return match.group(0)  # Keep original if unresolved

        return re.sub(pattern, replace_var, text)

    def deep_resolve(self, value: Any, depth: int = 0) -> Any:
        """
        Recursively resolve all references in a value.
        Handles dicts, lists, and string references.
        """
        if depth > 100:
            self.errors.append("Maximum recursion depth exceeded")
            return value

        if isinstance(value, str):
            # First check for inline variables in expressions (${...} pattern)
            # This must come BEFORE the file reference check because ${...} also starts with $
            if '${' in value:
                return self.resolve_inline_variables(value)

            # Check if it's a pure file reference ($file.yml:key pattern)
            # Only matches if it starts with $ and doesn't have { immediately after
            if value.startswith('$') and not value.startswith('${'):
                resolved, success = self.resolve_file_reference(value)
                if success:
                    return resolved
                else:
                    return value  # Keep unresolved reference

            return value

        elif isinstance(value, dict):
            result = {}

            # Handle merge key (<<) first
            if '<<' in value:
                merge_source = value['<<']
                if isinstance(merge_source, str):
                    # File reference for merge
                    resolved, success = self.resolve_file_reference(merge_source)
                    if success and isinstance(resolved, dict):
                        result.update(self.deep_resolve(resolved, depth + 1))
                elif isinstance(merge_source, list):
                    # List of references to merge
                    for item in merge_source:
                        if isinstance(item, str):
                            resolved, success = self.resolve_file_reference(item)
                            if success and isinstance(resolved, dict):
                                result.update(self.deep_resolve(resolved, depth + 1))
                        elif isinstance(item, dict):
                            result.update(self.deep_resolve(item, depth + 1))
                elif isinstance(merge_source, dict):
                    # Already resolved dict (from YAML alias)
                    result.update(self.deep_resolve(merge_source, depth + 1))

            # Process remaining keys
            for key, val in value.items():
                if key == '<<':
                    continue  # Already handled

                resolved_val = self.deep_resolve(val, depth + 1)
                result[key] = resolved_val

            return result

        elif isinstance(value, list):
            return [self.deep_resolve(item, depth + 1) for item in value]

        else:
            return value

    def process_sampler_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a single sampler file and extract all samplers.
        Returns dict of sampler_name -> resolved_sampler_config.
        """
        data = self.load_yaml_file(file_path)
        if data is None:
            return {}

        samplers = {}

        # Extract samplers section
        if 'samplers' in data and isinstance(data['samplers'], dict):
            for name, config in data['samplers'].items():
                # Skip YAML anchors that start with & (they're just markers)
                resolved = self.deep_resolve(config)
                samplers[name] = resolved

        return samplers

    def process_functions_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a functions file and extract all function definitions.
        """
        data = self.load_yaml_file(file_path)
        if data is None:
            return {}

        functions = {}

        # Extract functions section
        if 'functions' in data and isinstance(data['functions'], dict):
            for name, config in data['functions'].items():
                resolved = self.deep_resolve(config)
                functions[name] = resolved

        return functions

    def collect_all_samplers(self, sampler_dir: Path = Path("math/samplers")) -> Dict[str, Any]:
        """
        Collect and resolve all samplers from the sampler directory.
        """
        full_dir = self.base_dir / sampler_dir
        if not full_dir.exists():
            self.errors.append(f"Sampler directory not found: {full_dir}")
            return {}

        print(f"Processing samplers from: {full_dir}", file=sys.stderr)

        for yml_file in sorted(full_dir.glob("*.yml")):
            rel_path = yml_file.relative_to(self.base_dir)
            print(f"  Processing: {rel_path}", file=sys.stderr)

            samplers = self.process_sampler_file(rel_path)
            for name, config in samplers.items():
                if name in self.all_samplers:
                    self.warnings.append(f"Duplicate sampler '{name}' found, overwriting")
                self.all_samplers[name] = config

        return self.all_samplers

    def collect_all_functions(self, functions_dir: Path = Path("math/functions")) -> Dict[str, Any]:
        """
        Collect and resolve all functions from the functions directory.
        """
        full_dir = self.base_dir / functions_dir
        if not full_dir.exists():
            self.warnings.append(f"Functions directory not found: {full_dir}")
            return {}

        print(f"Processing functions from: {full_dir}", file=sys.stderr)

        for yml_file in sorted(full_dir.glob("*.yml")):
            rel_path = yml_file.relative_to(self.base_dir)
            print(f"  Processing: {rel_path}", file=sys.stderr)

            functions = self.process_functions_file(rel_path)
            for name, config in functions.items():
                if name in self.all_functions:
                    self.warnings.append(f"Duplicate function '{name}' found, overwriting")
                self.all_functions[name] = config

        return self.all_functions

    def build_resolved_output(self) -> Dict[str, Any]:
        """
        Build the final resolved output structure.
        """
        # Collect all samplers and functions
        self.collect_all_samplers()
        self.collect_all_functions()

        # Build output structure
        output = {
            'type': 'EXPRESSION',
            'expression': 'y',
            'samplers': self.all_samplers,
        }

        # Only include functions if we found any
        if self.all_functions:
            output['functions'] = self.all_functions

        return output

    def generate_yaml_output(self, output: Dict[str, Any]) -> str:
        """
        Generate YAML string output with proper formatting.
        """
        # Custom representer for multiline strings
        def str_representer(dumper, data):
            if '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)

        yaml.add_representer(str, str_representer)

        return yaml.dump(
            output,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120
        )


def represent_ordereddict(dumper, data):
    """Custom representer to maintain key order in YAML output."""
    return dumper.represent_mapping('tag:yaml.org,2002:map', data.items())


yaml.add_representer(OrderedDict, represent_ordereddict)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Resolve all sampler definitions into a single YAML file'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='.artifacts/resolved_samplers.yml',
        help='Output file path (default: .artifacts/resolved_samplers.yml)'
    )
    parser.add_argument(
        '-b', '--base-dir',
        type=str,
        default='.',
        help='Base directory for resolving paths (default: current directory)'
    )
    parser.add_argument(
        '--sampler-dir',
        type=str,
        default='math/samplers',
        help='Directory containing sampler files (default: math/samplers)'
    )
    parser.add_argument(
        '--functions-dir',
        type=str,
        default='math/functions',
        help='Directory containing function files (default: math/functions)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    print("=" * 70, file=sys.stderr)
    print("Terra Sampler Resolver", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    # Initialize resolver
    resolver = SamplerResolver(base_dir=Path(args.base_dir))

    # Collect and resolve everything
    print("\nCollecting samplers...", file=sys.stderr)
    resolver.collect_all_samplers(Path(args.sampler_dir))

    print("\nCollecting functions...", file=sys.stderr)
    resolver.collect_all_functions(Path(args.functions_dir))

    # Build output
    output = {
        'type': 'EXPRESSION',
        'expression': 'y',
        'samplers': resolver.all_samplers,
    }
    if resolver.all_functions:
        output['functions'] = resolver.all_functions

    # Generate YAML
    yaml_output = resolver.generate_yaml_output(output)

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_output)

    print(f"\nOutput written to: {output_path}", file=sys.stderr)
    print(f"  Total samplers: {len(resolver.all_samplers)}", file=sys.stderr)
    print(f"  Total functions: {len(resolver.all_functions)}", file=sys.stderr)

    # Report errors and warnings
    if resolver.errors:
        print(f"\n{'=' * 70}", file=sys.stderr)
        print("ERRORS:", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for error in resolver.errors:
            print(f"  - {error}", file=sys.stderr)

    if resolver.warnings:
        print(f"\n{'-' * 70}", file=sys.stderr)
        print("WARNINGS:", file=sys.stderr)
        print("-" * 70, file=sys.stderr)
        for warning in resolver.warnings:
            print(f"  - {warning}", file=sys.stderr)

    # Exit with error code if there were errors
    if resolver.errors:
        sys.exit(1)

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
