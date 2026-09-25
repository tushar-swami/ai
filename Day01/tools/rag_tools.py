"""
RAG Tools — Knowledge base search utilities for AI agents.

This module is 100% custom-built and bridges our custom BM25 RAG engine (rag.py)
to the Tool Manager registry.
"""

from tools.registry import tool
import rag


@tool(
    description=(
        "Search the local knowledge base for relevant facts and passages about "
        "countries (e.g. Japan), animals (e.g. snow leopard), notable people (e.g. Marie Curie), "
        "aliens / extraterrestrial life, and deep ocean exploration. "
        "Returns only the most relevant excerpts with source files and line numbers."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "Keywords or question to search the knowledge base for (e.g. 'Marie Curie Nobel Prize', 'Mariana Trench depth', 'snow leopard diet').",
        },
        "top_k": {
            "type": "integer",
            "description": "Number of top matching snippets to retrieve (defaults to 3).",
        },
    },
)
def search_knowledge(query: str, top_k: int = 3) -> str:
    """
    Search the indexed knowledge documents and return formatted snippets.

    Args:
        query: Search keywords or question.
        top_k: Number of relevant snippets to return.

    Returns:
        str: Formatted excerpts with source attribution.
    """
    if not query or not str(query).strip():
        return "Error: No search query provided."

    try:
        top_k = max(1, min(10, int(top_k)))
    except (ValueError, TypeError):
        top_k = 3

    return rag.format_search_results(query.strip(), top_k=top_k)


if __name__ == "__main__":
    import sys
    test_query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "snow leopard camouflage"
    print(f"Testing search_knowledge('{test_query}'):\n")
    print(search_knowledge(test_query))
