"""
Datetime tools — date, time, and datetime queries.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tools.registry import tool


@tool(
    description="Fetch the current date, time, or full datetime. format_type can be 'time', 'date', or 'all'.",
    parameters={
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
)
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
