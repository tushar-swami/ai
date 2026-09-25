"""
Pure Python RAG Engine (Retrieval-Augmented Generation) — Built from scratch.

Features:
    - Zero third-party dependencies (uses Python standard library math, re, pathlib, collections).
    - Intelligent text chunking with configurable window and overlap.
    - Probabilistic BM25 term weighting and document length normalization.
    - Top-k snippet retrieval with source attribution (file name and line numbers).
    - Standalone CLI execution for testing search or running end-to-end Q&A with Ollama.
"""

from collections import Counter
from dataclasses import dataclass
import math
import os
from pathlib import Path
import re
import sys

# Directory paths
DAY01_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = DAY01_DIR / "knowledge"
DATA_DIR = DAY01_DIR / "data"

# Common English stopwords to ignore in search queries
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "did", "do", "does", "doing", "don't", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't",
    "it", "its", "itself", "me", "more", "most", "my", "myself", "no", "nor", "not",
    "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours",
    "ourselves", "out", "over", "own", "same", "she", "should", "so", "some", "such",
    "than", "that", "the", "their", "theirs", "them", "themselves", "then", "there",
    "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who",
    "whom", "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


@dataclass
class Chunk:
    """Represents a discrete slice of a document with source attribution."""
    chunk_id: int
    source_file: str
    line_start: int
    line_end: int
    text: str
    tokens: list[str]


def tokenize(text: str) -> list[str]:
    """Extract lowercase alphanumeric tokens, filtering out single chars and stopwords."""
    words = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
    return [w for w in words if w not in STOPWORDS]


class DocumentChunker:
    """Splits knowledge files into overlapping passages to preserve context."""

    def __init__(self, chunk_lines: int = 6, overlap_lines: int = 2):
        self.chunk_lines = chunk_lines
        self.overlap_lines = overlap_lines

    def chunk_file(self, file_path: Path, start_id: int = 0) -> list[Chunk]:
        """Read a file and split into overlapping line chunks."""
        chunks: list[Chunk] = []
        if not file_path.is_file():
            return chunks

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return chunks

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return chunks

        step = max(1, self.chunk_lines - self.overlap_lines)
        chunk_idx = start_id

        for i in range(0, len(lines), step):
            chunk_slice = lines[i : i + self.chunk_lines]
            chunk_text = "\n".join(chunk_slice)
            tokens = tokenize(chunk_text)

            if tokens:
                chunks.append(
                    Chunk(
                        chunk_id=chunk_idx,
                        source_file=file_path.name,
                        line_start=i + 1,
                        line_end=min(i + self.chunk_lines, len(lines)),
                        text=chunk_text,
                        tokens=tokens,
                    )
                )
                chunk_idx += 1

        return chunks

    def load_folders(self, *folders: Path) -> list[Chunk]:
        """Load and chunk all .txt files found across given folders."""
        all_chunks: list[Chunk] = []
        chunk_id = 0

        for folder in folders:
            if not folder.exists():
                continue
            for file_path in sorted(folder.glob("*.txt")):
                file_chunks = self.chunk_file(file_path, start_id=chunk_id)
                all_chunks.extend(file_chunks)
                chunk_id += len(file_chunks)

        return all_chunks


class BM25Engine:
    """
    Probabilistic BM25 ranking algorithm implemented in pure Python.
    Calculates BM25 score = sum(IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * (|D| / avgdl))))
    """

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.total_docs = len(chunks)

        # Precompute document lengths and frequencies
        self.doc_lens = [len(c.tokens) for c in chunks]
        self.avg_doc_len = (sum(self.doc_lens) / self.total_docs) if self.total_docs > 0 else 1.0

        # Term frequency per chunk: list of Counter({term: count})
        self.term_freqs = [Counter(c.tokens) for c in chunks]

        # Document frequency: count of documents containing term t
        self.doc_freq: dict[str, int] = Counter()
        for tf in self.term_freqs:
            for term in tf:
                self.doc_freq[term] += 1

        # Precompute Inverse Document Frequency (IDF)
        self.idf: dict[str, float] = {}
        for term, df in self.doc_freq.items():
            # Standard BM25 IDF formula with smoothing
            self.idf[term] = math.log(1.0 + (self.total_docs - df + 0.5) / (df + 0.5))

    def score_chunk(self, query_tokens: list[str], chunk_idx: int) -> float:
        """Calculate BM25 relevance score between query and a specific chunk."""
        tf = self.term_freqs[chunk_idx]
        doc_len = self.doc_lens[chunk_idx]
        score = 0.0

        len_norm = 1.0 - self.b + self.b * (doc_len / self.avg_doc_len)

        for term in query_tokens:
            if term in tf:
                term_tf = tf[term]
                term_idf = self.idf.get(term, 0.0)
                # BM25 term saturation formula
                term_score = term_idf * (term_tf * (self.k1 + 1.0)) / (term_tf + self.k1 * len_norm)
                score += term_score

        return score

    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        """Return top-k highest scoring chunks for query."""
        tokens = tokenize(query)
        if not tokens:
            return []

        scores: list[tuple[Chunk, float]] = []
        for i, chunk in enumerate(self.chunks):
            score = self.score_chunk(tokens, i)
            if score > 0.0:
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ── Global Shared Engine (Loaded once on startup) ────────────────────
_engine: BM25Engine | None = None


def get_engine() -> BM25Engine:
    """Lazily load and cache the BM25 index across all knowledge and data files."""
    global _engine
    if _engine is None:
        chunker = DocumentChunker(chunk_lines=6, overlap_lines=2)
        chunks = chunker.load_folders(KNOWLEDGE_DIR, DATA_DIR)
        _engine = BM25Engine(chunks)
    return _engine


def search_knowledge_base(query: str, top_k: int = 3) -> list[dict]:
    """
    Search indexed knowledge files and return structured results.

    Returns:
        list[dict]: List of items with 'file', 'lines', 'score', and 'text'.
    """
    engine = get_engine()
    results = engine.retrieve(query, top_k=top_k)
    return [
        {
            "file": chunk.source_file,
            "lines": f"{chunk.line_start}-{chunk.line_end}",
            "score": round(score, 3),
            "text": chunk.text,
        }
        for chunk, score in results
    ]


def format_search_results(query: str, top_k: int = 3) -> str:
    """Format search results into a clean string suitable for LLM context or user reading."""
    results = search_knowledge_base(query, top_k=top_k)
    if not results:
        return f"No relevant facts found in knowledge base for query: '{query}'"

    output = [f"Found {len(results)} relevant passages for '{query}':\n"]
    for i, res in enumerate(results, 1):
        output.append(f"[{i}] Source: {res['file']} (Lines {res['lines']}, Score: {res['score']})")
        output.append(res["text"])
        output.append("-" * 50)

    return "\n".join(output)


def ask_rag(question: str, top_k: int = 3) -> str:
    """
    End-to-end RAG question answering:
    1. Retrieves relevant passages from knowledge files.
    2. Builds an augmented prompt with the passages as context.
    3. Calls local Ollama model to generate a concise, grounded answer.
    """
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(DAY01_DIR / ".env")
    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "gemma4:e4b")

    context_snippets = format_search_results(question, top_k=top_k)

    augmented_prompt = f"""You are a helpful knowledge assistant. Answer the user's question using ONLY the retrieved facts below.
If the facts do not contain the answer, say that you don't know based on the provided documents.
Always cite the source file where the information was found.

--- RETRIEVED CONTEXT ---
{context_snippets}
-------------------------

Question: {question}
Answer:"""

    client = OpenAI(base_url=base_url, api_key=api_key)
    res = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": augmented_prompt}],
        stream=False,
    )
    return res.choices[0].message.content or ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python rag.py \"<your question>\"          -> Run full RAG Q&A with AI")
        print("  python rag.py --search \"<your query>\"    -> Show retrieved chunks only\n")
        sys.exit(0)

    if sys.argv[1] == "--search":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Japan Mount Fuji"
        print(format_search_results(q))
    else:
        q = " ".join(sys.argv[1:])
        print(f"\n🔍 Searching knowledge base for: \"{q}\"...\n")
        print(format_search_results(q, top_k=2))
        print("🤖 Generating AI response...\n")
        print(ask_rag(q, top_k=3))
