import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

try:
    from tools import registry
except ImportError:
    from Day01.tools import registry

try:
    from personas import prompt_select_persona, get_persona, list_personas, Persona
except ImportError:
    from Day01.personas import prompt_select_persona, get_persona, list_personas, Persona


def main():
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "gemma4:e4b")

    # Prompt user to choose agent role/persona at startup
    active_persona = prompt_select_persona(default_key="general")
    DEFAULT_SYSTEM_PROMPT = active_persona.prompt

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

    print(f"\nConnecting to: {base_url}")
    print(f"Using model:   {model}")
    print(f"Active role:   {active_persona.name} — {active_persona.description}")
    print(f"Active tools:  {', '.join(registry.tool_names)} ({registry.count} total)")
    print("Commands:")
    print("  'exit' or 'quit'        - End session")
    print("  '/role [name]'          - Switch persona (e.g. /role devops or /role general)")
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
        if prompt.lower() == "/role":
            print(f"\nActive Persona: {active_persona.name}")
            print(f"Description:    {active_persona.description}\n")
            print("Available Roles:")
            for p in list_personas():
                marker = " (Active)" if p.key == active_persona.key else ""
                print(f"  • /role {p.key:<10} - {p.name}{marker}")
            print("  • /role custom     - Enter custom system prompt\n")
            continue

        if prompt.lower().startswith("/role "):
            role_arg = prompt[6:].strip()
            if role_arg.lower() == "custom":
                try:
                    custom_text = input("Enter custom system prompt: ").strip()
                    if custom_text:
                        active_persona = Persona(
                            key="custom",
                            name="Custom Persona",
                            description="User-defined custom persona",
                            prompt=custom_text,
                        )
                except (KeyboardInterrupt, EOFError):
                    print("Role switch cancelled.\n")
                    continue
            else:
                matched_persona = get_persona(role_arg)
                if not matched_persona:
                    print(f"Unrecognized role '{role_arg}'. Type /role to see available roles.\n")
                    continue
                active_persona = matched_persona

            DEFAULT_SYSTEM_PROMPT = active_persona.prompt
            messages = [{"role": "system", "content": active_persona.prompt}]
            save_history()
            print(f"\nSwitched to: {active_persona.name}")
            print(f"Role: {active_persona.description}")
            print("Conversation memory reset for new role.\n")
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

        # Autonomous Multi-Step Agentic Loop (up to 5 autonomous investigation steps)
        max_tool_steps = 5
        step_count = 0

        while step_count < max_tool_steps:
            context_messages = [messages[0]] + messages[1:][-12:]
            try:
                res = client.chat.completions.create(
                    model=model,
                    messages=context_messages,
                    tools=registry.schemas,
                    stream=False,
                )
                msg = res.choices[0].message
            except Exception as e:
                print(f"\nError calling model: {e}\n")
                break

            # If the model requested tool calls, execute them and continue investigation!
            if msg.tool_calls:
                step_count += 1
                for tc in msg.tool_calls:
                    func_name = tc.function.name
                    func_args = tc.function.arguments
                    print(f"\n\033[94m[Agent Investigation Step {step_count}: {func_name}({func_args})]\033[0m", flush=True)
                    tool_output = registry.execute(func_name, func_args)

                    # Clean display for terminal UX
                    display_out = tool_output if len(tool_output) < 350 else tool_output[:350] + "\n... [truncated for display]"
                    print(f"\033[92m{display_out}\033[0m\n", flush=True)

                    messages.append({
                        "role": "assistant",
                        "content": msg.content or "",
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
                # Continue the loop so model can review the output and call the NEXT tool
                continue
            else:
                # No more tools needed — the agent has finished investigating and wrote its answer!
                answer = msg.content or ""
                if "<think>" in answer and "</think>" in answer:
                    answer = answer.split("</think>")[-1].strip()

                # Clean any residual stage directions if present
                answer = re.sub(r"\*\([^\)]*\)\*", "", answer).strip()

                print(f"\nAI: {answer}\n")
                messages.append({"role": "assistant", "content": answer})
                save_history()
                break


if __name__ == "__main__":
    main()

