"""
Tool Registry — the core of the Tool Manager.

Provides:
    - ToolRegistry class: stores, discovers, and executes tools.
    - @tool decorator: register a function as a tool with its schema in one line.

Usage:
    from tools.registry import registry, tool

    @tool(description="Roll a dice", parameters={...})
    def roll_dice(sides: int = 6) -> int:
        return random.randint(1, sides)

    # In hello_ai.py:
    registry.schemas   # list of OpenAI-compatible tool schemas
    registry.execute("roll_dice", {"sides": 20})
"""

import json
from typing import Any, Callable


class ToolRegistry:
    """Central registry that manages all tool functions and their schemas."""

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._schemas: dict[str, dict] = {}

    # ── Registration ──────────────────────────────────────────────────

    def register(
        self,
        func: Callable,
        *,
        name: str | None = None,
        description: str,
        parameters: dict,
    ) -> Callable:
        """
        Register a callable as a tool.

        Args:
            func: The tool function.
            name: Override name (defaults to func.__name__).
            description: Human-readable description for the LLM.
            parameters: JSON-Schema style dict of the function's parameters.
        """
        tool_name = name or func.__name__

        if tool_name in self._tools:
            existing = self._tools[tool_name]
            # If it's a completely different function, reject collision
            if existing is not func and existing.__name__ != func.__name__:
                raise ValueError(
                    f"Tool '{tool_name}' is already registered. "
                    "Use a unique function name or pass name= to the @tool decorator."
                )

        self._tools[tool_name] = func
        self._schemas[tool_name] = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": parameters,
                    "required": [],
                },
            },
        }
        return func

    # ── Properties ────────────────────────────────────────────────────

    @property
    def schemas(self) -> list[dict]:
        """Return all tool schemas as a list (OpenAI / Ollama compatible)."""
        return list(self._schemas.values())

    @property
    def tool_names(self) -> list[str]:
        """Return sorted list of registered tool names."""
        return sorted(self._tools.keys())

    @property
    def count(self) -> int:
        """Number of registered tools."""
        return len(self._tools)

    # ── Execution ─────────────────────────────────────────────────────

    def execute(self, name: str, arguments: dict | str = None) -> str:
        """
        Execute a tool by name with the given arguments.

        Args:
            name: Registered tool name.
            arguments: Dict or JSON string of keyword arguments.

        Returns:
            str: Tool result as a string, or JSON error on failure.
        """
        func = self._tools.get(name)
        if not func:
            return json.dumps({"error": f"Tool '{name}' not found."})

        # Normalize arguments
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except Exception:
                arguments = {}
        elif arguments is None:
            arguments = {}

        try:
            return str(func(**arguments))
        except Exception as e:
            return json.dumps({"error": str(e)})

    # ── Utilities ─────────────────────────────────────────────────────

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def __repr__(self) -> str:
        return f"ToolRegistry({self.count} tools: {', '.join(self.tool_names)})"


# ── Singleton registry ────────────────────────────────────────────────
registry = ToolRegistry()


# ── @tool decorator ──────────────────────────────────────────────────
def tool(*, description: str, parameters: dict, name: str | None = None):
    """
    Decorator to register a function as a tool.

    Usage:
        @tool(
            description="Roll a dice with N sides",
            parameters={
                "sides": {
                    "type": "integer",
                    "description": "Number of sides on the die. Defaults to 6.",
                }
            },
        )
        def roll_dice(sides: int = 6) -> int:
            return random.randint(1, sides)
    """
    def decorator(func: Callable) -> Callable:
        registry.register(func, name=name, description=description, parameters=parameters)
        return func
    return decorator
