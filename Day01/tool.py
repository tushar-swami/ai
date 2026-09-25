import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_current_datetime(timezone_str: str = "local") -> dict:
    """
    Fetch the current date, time, day of the week, and timezone.

    Args:
        timezone_str: The timezone name (e.g. "local", "UTC", "Asia/Kolkata", "America/New_York").
                      Defaults to "local".

    Returns:
        dict: A dictionary containing structured date and time information.
    """
    try:
        if timezone_str.lower() in ("local", "system", ""):
            # Local system timezone
            now = datetime.now().astimezone()
        else:
            tz = ZoneInfo(timezone_str)
            now = datetime.now(tz)
    except ZoneInfoNotFoundError:
        # Fallback to local if invalid timezone is passed
        now = datetime.now().astimezone()
        timezone_str = f"local (fallback, '{timezone_str}' not recognized)"

    tz_name = now.tzname() or "UTC"
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day_of_week": now.strftime("%A"),
        "iso": now.isoformat(),
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M:%S %p") + f" ({tz_name})",
        "timezone": str(now.tzinfo) if timezone_str != "local" else tz_name,
    }


# OpenAI / Ollama compatible tool definition
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_current_datetime",
            "description": "Fetch the current date, time, and day of the week. Useful when the user asks for the current date, time, day, or year.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone_str": {
                        "type": "string",
                        "description": "Optional timezone string (e.g. 'local', 'UTC', 'Asia/Kolkata', 'America/New_York'). Defaults to 'local'.",
                    }
                },
                "required": [],
            },
        },
    }
]


# Available functions mapping for tool execution
TOOL_MAP = {
    "get_current_datetime": get_current_datetime,
}


def execute_tool(name: str, arguments: dict | str = None) -> str:
    """
    Execute a tool by name with arguments and return a JSON string result.
    """
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            arguments = {}
    elif arguments is None:
        arguments = {}

    func = TOOL_MAP.get(name)
    if not func:
        return json.dumps({"error": f"Tool '{name}' not found."})

    try:
        result = func(**arguments)
        return json.dumps(result, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


if __name__ == "__main__":
    print("Testing get_current_datetime()...\n")
    local_info = get_current_datetime()
    print("Local Date & Time:")
    print(json.dumps(local_info, indent=2))

    print("\nTesting UTC:")
    utc_info = get_current_datetime("UTC")
    print(json.dumps(utc_info, indent=2))

    print("\nTesting execute_tool() with JSON args:")
    exec_result = execute_tool("get_current_datetime", '{"timezone_str": "America/New_York"}')
    print(exec_result)
