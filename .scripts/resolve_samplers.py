#!/usr/bin/env python3
"""
resolve_samplers.py

Resolves all sampler definitions from the math/ directory into a single YAML file
with all external references and inline variables resolved.

Key features:
- Resolves $file.yml:key.path and ${file.yml:key} inline variable references
- Evaluates constant mathematical expressions (e.g., "1 / 1000" -> 0.001)
- Orders shared samplers by dependency (dependencies first in output)
- Removes duplicate sub-sampler entries from 'samplers:' (plural) maps when
  they match pack-level sampler names (NoiseTool loads them sequentially so
  they're available via globalSamplers)
- Keeps 'sampler:' (singular) entries as full inline copies (wrapper types
  like FBM/CACHE load them directly)
- Completely overwrites the output file with only resolved content

Output format:
    samplers:
      namedSampler:
        ...
      dependentSampler:
        type: EXPRESSION
        expression: "namedSampler(x, z)"
        # namedSampler NOT duplicated here — found via globalSamplers
    functions:
      ...
"""
from ensure_module import ensure_modules
ensure_modules(["yaml", "re"])


# =============================================================================
# Configuration
# =============================================================================

# Default render scale factor for noise visualization/preview
# - Frequency values are MULTIPLIED by this factor (higher = more detail visible)
# - Amplitude values are DIVIDED by this factor (keeps proportions balanced)
# Set to 1.0 for no scaling (original values)
DEFAULT_RENDER_SCALE = 1.0

import yaml
import re
import sys
import ast
import copy
import json
import operator
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple, Union


# =============================================================================
# YAML Multiline String Representer (registered once, used everywhere)
# =============================================================================

def _represent_multiline_str(dumper, data):
    """Use block scalar style (|) for multiline strings in YAML output."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, _represent_multiline_str)


# =============================================================================
# Safe Mathematical Expression Evaluator
# =============================================================================

class ExpressionEvaluator:
    """
    Safely evaluates simple mathematical expressions like "1 / 1000" or "1-2*(150/1500)".

    Only supports:
    - Numbers (int, float)
    - Basic operators: +, -, *, /, ^, **
    - Parentheses
    - Unary minus

    Does NOT evaluate expressions containing:
    - Variables (x, y, z, etc.)
    - Function calls (sin, cos, etc.)
    - Multi-line expressions
    """

    # Allowed operators
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    @classmethod
    def is_evaluable_expression(cls, text: str) -> bool:
        """
        Check if a string looks like a simple mathematical expression that can be evaluated.

        Returns False for:
        - Multi-line strings (runtime expressions)
        - Strings containing letters (variables/functions)
        - Empty strings
        - Pure numbers (already evaluated)
        """
        if not text or not isinstance(text, str):
            return False

        # Skip multi-line expressions (these are runtime expressions)
        if '\n' in text:
            return False

        text = text.strip()

        # Skip empty strings
        if not text:
            return False

        # Check if it's already a pure number
        try:
            float(text)
            return False  # Already a number, no need to evaluate
        except ValueError:
            pass

        # Must contain at least one operator to be an expression
        if not any(op in text for op in ['+', '-', '*', '/', '^']):
            return False

        # Check for variable names or function calls (letters)
        # Allow 'e' and 'E' for scientific notation like 1e-5
        # Pattern: letters that aren't part of scientific notation
        cleaned = re.sub(r'\d+[eE][+-]?\d+', '', text)  # Remove scientific notation
        if re.search(r'[a-zA-Z_]', cleaned):
            return False

        return True

    @classmethod
    def evaluate(cls, text: str) -> Tuple[Optional[Union[int, float]], bool]:
        """
        Safely evaluate a mathematical expression.

        Returns (result, success) tuple.
        If evaluation fails or is not safe, returns (None, False).
        """
        if not cls.is_evaluable_expression(text):
            return None, False

        try:
            # Replace ^ with ** for Python evaluation
            expr = text.replace('^', '**')

            # Parse the expression into an AST
            tree = ast.parse(expr, mode='eval')

            # Evaluate the AST safely
            result = cls._eval_node(tree.body)

            # Round to avoid floating point artifacts (e.g., 0.0010000000000000002)
            if isinstance(result, float):
                # Round to 10 significant digits
                if result != 0:
                    magnitude = math.floor(math.log10(abs(result)))
                    result = round(result, 10 - int(magnitude) - 1)
                # Convert to int if it's a whole number
                if result == int(result):
                    result = int(result)

            return result, True

        except Exception:
            return None, False

    @classmethod
    def _eval_node(cls, node: ast.AST) -> Union[int, float]:
        """Recursively evaluate an AST node."""
        # Handle numeric constants (works in all Python 3.x versions)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

        # Python 3.7 compatibility: ast.Num was deprecated in 3.8, removed in 3.14
        if hasattr(ast, 'Num') and isinstance(node, ast.Num):
            return node.n

        if isinstance(node, ast.BinOp):
            left = cls._eval_node(node.left)
            right = cls._eval_node(node.right)
            op_func = cls.OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported operator: {type(node.op)}")
            return op_func(left, right)

        elif isinstance(node, ast.UnaryOp):
            operand = cls._eval_node(node.operand)
            op_func = cls.OPERATORS.get(type(node.op))
            if op_func is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op)}")
            return op_func(operand)

        elif isinstance(node, ast.Expression):
            return cls._eval_node(node.body)

        else:
            raise ValueError(f"Unsupported AST node type: {type(node)}")


class SamplerResolver:
    """
    Resolves sampler configurations by:
    1. Loading YAML files with anchors/aliases
    2. Resolving $file.yml:key.path references
    3. Resolving ${file.yml:key} inline variable references
    4. Evaluating constant mathematical expressions (e.g., "1 / 1000" -> 0.001)
    5. Converting salt values to floats (e.g., 694 -> 694.0)
    6. Merging all samplers into a single structure
    """

    # Keys that should NOT have their values evaluated (runtime expressions)
    EXPRESSION_KEYS = {'expression'}

    # Keys whose values should be converted to float (for proper type interpretation)
    FLOAT_KEYS = {'salt'}

    # Keys whose values should be MULTIPLIED by render scale
    FREQUENCY_KEYS = {'frequency', 'erosion-frequency'}

    # Keys whose values should be DIVIDED by render scale
    AMPLITUDE_KEYS = {'amplitude'}

    def __init__(self, base_dir: Path = Path("."), should_evaluate_constants: bool = True,
                 render_scale: float = 1.0):
        self.base_dir = base_dir
        self.should_evaluate_constants = should_evaluate_constants
        self.render_scale = render_scale
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
        # Errors encountered (deduplicated)
        self.errors: Set[str] = set()
        # Warnings encountered (deduplicated)
        self.warnings: Set[str] = set()
        # Count of evaluated expressions
        self.evaluated_count: int = 0

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
            self.errors.add(f"File not found: {full_path}")
            return None

        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                # Use safe_load which resolves anchors/aliases automatically
                data = yaml.safe_load(f)
                self.file_cache[cache_key] = data
                return data
        except yaml.YAMLError as e:
            self.errors.add(f"YAML error in {file_path}: {e}")
            return None
        except Exception as e:
            self.errors.add(f"Error reading {file_path}: {e}")
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
            self.errors.add(f"Circular reference detected: {ref}")
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
            self.errors.add(f"Key path '{key_path}' not found in {file_part}")
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
                    self.warnings.add(f"Complex value for inline reference ${{{ref}}}, using str()")
                    return str(value)
            else:
                self.warnings.add(f"Could not resolve inline reference ${{{ref}}}")
                return match.group(0)  # Keep original if unresolved

        return re.sub(pattern, replace_var, text)

    def deep_resolve(self, value: Any, depth: int = 0) -> Any:
        """
        Recursively resolve all references in a value.
        Handles dicts, lists, and string references.
        """
        if depth > 100:
            self.errors.add("Maximum recursion depth exceeded")
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

    def evaluate_constants(self, value: Any, parent_key: str = "", depth: int = 0) -> Any:
        """
        Recursively evaluate constant mathematical expressions in the data structure.

        Converts strings like "1 / 1000" to 0.001.
        Converts salt values to floats (e.g., 694 -> 694.0) for proper type interpretation.

        Skips evaluation for:
        - Multi-line strings (runtime expressions)
        - Values under 'expression' keys (runtime expressions)
        - Strings containing variable names (x, y, z, etc.)
        """
        if depth > 100:
            return value

        if isinstance(value, str):
            # Skip if this is under an 'expression' key (runtime expression)
            if parent_key in self.EXPRESSION_KEYS:
                return value

            # For salt keys, try to convert string numbers to float
            # This handles cases like "0694" which YAML keeps as a string
            if parent_key in self.FLOAT_KEYS:
                try:
                    return float(value)
                except ValueError:
                    pass  # Not a number, keep as string

            # Try to evaluate as a mathematical expression
            result, success = ExpressionEvaluator.evaluate(value)
            if success:
                self.evaluated_count += 1
                # If this is a salt key, ensure it's a float
                if parent_key in self.FLOAT_KEYS:
                    return float(result)
                return result

            return value

        elif isinstance(value, (int, float)):
            # Convert salt values to float to ensure proper type interpretation
            # This handles cases like salt: 0694 which YAML parses as int 694
            if parent_key in self.FLOAT_KEYS:
                return float(value)

            # Apply render scale to frequency values (multiply)
            if parent_key in self.FREQUENCY_KEYS and self.render_scale != 1.0:
                return value * self.render_scale

            # Apply render scale to amplitude values (divide)
            if parent_key in self.AMPLITUDE_KEYS and self.render_scale != 1.0:
                return value / self.render_scale

            return value

        elif isinstance(value, dict):
            result = {}
            for key, val in value.items():
                result[key] = self.evaluate_constants(val, parent_key=key, depth=depth + 1)
            return result

        elif isinstance(value, list):
            return [self.evaluate_constants(item, parent_key=parent_key, depth=depth + 1) for item in value]

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

    def collect_all_samplers(self, sampler_dir: Path = Path("math/samplers"), exclude: List[str] = None) -> Dict[str, Any]:
        """
        Collect and resolve all samplers from the sampler directory.

        Args:
            sampler_dir: Directory containing sampler files
            exclude: List of filenames to exclude (e.g., ['combined_climate.yml'])
        """
        if exclude is None:
            exclude = []

        full_dir = self.base_dir / sampler_dir
        if not full_dir.exists():
            self.errors.add(f"Sampler directory not found: {full_dir}")
            return {}

        print(f"Processing samplers from: {full_dir}", file=sys.stderr)
        if exclude:
            print(f"  Excluding: {', '.join(exclude)}", file=sys.stderr)

        for yml_file in sorted(full_dir.glob("*.yml")):
            # Skip excluded files
            if yml_file.name in exclude:
                print(f"  Skipping (excluded): {yml_file.name}", file=sys.stderr)
                continue

            rel_path = yml_file.relative_to(self.base_dir)
            print(f"  Processing: {rel_path}", file=sys.stderr)

            samplers = self.process_sampler_file(rel_path)
            for name, config in samplers.items():
                if name in self.all_samplers:
                    self.warnings.add(f"Duplicate sampler '{name}' found, overwriting")
                self.all_samplers[name] = config

        return self.all_samplers

    def collect_all_functions(self, functions_dir: Path = Path("math/functions")) -> Dict[str, Any]:
        """
        Collect and resolve all functions from the functions directory.
        """
        full_dir = self.base_dir / functions_dir
        if not full_dir.exists():
            self.warnings.add(f"Functions directory not found: {full_dir}")
            return {}

        print(f"Processing functions from: {full_dir}", file=sys.stderr)

        for yml_file in sorted(full_dir.glob("*.yml")):
            rel_path = yml_file.relative_to(self.base_dir)
            print(f"  Processing: {rel_path}", file=sys.stderr)

            functions = self.process_functions_file(rel_path)
            for name, config in functions.items():
                if name in self.all_functions:
                    self.warnings.add(f"Duplicate function '{name}' found, overwriting")
                self.all_functions[name] = config

        return self.all_functions


# =============================================================================
# Anchor/Alias Deduplication System
# =============================================================================

def _content_hash(config: Any) -> str:
    """Compute a deterministic content hash for a sampler config."""
    return json.dumps(config, sort_keys=True, default=str)


def _identify_shared_samplers(all_samplers: Dict[str, Any]) -> Set[str]:
    """
    Identify top-level samplers whose resolved content appears as nested
    sub-samplers inside other sampler trees. These will become anchors.
    """
    # Build hash -> name lookup for all top-level samplers
    hash_to_name: Dict[str, str] = {}
    for name, config in all_samplers.items():
        h = _content_hash(config)
        hash_to_name[h] = name

    shared: Set[str] = set()

    def walk(config: Any, owner_name: str):
        if not isinstance(config, dict):
            if isinstance(config, list):
                for item in config:
                    walk(item, owner_name)
            return

        # Check 'samplers' (plural) - named sub-samplers
        sub_samplers = config.get('samplers')
        if isinstance(sub_samplers, dict):
            for key, value in sub_samplers.items():
                if isinstance(value, dict):
                    h = _content_hash(value)
                    matched_name = hash_to_name.get(h)
                    if matched_name and matched_name != owner_name:
                        if value == all_samplers[matched_name]:
                            shared.add(matched_name)
                    walk(value, owner_name)

        # Check 'sampler' (singular) - wrapper types like CACHE, FBM
        sampler_val = config.get('sampler')
        if isinstance(sampler_val, dict):
            h = _content_hash(sampler_val)
            matched_name = hash_to_name.get(h)
            if matched_name:
                if sampler_val == all_samplers[matched_name]:
                    shared.add(matched_name)
            walk(sampler_val, owner_name)

        # Recurse into other dict values
        for key, value in config.items():
            if key not in ('samplers', 'sampler'):
                walk(value, owner_name)

    for name, config in all_samplers.items():
        walk(config, name)

    return shared


def _build_dependency_order(all_samplers: Dict[str, Any], shared: Set[str]) -> List[str]:
    """
    Topologically sort shared samplers (dependencies first), then append
    remaining samplers in their original order. YAML requires anchors to
    appear before their aliases.
    """
    # Build dependency graph among shared samplers
    hash_to_name: Dict[str, str] = {}
    for name in shared:
        h = _content_hash(all_samplers[name])
        hash_to_name[h] = name

    deps: Dict[str, Set[str]] = {name: set() for name in shared}

    def walk(config: Any, owner: str):
        if not isinstance(config, dict):
            if isinstance(config, list):
                for item in config:
                    walk(item, owner)
            return

        sub_samplers = config.get('samplers')
        if isinstance(sub_samplers, dict):
            for key, value in sub_samplers.items():
                if isinstance(value, dict):
                    h = _content_hash(value)
                    dep_name = hash_to_name.get(h)
                    if dep_name and dep_name != owner and value == all_samplers[dep_name]:
                        deps[owner].add(dep_name)
                    walk(value, owner)

        sampler_val = config.get('sampler')
        if isinstance(sampler_val, dict):
            h = _content_hash(sampler_val)
            dep_name = hash_to_name.get(h)
            if dep_name and dep_name != owner and sampler_val == all_samplers[dep_name]:
                deps[owner].add(dep_name)
            walk(sampler_val, owner)

        for key, value in config.items():
            if key not in ('samplers', 'sampler'):
                walk(value, owner)

    for name in shared:
        walk(all_samplers[name], name)

    # Topological sort
    result: List[str] = []
    visited: Set[str] = set()
    visiting: Set[str] = set()

    def visit(name: str):
        if name in visited:
            return
        if name in visiting:
            return  # Cycle - skip to avoid infinite loop
        visiting.add(name)
        for dep in deps.get(name, set()):
            visit(dep)
        visiting.discard(name)
        visited.add(name)
        result.append(name)

    for name in shared:
        visit(name)

    # Append non-shared samplers in original order
    for name in all_samplers:
        if name not in shared:
            result.append(name)

    return result



def _remove_global_sampler_refs(config: Any, all_sampler_names: Set[str],
                                 owner_name: str,
                                 errors: Optional[Set[str]] = None) -> Any:
    """
    Deep-walk a sampler config and remove entries from 'samplers:' (plural)
    maps that match pack-level sampler names. With sequential loading in
    DummyPack, these samplers are already available via globalSamplers, so
    EXPRESSION types will find them automatically.

    Only removes from 'samplers:' (plural) — 'sampler:' (singular) entries
    are kept as full inline copies because wrapper types (FBM, CACHE, etc.)
    load them directly from config, not via expression evaluation.

    Validates that removed samplers are referenced with coordinate arguments
    (e.g. name(x, z)) in the expression, not as bare names.
    """
    config = copy.deepcopy(config)

    def _find_bare_sampler_refs(expression: str, sampler_name: str) -> bool:
        """Check if sampler_name appears as a bare name (without parenthesized
        coordinate args) in the expression."""
        # Match the name NOT followed by '(' (with optional whitespace)
        pattern = r'(?<![a-zA-Z_0-9])' + re.escape(sampler_name) + r'(?!\s*\()(?![a-zA-Z_0-9])'
        return bool(re.search(pattern, expression))

    def walk(node: Any, context_name: str):
        if not isinstance(node, dict):
            if isinstance(node, list):
                for item in node:
                    walk(item, context_name)
            return

        expression = str(node.get('expression', '')) if 'expression' in node else ''

        # Remove matching entries from 'samplers' (plural)
        sub_samplers = node.get('samplers')
        if isinstance(sub_samplers, dict):
            keys_to_remove = []
            for key in sub_samplers:
                if key in all_sampler_names and key != owner_name:
                    # Validate: expression must use name(coords), not bare name
                    if expression and _find_bare_sampler_refs(expression, key):
                        if errors is not None:
                            errors.add(
                                f"Sampler '{context_name}': references '{key}' "
                                f"without coordinate arguments (e.g. {key}(x, z)). "
                                f"Pack-level samplers must be called with coordinates."
                            )
                    keys_to_remove.append(key)
                elif isinstance(sub_samplers[key], dict):
                    walk(sub_samplers[key], context_name)
            for key in keys_to_remove:
                del sub_samplers[key]

        # Keep 'sampler' (singular) as full inline copy — recurse into it
        sampler_val = node.get('sampler')
        if isinstance(sampler_val, dict):
            walk(sampler_val, context_name)

        # Recurse into other dict values
        for key, value in node.items():
            if key not in ('samplers', 'sampler'):
                if isinstance(value, dict):
                    walk(value, context_name)
                elif isinstance(value, list):
                    for item in value:
                        walk(item, context_name)

    walk(config, owner_name)
    return config


def _extract_function_calls(expression: str) -> Set[str]:
    """Extract all identifiers used as function calls in an expression string."""
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    return set(re.findall(pattern, expression))


def validate_expression_samplers(
    all_samplers: Dict[str, Any],
    all_functions: Dict[str, Any],
    errors: Set[str],
    warnings: Set[str],
) -> None:
    """
    Walk every sampler config tree and validate EXPRESSION-type nodes:

    Error:   a pack-level sampler name is called in the expression but is not
             declared in the node's local 'samplers:' section (Terra will fail
             to find it if loading order doesn't guarantee it's in globalSamplers
             at parse time).

    Warning: a local 'samplers:' entry is declared but never called in the
             expression (dead declaration).

    Identifiers that are user-defined functions (present in all_functions) are
    skipped so they don't produce false positives.  Identifiers that are neither
    in all_samplers nor all_functions are assumed to be built-ins (if, sin,
    abs, …) and are also silently ignored.
    """
    all_sampler_names: Set[str] = set(all_samplers.keys())
    all_function_names: Set[str] = set(all_functions.keys())

    def walk(node: Any, owner_name: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, owner_name)
            return
        if not isinstance(node, dict):
            return

        if node.get('type') == 'EXPRESSION' and 'expression' in node:
            expression = str(node['expression'])
            local_samplers = node.get('samplers') or {}
            if not isinstance(local_samplers, dict):
                local_samplers = {}
            local_names: Set[str] = set(local_samplers.keys())

            called = _extract_function_calls(expression)

            # Error: pack-level sampler called but not in local samplers:
            for identifier in called:
                if identifier in all_function_names:
                    continue  # user-defined function — not a sampler
                if identifier in all_sampler_names and identifier not in local_names:
                    errors.add(
                        f"Sampler '{owner_name}': expression calls '{identifier}(...)' "
                        f"but '{identifier}' is not declared in local samplers:"
                    )

            # Warning: local samplers: entry never called in expression
            for local_name in local_names:
                if local_name not in called:
                    warnings.add(
                        f"Sampler '{owner_name}': local sampler '{local_name}' is declared "
                        f"but not used in expression"
                    )

        # Recurse into all nested values
        for value in node.values():
            walk(value, owner_name)

    for name, config in all_samplers.items():
        walk(config, name)


def inject_dendry_defaults(all_samplers: Dict[str, Any]) -> int:
    """
    Walk all samplers and inject default properties for DENDRY type samplers.

    Adds 'cachepixels' set to the YAML alias *PerspectiveMultiplier if not
    already present.

    Returns the number of samplers modified.
    """
    # Sentinel value that will be replaced with an unquoted YAML alias in output
    PERSPECTIVE_ALIAS = "__ALIAS__PerspectiveMultiplier"
    count = 0

    for name, config in all_samplers.items():
        if isinstance(config, dict) and config.get('type') == 'DENDRY':
            if 'cachepixels' not in config:
                config['cachepixels'] = PERSPECTIVE_ALIAS
                count += 1

    return count


def build_resolved_output(all_samplers: Dict[str, Any],
                          errors: Optional[Set[str]] = None) -> str:
    """
    Build YAML output with shared samplers deduplicated.

    With NoiseTool's sequential loading (DummyPack loads pack-level samplers
    one at a time in dependency order), EXPRESSION types can reference other
    pack-level samplers by name via globalSamplers. This means sub-sampler
    entries in 'samplers:' (plural) that match pack-level names can be removed.

    'sampler:' (singular) entries are kept as full inline copies because wrapper
    types (FBM, CACHE, etc.) load them directly from config.
    """
    # Identify shared samplers and compute output order (dependencies first)
    shared = _identify_shared_samplers(all_samplers)
    ordered = _build_dependency_order(all_samplers, shared)
    all_names = set(all_samplers.keys())

    output_lines: List[str] = []

    for name in ordered:
        config = all_samplers[name]

        # Remove sub-sampler entries that match pack-level names
        config = _remove_global_sampler_refs(config, all_names, name, errors=errors)

        # Dump this sampler as YAML
        yaml_str = yaml.dump(
            {name: config},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120
        )

        # Indent for placement under 'samplers:' key
        lines = yaml_str.split('\n')
        indented = ['  ' + line if line.strip() else line for line in lines]
        output_lines.append('\n'.join(indented).rstrip())

    return '\n'.join(output_lines)


# =============================================================================
# Main Entry Point
# =============================================================================

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
    parser.add_argument(
        '--no-eval',
        action='store_true',
        help='Disable evaluation of constant expressions (keep as strings)'
    )
    parser.add_argument(
        '-s', '--render-scale',
        type=float,
        default=DEFAULT_RENDER_SCALE,
        help=f'Render scale factor: frequencies are multiplied, amplitudes are divided (default: {DEFAULT_RENDER_SCALE})'
    )
    parser.add_argument(
        '-x', '--exclude',
        type=str,
        action='append',
        default=[],
        help='Exclude sampler file(s) by name (can be used multiple times, e.g., -x combined_climate.yml -x other.yml)'
    )

    args = parser.parse_args()

    print("=" * 70, file=sys.stderr)
    print("Terra Sampler Resolver", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"Render scale: {args.render_scale}x", file=sys.stderr)
    if args.render_scale != 1.0:
        print(f"  - Frequencies will be multiplied by {args.render_scale}", file=sys.stderr)
        print(f"  - Amplitudes will be divided by {args.render_scale}", file=sys.stderr)

    # Initialize resolver
    should_evaluate = not args.no_eval
    resolver = SamplerResolver(
        base_dir=Path(args.base_dir),
        should_evaluate_constants=should_evaluate,
        render_scale=args.render_scale
    )

    # Collect and resolve everything
    print("\nCollecting samplers...", file=sys.stderr)
    resolver.collect_all_samplers(Path(args.sampler_dir), exclude=args.exclude)

    print("\nCollecting functions...", file=sys.stderr)
    resolver.collect_all_functions(Path(args.functions_dir))

    # Evaluate constant expressions
    if should_evaluate:
        print("\nEvaluating constant expressions...", file=sys.stderr)
        resolver.all_samplers = resolver.evaluate_constants(resolver.all_samplers)
        if resolver.all_functions:
            resolver.all_functions = resolver.evaluate_constants(resolver.all_functions)
        print(f"  Evaluated {resolver.evaluated_count} expressions", file=sys.stderr)

    # Inject DENDRY defaults (cachepixels)
    print("\nInjecting DENDRY defaults...", file=sys.stderr)
    dendry_count = inject_dendry_defaults(resolver.all_samplers)
    print(f"  Modified {dendry_count} DENDRY sampler(s)", file=sys.stderr)

    # Validate expression samplers (missing/unused local sampler declarations)
    print("\nValidating expression samplers...", file=sys.stderr)
    validate_expression_samplers(
        resolver.all_samplers,
        resolver.all_functions,
        resolver.errors,
        resolver.warnings,
    )

    # Build resolved sampler output
    print("\nBuilding resolved output...", file=sys.stderr)
    samplers_yaml = build_resolved_output(resolver.all_samplers, errors=resolver.errors)

    # Build functions section if present
    functions_yaml = ""
    if resolver.all_functions:
        functions_output = yaml.dump(
            {'functions': resolver.all_functions},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120
        )
        functions_yaml = '\n' + functions_output

    # Assemble complete output (overwrite entirely)
    final_output = 'samplers:\n' + samplers_yaml + functions_yaml

    # Replace DENDRY alias sentinels with unquoted YAML aliases
    # PyYAML may or may not quote the sentinel, so handle all cases
    final_output = final_output.replace("'__ALIAS__PerspectiveMultiplier'", '*PerspectiveMultiplier')
    final_output = final_output.replace('"__ALIAS__PerspectiveMultiplier"', '*PerspectiveMultiplier')
    final_output = final_output.replace('__ALIAS__PerspectiveMultiplier', '*PerspectiveMultiplier')

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_output)

    print(f"\nOutput written to: {output_path}", file=sys.stderr)
    print(f"  Total samplers: {len(resolver.all_samplers)}", file=sys.stderr)
    print(f"  Total functions: {len(resolver.all_functions)}", file=sys.stderr)

    # Report errors and warnings (convert sets to sorted lists)
    if resolver.errors:
        print(f"\n{'=' * 70}", file=sys.stderr)
        print("ERRORS:", file=sys.stderr)
        print("=" * 70, file=sys.stderr)
        for error in sorted(resolver.errors):
            print(f"  - {error}", file=sys.stderr)

    if resolver.warnings:
        print(f"\n{'-' * 70}", file=sys.stderr)
        print("WARNINGS:", file=sys.stderr)
        print("-" * 70, file=sys.stderr)
        for warning in sorted(resolver.warnings):
            print(f"  - {warning}", file=sys.stderr)

    # Exit with error code if there were errors
    if resolver.errors:
        sys.exit(1)

    print("\nDone!", file=sys.stderr)


if __name__ == "__main__":
    main()
