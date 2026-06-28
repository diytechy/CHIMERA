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
ensure_modules(["yaml"])  # re is stdlib; no bootstrap needed


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
# Duplicate-anchor-tolerant YAML loader
# =============================================================================

from yaml.events import AliasEvent


class DuplicateAnchorSafeLoader(yaml.SafeLoader):
    """SafeLoader that tolerates duplicate YAML anchors (last definition wins).

    Terra is parsed by SnakeYAML (Java), which lets an anchor be (re)defined more than
    once -- later aliases resolve to the most recent definition. PyYAML's SafeLoader
    instead raises ComposerError on the second definition, which aborts the WHOLE file.
    In this tool that surfaced as a silently dropped file (load_yaml_file caught the error
    and returned None), so every sampler in e.g. spots.yml vanished from the output. This
    loader restores SnakeYAML's last-wins behaviour.
    """

    def compose_node(self, parent, index):
        # Only intervene on an anchor *definition* (not an alias use): forget any earlier
        # node registered under this anchor so the base composer won't raise; it then
        # registers the new (last) node. Alias events are left untouched so they still
        # resolve to whatever anchor is currently registered.
        if not self.check_event(AliasEvent):
            event = self.peek_event()
            if event is not None and event.anchor is not None:
                self.anchors.pop(event.anchor, None)
        return super().compose_node(parent, index)


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
                # DuplicateAnchorSafeLoader resolves anchors/aliases and, unlike safe_load,
                # tolerates duplicate anchors (last wins) the way Terra's SnakeYAML does --
                # otherwise one duplicate anchor would drop every sampler in the file.
                data = yaml.load(f, Loader=DuplicateAnchorSafeLoader)
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

    def _process_section(self, file_path: Path, section: str) -> Dict[str, Any]:
        """Load a file and deep-resolve every entry under the given top-level section.

        Shared by samplers ('samplers') and functions ('functions'), which previously had
        two identical copies of this. Returns {name: resolved_config}.
        """
        data = self.load_yaml_file(file_path)
        if data is None:
            return {}
        entries = data.get(section)
        if not isinstance(entries, dict):
            return {}
        return {name: self.deep_resolve(config) for name, config in entries.items()}

    def process_sampler_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single sampler file -> {sampler_name: resolved_config}."""
        return self._process_section(file_path, 'samplers')

    def process_functions_file(self, file_path: Path) -> Dict[str, Any]:
        """Process a single functions file -> {function_name: resolved_config}."""
        return self._process_section(file_path, 'functions')

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


def _iter_sampler_nodes(config: Any):
    """Depth-first iterator over every dict node in a sampler-config tree.

    Replaces the hand-rolled recursive walk(...) that several functions used to each
    duplicate. Because every dict node is yielded, a caller that inspects each node's own
    'samplers'/'sampler' entries covers exactly the same nodes the old recursion did.
    """
    if isinstance(config, dict):
        yield config
        for value in config.values():
            yield from _iter_sampler_nodes(value)
    elif isinstance(config, list):
        for item in config:
            yield from _iter_sampler_nodes(item)


def _identify_shared_samplers(all_samplers: Dict[str, Any]) -> Set[str]:
    """
    Identify top-level samplers whose resolved content appears as nested
    sub-samplers inside other sampler trees. These will become anchors.
    """
    # Build hash -> name lookup for all top-level samplers
    hash_to_name: Dict[str, str] = {_content_hash(c): n for n, c in all_samplers.items()}

    shared: Set[str] = set()

    for owner_name, config in all_samplers.items():
        for node in _iter_sampler_nodes(config):
            # 'samplers' (plural): named sub-samplers (a self-reference is not "shared")
            sub_samplers = node.get('samplers')
            if isinstance(sub_samplers, dict):
                for value in sub_samplers.values():
                    if isinstance(value, dict):
                        matched_name = hash_to_name.get(_content_hash(value))
                        if matched_name and matched_name != owner_name \
                                and value == all_samplers[matched_name]:
                            shared.add(matched_name)
            # 'sampler' (singular): wrapper types like CACHE, FBM (self-reference allowed)
            sampler_val = node.get('sampler')
            if isinstance(sampler_val, dict):
                matched_name = hash_to_name.get(_content_hash(sampler_val))
                if matched_name and sampler_val == all_samplers[matched_name]:
                    shared.add(matched_name)

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

    def _matched_dep(value: Any, owner: str) -> Optional[str]:
        if not isinstance(value, dict):
            return None
        dep_name = hash_to_name.get(_content_hash(value))
        if dep_name and dep_name != owner and value == all_samplers[dep_name]:
            return dep_name
        return None

    for owner in shared:
        for node in _iter_sampler_nodes(all_samplers[owner]):
            sub_samplers = node.get('samplers')
            if isinstance(sub_samplers, dict):
                for value in sub_samplers.values():
                    dep_name = _matched_dep(value, owner)
                    if dep_name:
                        deps[owner].add(dep_name)
            dep_name = _matched_dep(node.get('sampler'), owner)
            if dep_name:
                deps[owner].add(dep_name)

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

    def _has_bare_ref(expression: str, sampler_name: str) -> bool:
        """True if sampler_name appears as a bare name (no parenthesized coord args)."""
        pattern = r'(?<![a-zA-Z_0-9])' + re.escape(sampler_name) + r'(?!\s*\()(?![a-zA-Z_0-9])'
        return bool(re.search(pattern, expression))

    # Deleting matched keys from a node's 'samplers' dict only mutates that child dict, not
    # the node's own key set, so it is safe to do while iterating _iter_sampler_nodes; the
    # iterator then descends into the surviving (non-removed) sub-samplers, as before. Only
    # 'samplers' (plural) entries are removed -- 'sampler' (singular) wrappers are kept inline.
    for node in _iter_sampler_nodes(config):
        sub_samplers = node.get('samplers')
        if not isinstance(sub_samplers, dict):
            continue
        expression = str(node.get('expression', ''))
        for key in [k for k in sub_samplers if k in all_sampler_names and k != owner_name]:
            if expression and _has_bare_ref(expression, key) and errors is not None:
                errors.add(
                    f"Sampler '{owner_name}': references '{key}' without coordinate "
                    f"arguments (e.g. {key}(x, z)). Pack-level samplers must be called "
                    f"with coordinates."
                )
            del sub_samplers[key]

    return config


# Built-in functions provided by Terra's expression engine. An identifier called in an
# expression that is neither a sampler (pack-level or local), a function (global or local),
# nor one of these built-ins is treated as genuinely undefined.
EXPRESSION_BUILTINS: Set[str] = {
    'if',
    'abs', 'sign', 'signum',
    'floor', 'ceil', 'ceiling', 'round', 'trunc', 'rint',
    'min', 'max', 'mod', 'fma', 'hypot',
    'pow', 'sqrt', 'cbrt', 'exp', 'expm1', 'log', 'log10', 'log1p', 'ln',
    'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
    'sinh', 'cosh', 'tanh', 'toRadians', 'toDegrees',
}


def _extract_function_calls(expression: str) -> Set[str]:
    """Extract all identifiers used as function calls in an expression string.

    Comments are stripped first (/* block */, // line, and # line) so that words inside
    explanatory comments in multi-line expressions are not mistaken for function calls
    (e.g. a comment mentioning "bank (0)" must not register a call to 'bank').
    """
    expression = re.sub(r'/\*.*?\*/', ' ', expression, flags=re.DOTALL)
    expression = re.sub(r'//[^\n]*', ' ', expression)
    expression = re.sub(r'#[^\n]*', ' ', expression)
    pattern = r'\b([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    return set(re.findall(pattern, expression))


def validate_expression_samplers(
    all_samplers: Dict[str, Any],
    all_functions: Dict[str, Any],
    errors: Set[str],
    warnings: Set[str],
) -> None:
    """
    Walk every sampler config tree and validate EXPRESSION-type nodes.

    For each node, the identifiers that may legitimately be called are: pack-level samplers
    (resolved at runtime via globalSamplers, regardless of local declaration), global
    functions, the node's OWN local 'samplers:'/'functions:' entries, and the expression
    built-ins (if, floor, min, …).

    Error:   an identifier is called that is none of the above -- a genuinely undefined name
             (typically a typo). Calling a known pack-level sampler bare (without a local
             'samplers:' declaration) is NOT an error -- it is the normal globalSamplers
             pattern used throughout the pack.

    Warning: a local 'samplers:' entry is declared but never called (dead declaration).
    """
    all_sampler_names: Set[str] = set(all_samplers.keys())
    all_function_names: Set[str] = set(all_functions.keys())

    for owner_name, config in all_samplers.items():
        for node in _iter_sampler_nodes(config):
            if node.get('type') != 'EXPRESSION' or 'expression' not in node:
                continue

            expression = str(node['expression'])
            local_samplers = node.get('samplers')
            local_functions = node.get('functions')
            local_sampler_names: Set[str] = (
                set(local_samplers.keys()) if isinstance(local_samplers, dict) else set()
            )
            local_function_names: Set[str] = (
                set(local_functions.keys()) if isinstance(local_functions, dict) else set()
            )
            called = _extract_function_calls(expression)

            in_scope = (
                all_sampler_names | all_function_names
                | local_sampler_names | local_function_names | EXPRESSION_BUILTINS
            )

            # Error: a called identifier resolves to nothing known (likely a typo).
            for identifier in called:
                if identifier not in in_scope:
                    errors.add(
                        f"Sampler '{owner_name}': expression calls '{identifier}(...)' which is "
                        f"not a known sampler, function, or built-in"
                    )

            # Warning: a local samplers: entry is declared but never called.
            for local_name in local_sampler_names:
                if local_name not in called:
                    warnings.add(
                        f"Sampler '{owner_name}': local sampler '{local_name}' is declared "
                        f"but not used in expression"
                    )


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
