import json
import random
import secrets
import string
import sys
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Pre-allocated character sets for password generation optimization
LOWER_CHARS = string.ascii_lowercase
UPPER_CHARS = string.ascii_uppercase
DIGIT_CHARS = string.digits
SPECIAL_CHARS = "!@#$%^&*-_=+"
ALPHANUMERIC_CHARS = LOWER_CHARS + UPPER_CHARS + DIGIT_CHARS
ALL_CHARS = ALPHANUMERIC_CHARS + SPECIAL_CHARS


def get_current_datetime(format_type: str = "all", timezone_str: str = "local") -> str:
    """
    Fetch the current date, time, or both.

    Args:
        format_type: 'time' for hh:mm:ss, 'date' for dd-mm-yyyy, 'all' for dd-mm-yyyy hh:mm:ss.
        timezone_str: Timezone name (e.g., 'local', 'UTC', 'Asia/Kolkata'). Defaults to 'local'.

    Returns:
        str: Formatted time or datetime string.
    """
    try:
        now = datetime.now().astimezone() if timezone_str.lower() in ("local", "system", "") else datetime.now(ZoneInfo(timezone_str))
    except ZoneInfoNotFoundError:
        now = datetime.now().astimezone()

    if format_type == "time":
        return now.strftime("%H:%M:%S")
    if format_type == "date":
        return now.strftime("%d-%m-%Y")
    return now.strftime("%d-%m-%Y %H:%M:%S")


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


# OpenAI / Ollama compatible tool definitions
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Fetch the current date, time, or full datetime. format_type can be 'time', 'date', or 'all'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "format_type": {
                        "type": "string",
                        "enum": ["time", "date", "all"],
                        "description": "Output format: 'time' for hh:mm:ss, 'date' for dd-mm-yyyy, 'all' for dd-mm-yyyy hh:mm:ss (default).",
                    },
                    "timezone_str": {
                        "type": "string",
                        "description": "Optional timezone (e.g., 'local', 'UTC', 'Asia/Kolkata'). Defaults to 'local'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "roll_dice",
            "description": "Roll a die and return only the random number rolled. Default is a 6-sided die.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sides": {
                        "type": "integer",
                        "description": "Number of sides on the die. Defaults to 6.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_password",
            "description": "Generate a secure random password with letters, digits, and optional special characters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "length": {
                        "type": "integer",
                        "description": "Length of the password. Defaults to 12.",
                    },
                    "include_special": {
                        "type": "boolean",
                        "description": "Whether to include special characters like !@#$. Defaults to true.",
                    },
                },
                "required": [],
            },
        },
    },
]

TOOL_MAP = {
    "get_current_datetime": get_current_datetime,
    "roll_dice": roll_dice,
    "generate_password": generate_password,
}


def execute_tool(name: str, arguments: dict | str = None) -> str:
    """
    Execute a tool by name with arguments and return the result string.
    """
    func = TOOL_MAP.get(name)
    if not func:
        return json.dumps({"error": f"Tool '{name}' not found."})

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


if __name__ == "__main__":
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else ""

    if arg == "time":
        # Shows time if parameter is time
        print(get_current_datetime(format_type="time"))
    elif arg in ("date", "datetime"):
        print(get_current_datetime(format_type="all"))
    elif "dice" in arg:
        print(roll_dice())
    elif "pass" in arg:
        print(generate_password())
    else:
        # Otherwise prints all
        print(f"Time:     {get_current_datetime(format_type='all')}")
        print(f"Dice:     {roll_dice()}")
        print(f"Password: {generate_password()}")
