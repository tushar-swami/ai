"""
Tools Package — Auto-discovery of all tool modules.

How it works:
    1. On import, scans this directory for *_tools.py files.
    2. Imports each file, which triggers the @tool decorators inside.
    3. The decorators auto-register each tool into the shared registry.

Usage in hello_ai.py:
    from tools import registry
    registry.schemas       # list of OpenAI-compatible schemas
    registry.execute(...)  # run a tool by name
    registry.tool_names    # list of registered tool names

Adding a new tool:
    1. Create a new file like tools/weather_tools.py
    2. Use the @tool decorator on your function
    3. Done — it's auto-discovered on next import
"""

import importlib
import pkgutil

from tools.registry import registry, tool  # noqa: F401 — re-export for convenience

# ── Auto-discover and import all *_tools.py modules in this package ──
_package_path = __path__
_package_name = __name__

for _finder, _module_name, _is_pkg in pkgutil.iter_modules(_package_path):
    if _module_name.endswith("_tools"):
        importlib.import_module(f"{_package_name}.{_module_name}")
