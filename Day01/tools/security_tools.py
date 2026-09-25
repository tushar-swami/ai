"""
Security tools — password generation and related utilities.
"""

import secrets
import string

from tools.registry import tool

# Pre-allocated character sets for performance
LOWER_CHARS = string.ascii_lowercase
UPPER_CHARS = string.ascii_uppercase
DIGIT_CHARS = string.digits
SPECIAL_CHARS = "!@#$%^&*-_=+"
ALPHANUMERIC_CHARS = LOWER_CHARS + UPPER_CHARS + DIGIT_CHARS
ALL_CHARS = ALPHANUMERIC_CHARS + SPECIAL_CHARS


@tool(
    description="Generate a secure random password with letters, digits, and optional special characters.",
    parameters={
        "length": {
            "type": "integer",
            "description": "Length of the password. Defaults to 12.",
        },
        "include_special": {
            "type": "boolean",
            "description": "Whether to include special characters like !@#$. Defaults to true.",
        },
    },
)
def generate_password(length: int = 12, include_special: bool = True) -> str:
    """
    Generate a cryptographically secure random password.

    Args:
        length: Desired length (minimum 4, defaults to 12).
        include_special: Whether to include special characters (!@#$%^&*-_=+).

    Returns:
        str: Generated password string.
    """
    try:
        length = max(4, int(length))
    except (ValueError, TypeError):
        length = 12

    chars = ALL_CHARS if include_special else ALPHANUMERIC_CHARS

    # Ensure required character variety
    pwd = [
        secrets.choice(LOWER_CHARS),
        secrets.choice(UPPER_CHARS),
        secrets.choice(DIGIT_CHARS),
    ]
    if include_special:
        pwd.append(secrets.choice(SPECIAL_CHARS))

    # Fill remainder
    pwd.extend(secrets.choice(chars) for _ in range(length - len(pwd)))

    # Secure in-place shuffle
    secrets.SystemRandom().shuffle(pwd)
    return "".join(pwd)
