#!/usr/bin/env python3
"""
resolve_samplers.py

Resolves all sampler definitions from the math/ directory into a single YAML file
with all external references and inline variables resolved.

Key features:
- Preserves the header section of the output file (expressions, comments, custom samplers)
- Retains YAML anchors (&name) and aliases (*name) for CACHE sampler compatibility
- Only replaces the resolved samplers section, keeping user customizations

Output format:
    type: EXPRESSION
    expression: <user's test expression>
    #expression: <commented alternatives>
    samplers:
      <custom test samplers with anchors>
      <resolved samplers from math/>
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
import operator
import math
from pathlib import Path
from typing import Dict, Any, Optional, List, Set, Tuple, Union
from collections import OrderedDict


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
        # Errors encountered
        self.errors: List[str] = []
        # Warnings encountered
        self.warnings: List[str] = []
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
            self.errors.append(f"Sampler directory not found: {full_dir}")
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


class HeaderPreserver:
    """
    Preserves the header section of the output file, including:
    - type: EXPRESSION
    - expression lines (active and commented)
    - Custom test samplers defined before the resolved samplers
    """

    HEADER_END_MARKER = "# --- RESOLVED SAMPLERS BELOW ---"

    @classmethod
    def read_existing_header(cls, file_path: Path) -> Tuple[str, Dict[str, Any]]:
        """
        Read the existing output file and extract:
        1. The header text (everything before samplers: or the marker)
        2. Custom samplers defined in the header section

        Returns (header_text, custom_samplers_dict)
        """
        if not file_path.exists():
            return cls._default_header(), {}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception:
            return cls._default_header(), {}

        # Try to find the marker first
        if cls.HEADER_END_MARKER in content:
            parts = content.split(cls.HEADER_END_MARKER)
            header_text = parts[0].rstrip() + '\n'
            # Parse custom samplers from header
            custom_samplers = cls._extract_custom_samplers(header_text)
            return header_text, custom_samplers

        # Otherwise, find where "samplers:" section starts and extract header
        lines = content.split('\n')
        header_lines = []
        in_header = True
        custom_sampler_lines = []
        found_samplers = False
        brace_depth = 0

        for i, line in enumerate(lines):
            # Check if we've hit the samplers section at root level
            if line.startswith('samplers:') and not found_samplers:
                found_samplers = True
                header_lines.append(line)
                continue

            if not found_samplers:
                header_lines.append(line)
            elif found_samplers and in_header:
                # Collect custom samplers (indented content after samplers:)
                # Stop when we hit a sampler that looks like it came from math/
                # (i.e., known samplers like continents, elevation, etc.)
                stripped = line.strip()

                # Check if this looks like a resolved sampler (not a custom test sampler)
                # Custom samplers typically have names like cell_test, biome_place, etc.
                # Resolved samplers have names like continents, elevation, temperature, etc.
                if stripped and not stripped.startswith('#'):
                    # Check if it's a sampler definition (name: or name: &anchor)
                    match = re.match(r'^  ([a-zA-Z_][a-zA-Z0-9_-]*):(\s*&\w+)?(\s|$)', line)
                    if match:
                        sampler_name = match.group(1)
                        # Known resolved sampler names from math/
                        resolved_names = {
                            'continents', 'continentsCached', 'continentBorder',
                            'elevation', 'elevationCached', 'elevationDetailed',
                            'flatness', 'flatnessCached', 'rawFlatness',
                            'rawElevation', 'oceanElevation', 'oceanElevationCached',
                            'temperature', 'temperatureCached', 'rawTemperature',
                            'precipitation', 'precipitationCached', 'rawPrecipitation',
                            'spawnIsland', 'spawnIslandCached',
                            'spotDistance', 'spotRadius', 'spotAngle', 'spotSizePercent',
                            'spotBaseElevation', 'spotEdgeRadiusPercent',
                            'riverMask', 'riverTerrainErosion',
                            'largeSpotDistance', 'largeSpotRadius', 'largeSpotAngle',
                        }
                        if sampler_name in resolved_names:
                            # We've hit the resolved samplers section, stop collecting header
                            in_header = False
                            continue

                if in_header:
                    custom_sampler_lines.append(line)

        # Build header text
        header_text = '\n'.join(header_lines)
        if custom_sampler_lines:
            header_text += '\n' + '\n'.join(custom_sampler_lines)

        # Parse custom samplers
        custom_samplers = cls._extract_custom_samplers(header_text)

        return header_text.rstrip() + '\n', custom_samplers

    @classmethod
    def _extract_custom_samplers(cls, header_text: str) -> Dict[str, Any]:
        """Extract custom sampler definitions from header text."""
        try:
            # Use a YAML loader that preserves structure
            data = yaml.safe_load(header_text)
            if data and isinstance(data, dict) and 'samplers' in data:
                return data['samplers']
        except Exception:
            pass
        return {}

    @classmethod
    def _default_header(cls) -> str:
        """Return a default header if no existing file."""
        return """type: EXPRESSION
#expression: elevation(x, z)
#expression: continents(x, z)
#expression: temperature(x, z)
expression: y

samplers:
"""


class AnchorAwareYAMLDumper(yaml.SafeDumper):
    """
    Custom YAML dumper that preserves anchors for CACHE sampler compatibility.

    When a sampler is referenced by a CACHE sampler via anchor/alias,
    this dumper will output the anchor on the source sampler and
    use an alias reference in the CACHE sampler.
    """

    def __init__(self, *args, anchored_samplers: Set[str] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.anchored_samplers = anchored_samplers or set()
        self.written_anchors = set()


def build_anchor_aware_output(samplers: Dict[str, Any], custom_samplers: Dict[str, Any] = None) -> str:
    """
    Build YAML output that preserves anchors for CACHE sampler references.

    For each CACHE sampler that references another sampler via 'sampler' key,
    we need to:
    1. Add an anchor (&name) to the referenced sampler
    2. Use an alias (*name) in the CACHE sampler's 'sampler' field
    """
    # Identify which samplers are referenced by CACHE samplers
    cache_targets = {}  # Maps target sampler name -> anchor name

    for name, config in samplers.items():
        if isinstance(config, dict) and config.get('type') == 'CACHE':
            # Look for sampler reference - it might be a dict (inlined) or should be an anchor
            sampler_ref = config.get('sampler')
            if isinstance(sampler_ref, dict):
                # The sampler was inlined during resolution
                # We need to find which sampler this corresponds to
                # Check if there's a "Cached" suffix pattern
                if name.endswith('Cached'):
                    base_name = name[:-6]  # Remove 'Cached' suffix
                    if base_name in samplers:
                        cache_targets[base_name] = base_name

    # Also check custom samplers for CACHE patterns
    if custom_samplers:
        for name, config in custom_samplers.items():
            if isinstance(config, dict) and config.get('type') == 'CACHE':
                if name.endswith('Cached'):
                    base_name = name[:-6]
                    if base_name in custom_samplers:
                        cache_targets[base_name] = base_name

    # Build output lines with proper anchors
    output_lines = []

    # Custom string representer for multiline
    def represent_str(dumper, data):
        if '\n' in data:
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    yaml.add_representer(str, represent_str)

    # Helper to dump a sampler with optional anchor
    def dump_sampler(name: str, config: Any, add_anchor: bool = False) -> str:
        """Dump a single sampler definition, optionally with an anchor."""
        if isinstance(config, dict) and config.get('type') == 'CACHE':
            # Special handling for CACHE samplers - use alias reference
            base_name = name[:-6] if name.endswith('Cached') else None
            if base_name and base_name in cache_targets:
                # Create a modified config with alias reference
                cache_config = dict(config)
                # We'll manually write the alias reference
                lines = [f"  {name}:"]
                lines.append(f"    dimensions: {cache_config.get('dimensions', 2)}")
                lines.append(f"    type: CACHE")
                lines.append(f"    sampler: *{base_name}")
                return '\n'.join(lines)

        # Regular sampler - dump with optional anchor
        yaml_str = yaml.dump({name: config}, default_flow_style=False, allow_unicode=True,
                           sort_keys=False, width=120)

        if add_anchor:
            # Add anchor after the sampler name
            # "  name:" -> "  name: &name"
            yaml_str = yaml_str.replace(f"{name}:", f"{name}: &{name}", 1)

        # Indent properly (samplers are under 'samplers:' key)
        lines = yaml_str.split('\n')
        indented = ['  ' + line if line.strip() else line for line in lines]
        return '\n'.join(indented).rstrip()

    # Output custom samplers first (with anchors if needed)
    if custom_samplers:
        for name, config in custom_samplers.items():
            needs_anchor = name in cache_targets
            output_lines.append(dump_sampler(name, config, add_anchor=needs_anchor))

    # Output resolved samplers (with anchors if needed)
    for name, config in samplers.items():
        # Skip if this is a duplicate of a custom sampler
        if custom_samplers and name in custom_samplers:
            continue
        needs_anchor = name in cache_targets
        output_lines.append(dump_sampler(name, config, add_anchor=needs_anchor))

    return '\n'.join(output_lines)


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

    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing header and custom samplers from output file
    print("\nReading existing header...", file=sys.stderr)
    header_text, custom_samplers = HeaderPreserver.read_existing_header(output_path)
    print(f"  Found {len(custom_samplers)} custom samplers in header", file=sys.stderr)

    # Evaluate constant expressions in resolved samplers
    if should_evaluate:
        print("\nEvaluating constant expressions...", file=sys.stderr)
        resolver.all_samplers = resolver.evaluate_constants(resolver.all_samplers)
        if resolver.all_functions:
            resolver.all_functions = resolver.evaluate_constants(resolver.all_functions)
        print(f"  Evaluated {resolver.evaluated_count} expressions", file=sys.stderr)

    # Count CACHE samplers for reporting
    print("\nBuilding anchor-aware output...", file=sys.stderr)
    cache_count = sum(1 for name, config in resolver.all_samplers.items()
                     if isinstance(config, dict) and config.get('type') == 'CACHE')
    print(f"  Found {cache_count} CACHE samplers", file=sys.stderr)

    # Build functions section if present
    functions_yaml = ""
    if resolver.all_functions:
        # Custom string representer for multiline
        def represent_str(dumper, data):
            if '\n' in data:
                return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
            return dumper.represent_scalar('tag:yaml.org,2002:str', data)
        yaml.add_representer(str, represent_str)

        functions_output = yaml.dump(
            {'functions': resolver.all_functions},
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
            width=120
        )
        functions_yaml = '\n' + functions_output

    # Combine: header + marker + resolved samplers + functions
    #
    # IMPORTANT: header_text already contains custom samplers (before the marker).
    # samplers_yaml should ONLY contain the resolved samplers from math/samplers/,
    # NOT the custom samplers again. So we pass custom_samplers=None to avoid duplication.
    #
    # Rebuild samplers_yaml WITHOUT custom samplers to avoid duplication
    samplers_yaml = build_anchor_aware_output(resolver.all_samplers, custom_samplers=None)

    final_output = header_text
    if not header_text.rstrip().endswith('samplers:'):
        # Add samplers: key if not already in header
        if 'samplers:' not in header_text:
            final_output += '\nsamplers:\n'

    final_output += HeaderPreserver.HEADER_END_MARKER + '\n'
    final_output += samplers_yaml
    final_output += functions_yaml

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(final_output)

    print(f"\nOutput written to: {output_path}", file=sys.stderr)
    print(f"  Total samplers: {len(resolver.all_samplers)}", file=sys.stderr)
    print(f"  Total functions: {len(resolver.all_functions)}", file=sys.stderr)
    print(f"  Custom samplers preserved: {len(custom_samplers)}", file=sys.stderr)

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
