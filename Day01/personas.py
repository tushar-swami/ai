"""
Personas & System Prompts Manager.

Features:
    - Built-in catalog of specialized agent personas (Smart AI, DevOps Expert, etc.).
    - Extensible design: adding new roles in the future is as simple as adding an entry to PERSONAS.
    - Interactive CLI login menu for selecting persona on startup.
    - In-chat `/role` command to inspect or switch personas on the fly.
"""

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Persona:
    """Represents an agent role with name, description, and custom system prompt."""
    key: str
    name: str
    description: str
    prompt: str


# ── Built-in Personas Catalog ─────────────────────────────────────────
# To add a new role in the future, simply add a new Persona entry here!
PERSONAS: Dict[str, Persona] = {
    "general": Persona(
        key="general",
        name="Smart AI Agent",
        description="Versatile general-purpose AI assistant with access to local tools",
        prompt=(
            "You are a smart, efficient, and helpful AI assistant. You have access to local tools "
            "to check date/time, roll dice, generate passwords, list files, read documents, "
            "and search the knowledge base. When asked factual questions, use your tools to provide "
            "accurate, cited answers. Be direct, clear, and concise."
        ),
    ),
    "devops": Persona(
        key="devops",
        name="DevOps Expert Agent",
        description="Specialist in Docker, Kubernetes, CI/CD pipelines, Linux, Terraform & Cloud Architecture",
        prompt=(
            "You are a Senior DevOps & Cloud Infrastructure Engineer. You specialize in Docker, "
            "Kubernetes, Linux system administration, CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins), "
            "Terraform/OpenTofu, Bash scripting, monitoring (Prometheus/Grafana), cloud architecture (AWS/GCP/Azure), "
            "and live incident troubleshooting.\n\n"
            "Your Guidelines:\n"
            "1. Provide battle-tested, secure, and production-ready configurations (Dockerfiles, K8s manifests, pipeline YAMLs).\n"
            "2. Always emphasize security (least privilege, non-root containers), high availability, and observability.\n"
            "3. Write clean, commented scripts with step-by-step diagnostic and rollback instructions.\n"
            "4. You have access to local tools (reading files, searching knowledge base) to inspect configurations."
        ),
    ),
    "coder": Persona(
        key="coder",
        name="Senior Software Engineer",
        description="Expert in clean architecture, Python, algorithms, performance & debugging",
        prompt=(
            "You are a Staff Software Engineer and clean code architect. You write modular, type-annotated, "
            "and testable code adhering to SOLID principles and industry best practices. You provide insightful "
            "code reviews, debug complex issues systematically, and explain architectural trade-offs."
        ),
    ),
}


def list_personas() -> List[Persona]:
    """Return all registered personas."""
    return list(PERSONAS.values())


def get_persona(key_or_name: str) -> Persona | None:
    """Find a persona by its key or partial name match."""
    query = key_or_name.lower().strip()
    if query in PERSONAS:
        return PERSONAS[query]
    for p in PERSONAS.values():
        if query == p.key.lower() or query in p.name.lower():
            return p
    return None


def register_persona(key: str, name: str, description: str, prompt: str) -> Persona:
    """Dynamically register a new persona at runtime."""
    p = Persona(key=key, name=name, description=description, prompt=prompt)
    PERSONAS[key] = p
    return p


def prompt_select_persona(default_key: str = "general") -> Persona:
    """
    Display an interactive terminal menu for the user to select an agent persona at startup.
    Pressing Enter without input selects the default persona.
    """
    personas_list = list_personas()
    default_persona = PERSONAS.get(default_key, personas_list[0])

    print("\n" + "═" * 70)
    print(" 🤖 CHOOSE AGENT ROLE / PERSONA")
    print("═" * 70)

    for i, p in enumerate(personas_list, 1):
        marker = " (Default)" if p.key == default_key else ""
        print(f" [{i}] {p.name:<26}{marker} — {p.description}")
    custom_idx = len(personas_list) + 1
    print(f" [{custom_idx}] Custom Persona            — Enter your own custom system prompt")
    print("═" * 70)

    try:
        choice = input(f"Select role [1-{custom_idx}] (Press Enter for '{default_persona.name}'): ").strip()
    except (KeyboardInterrupt, EOFError):
        print(f"\nUsing default: {default_persona.name}")
        return default_persona

    if not choice:
        return default_persona

    # Number selection
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(personas_list):
            return personas_list[idx - 1]
        elif idx == custom_idx:
            try:
                custom_text = input("\nEnter custom system prompt: ").strip()
                if custom_text:
                    return Persona(
                        key="custom",
                        name="Custom Persona",
                        description="User-defined custom persona",
                        prompt=custom_text,
                    )
            except (KeyboardInterrupt, EOFError):
                pass
            return default_persona

    # Match by key or name
    matched = get_persona(choice)
    if matched:
        return matched

    print(f"Unrecognized choice '{choice}'. Defaulting to: {default_persona.name}\n")
    return default_persona


if __name__ == "__main__":
    selected = prompt_select_persona()
    print(f"\nSelected: {selected.name}")
    print(f"Description: {selected.description}")
    print(f"Prompt:\n{selected.prompt}\n")
