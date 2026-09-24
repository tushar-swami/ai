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
        "You are a standup comedian, answer everything in a funny way."
    )

    history_file = Path(__file__).parent / "history.json"

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
    print("Type 'exit' or 'quit' to end.")
    print("Type '/clear' (or '/clear <new persona>') to reset memory.\n")

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
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            print(delta, end="", flush=True)
            full_reply += delta
        print("\n")

        messages.append({"role": "assistant", "content": full_reply})
        save_history()


if __name__ == "__main__":
    main()

