import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

try:
    from tools import TOOLS, execute_tool
except ImportError:
    from Day01.tools import TOOLS, execute_tool


def main():
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "gemma4:e4b")

    DEFAULT_SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        (
            "You are a smart AI agent"
        )
    )

    history_file = Path(__file__).parent / "history.json"
    show_thinking = False

    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                messages = json.load(f)
            if not isinstance(messages, list) or len(messages) == 0:
                messages = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
            elif messages[0].get("role") != "system":
                messages.insert(0, {"role": "system", "content": DEFAULT_SYSTEM_PROMPT})
            else:
                # Keep active system prompt in sync with current configuration
                messages[0]["content"] = DEFAULT_SYSTEM_PROMPT
            print(f"Loaded {len(messages) - 1} previous messages from history.")
        except Exception:
            messages = [
                {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            ]
    else:
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
        ]

    def save_history():
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)

    print(f"Connecting to: {base_url}")
    print(f"Using model:   {model}")
    print(f"Active tools:  get_current_datetime, roll_dice, generate_password")
    print("Commands:")
    print("  'exit' or 'quit'        - End session")
    print("  '/clear [new persona]'  - Reset memory (optional new role)")
    print("  '/think'                - Toggle showing model thought process\n")

    client = OpenAI(
        base_url=base_url,
        api_key=api_key,
    )

    while True:
        try:
            prompt = input("User: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break

        if not prompt:
            continue
        if prompt.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break
        if prompt.lower() == "/think":
            show_thinking = not show_thinking
            state = "ON (thoughts will be shown)" if show_thinking else "OFF (thoughts hidden)"
            print(f"Thinking mode is now {state}.\n")
            continue
        if prompt.lower().startswith("/clear"):
            # Check if user specified a custom persona after /clear
            parts = prompt.split(maxsplit=1)
            new_system_role = parts[1].strip() if len(parts) > 1 else DEFAULT_SYSTEM_PROMPT
            messages = [
                {"role": "system", "content": new_system_role},
            ]
            save_history()
            print(f"Conversation memory cleared! Active persona: \"{new_system_role}\"\n")
            continue

        messages.append({"role": "user", "content": prompt})
        save_history()

        # Send system prompt + last 8 messages to maintain prompt efficiency
        context_messages = [messages[0]] + messages[1:][-8:]

        # Step 1: Let model decide if a tool is needed
        try:
            initial_res = client.chat.completions.create(
                model=model,
                messages=context_messages,
                tools=TOOLS,
                stream=False,
            )
            initial_msg = initial_res.choices[0].message
        except Exception as e:
            print(f"\nError calling model: {e}\n")
            continue

        # Step 2: Handle tool calls if triggered
        if initial_msg.tool_calls:
            for tc in initial_msg.tool_calls:
                func_name = tc.function.name
                func_args = tc.function.arguments
                print(f"\n\033[94m[Tool Call: {func_name}({func_args})]\033[0m", flush=True)
                tool_output = execute_tool(func_name, func_args)
                print(f"\033[92m[Tool Result: {tool_output}]\033[0m\n", flush=True)

                messages.append({
                    "role": "assistant",
                    "content": initial_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": func_name,
                                "arguments": func_args,
                            },
                        }
                    ],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_output,
                })
            save_history()

            # Step 3: Stream the final synthesized answer with tool context
            context_messages = [messages[0]] + messages[1:][-10:]
            response = client.chat.completions.create(
                model=model,
                messages=context_messages,
                stream=True,
            )
        else:
            # No tools needed: print direct answer immediately
            answer = initial_msg.content or ""
            # Strip any residual think tags if present
            if "<think>" in answer and "</think>" in answer:
                answer = answer.split("</think>")[-1].strip()

            print(f"\nAI: {answer}\n")
            messages.append({"role": "assistant", "content": answer})
            save_history()
            continue

        # Stream response when tools were called
        print("AI: ", end="", flush=True)
        full_reply = ""
        in_think_block = False
        in_action_block = False

        for chunk in response:
            delta = chunk.choices[0].delta
            content = delta.content or ""
            if not content:
                continue

            if "<think>" in content:
                in_think_block = True
                content = content.replace("<think>", "")
            if "</think>" in content:
                in_think_block = False
                content = content.split("</think>")[-1]

            if in_think_block and not show_thinking:
                continue

            content = re.sub(r"\*\([^\)]*\)\*", "", content)
            if "*(" in content and ")*" not in content:
                in_action_block = True
                content = content.split("*(")[0]
            elif in_action_block:
                if ")*" in content:
                    in_action_block = False
                    content = content.split(")*", 1)[1]
                else:
                    content = ""

            if not content:
                continue

            print(content, end="", flush=True)
            full_reply += content

        print("\n")
        messages.append({"role": "assistant", "content": full_reply})
        save_history()


if __name__ == "__main__":
    main()

