import json
import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI


def main():
    env_path = Path(__file__).parent / ".env"
    load_dotenv(dotenv_path=env_path)

    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "qwen3:4b")

    DEFAULT_SYSTEM_PROMPT = os.getenv(
        "SYSTEM_PROMPT",
        "You are a standup comedian, answer everything in a funny way. Deliver punchlines and jokes directly without explaining your thoughts or meta-monologue."
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

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
        )

        print("\nAI: ", end="", flush=True)
        full_reply = ""
        in_think_block = False
        printed_think_header = False

        for chunk in response:
            delta = chunk.choices[0].delta

            # Handle reasoning/thinking stream (Ollama / Qwen3 reasoning format)
            reasoning = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
            if not reasoning and hasattr(delta, "model_dump"):
                d_dict = delta.model_dump()
                reasoning = d_dict.get("reasoning") or d_dict.get("reasoning_content")

            if reasoning:
                if show_thinking:
                    if not printed_think_header:
                        print("\033[90m[Thinking: ", end="", flush=True)
                        printed_think_header = True
                    print(reasoning, end="", flush=True)
                continue

            content = delta.content or ""
            if not content:
                continue

            # Close think block header if we transition to content
            if printed_think_header:
                print("]\033[0m\n", end="", flush=True)
                printed_think_header = False

            # Filter raw <think>...</think> tags if present in content
            if "<think>" in content:
                in_think_block = True
                content = content.replace("<think>", "")
            if "</think>" in content:
                in_think_block = False
                content = content.split("</think>")[-1]

            if in_think_block and not show_thinking:
                continue

            print(content, end="", flush=True)
            full_reply += content

        if printed_think_header:
            print("]\033[0m\n", end="", flush=True)

        print("\n")

        messages.append({"role": "assistant", "content": full_reply})
        save_history()


if __name__ == "__main__":
    main()

