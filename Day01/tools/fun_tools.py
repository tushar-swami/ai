"""
Fun tools — dice roller and other entertainment utilities.
"""

import random

from tools.registry import tool


@tool(
    description="Roll a die and return only the random number rolled. Default is a 6-sided die.",
    parameters={
        "sides": {
            "type": "integer",
            "description": "Number of sides on the die. Defaults to 6.",
        },
    },
)
def roll_dice(sides: int = 6) -> int:
    """
    Roll a die and return only the number.

    Args:
        sides: Number of sides on the die (defaults to 6).

    Returns:
        int: Random integer between 1 and sides.
    """
    try:
        sides = max(1, int(sides))
    except (ValueError, TypeError):
        sides = 6
    return random.randint(1, sides)
