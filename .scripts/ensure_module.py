import importlib
import subprocess
import sys

def ensure_module(module_name, package_name=None):
    """
    Ensures a Python module is installed.

    module_name: name used in `import`
    package_name: name used in `pip install` (if different)
    """
    package_name = package_name or module_name

    try:
        return importlib.import_module(module_name)
    except ImportError:
        print(f"Module '{module_name}' is not installed.")

        choice = input(f"Do you want to install '{package_name}' now? [y/N]: ").strip().lower()
        if choice != "y":
            print("Installation skipped. Exiting.")
            sys.exit(1)

        print(f"Installing '{package_name}'...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        except subprocess.CalledProcessError:
            print(f"Failed to install '{package_name}'.")
            sys.exit(1)

        try:
            return importlib.import_module(module_name)
        except ImportError:
            print(f"Module '{module_name}' still cannot be imported after installation.")
            sys.exit(1)
        
def ensure_modules(modules):
    """
    Accepts a list of module names and returns a dict
    mapping module_name -> imported module object.
    """
    loaded = {}
    for name in modules:
        loaded[name] = ensure_module(name)
    return loaded
