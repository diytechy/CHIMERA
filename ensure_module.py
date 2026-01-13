"""Minimal ensure_module shim for local test runs.

This provides ensure_modules(mod_names) used by the generator script. It
attempts to import each module and returns a dict of module name -> module
object (or None on failure). This avoids failing the script when running in
an environment where that helper isn't available.
"""
import sys
import importlib
import traceback

def ensure_modules(mod_names):
    results = {}
    for name in mod_names:
        try:
            results[name] = importlib.import_module(name)
        except Exception:
            # Print a warning but don't raise; calling code typically imports
            # the modules explicitly afterward.
            print(f"Warning: could not import module '{name}':", file=sys.stderr)
            traceback.print_exc()
            results[name] = None
    return results
