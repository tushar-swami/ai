"""
Dual-Engine RAG Engine (BM25 Keyword + Dense Semantic Vectors) — Built from scratch.

Features:
    - Dynamic Engine Selection controlled by variable (EMBEDDING_MODEL in .env or CLI).
    - BM25Engine: Probabilistic keyword ranking in pure Python (zero external dependencies).
    - VectorEmbeddingEngine: 768-dim dense semantic embeddings via Ollama (e.g. nomic-embed-text:latest).
    - Disk Caching: Embeddings are cached in .cache/ so subsequent runs take milliseconds.
    - Side-by-Side Comparison: Run `python rag.py --compare "<query>"` to see BM25 vs Vector search results.
    - Standalone CLI execution for testing search or running end-to-end Q&A with Ollama.
"""

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from dotenv import load_dotenv

# Directory paths
DAY01_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = DAY01_DIR / "knowledge"
DATA_DIR = DAY01_DIR / "data"
CACHE_DIR = DAY01_DIR / ".cache"

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


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors using pure Python."""
    dot = 0.0
    norm1 = 0.0
    norm2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        norm1 += a * a
        norm2 += b * b
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm1) * math.sqrt(norm2))


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


# ── Engine 1: BM25 Keyword Search (Pure Python) ──────────────────────
class BM25Engine:
    """
    Probabilistic BM25 ranking algorithm implemented in pure Python.
    Calculates BM25 score = sum(IDF * (TF * (k1 + 1)) / (TF + k1 * (1 - b + b * (|D| / avgdl))))
    """

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.engine_label = "BM25 (Keyword Match)"
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


# ── Engine 2: Vector Embedding Search (Dense Semantic Vectors) ───────
class VectorEmbeddingEngine:
    """
    Semantic Vector Search engine using local embedding models via Ollama.
    Features persistent disk caching under .cache/ for fast startup.
    """

    def __init__(self, chunks: list[Chunk], model_name: str = "nomic-embed-text:latest"):
        self.model_name = model_name
        self.engine_label = f"Vector Semantic ({model_name})"
        self.chunks = chunks
        self.base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
        self.api_key = os.getenv("API_KEY", "ollama")
        self._embeddings: list[list[float]] = []
        self._load_or_compute_embeddings()

    def _get_cache_path(self) -> Path:
        """Generate sanitized cache file path based on model name."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", self.model_name)
        return CACHE_DIR / f"embeddings_{safe_name}.json"

    def _compute_chunks_fingerprint(self) -> str:
        """Create a hash of all chunk texts to detect changes in knowledge files."""
        hasher = hashlib.md5()
        for c in self.chunks:
            hasher.update(c.text.encode("utf-8"))
        return hasher.hexdigest()

    def _load_or_compute_embeddings(self):
        """Load embeddings from disk cache if valid, otherwise compute and save."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_path = self._get_cache_path()
        current_fingerprint = self._compute_chunks_fingerprint()

        # Try loading from cache
        if cache_path.is_file():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if (
                    data.get("model") == self.model_name
                    and data.get("fingerprint") == current_fingerprint
                    and len(data.get("embeddings", [])) == len(self.chunks)
                ):
                    self._embeddings = data["embeddings"]
                    return
            except Exception:
                pass  # On cache read failure, recompute

        # Recompute embeddings via OpenAI-compatible endpoint in batches
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        self._embeddings = []
        batch_size = 16

        for i in range(0, len(self.chunks), batch_size):
            batch_texts = [c.text for c in self.chunks[i : i + batch_size]]
            try:
                res = client.embeddings.create(model=self.model_name, input=batch_texts)
                for item in res.data:
                    self._embeddings.append(item.embedding)
            except Exception as e:
                raise RuntimeError(
                    f"Failed to generate embeddings using '{self.model_name}'. "
                    f"Is Ollama running with this model pulled? Error: {e}"
                ) from e

        # Save to disk cache
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "model": self.model_name,
                        "fingerprint": current_fingerprint,
                        "chunk_count": len(self.chunks),
                        "embeddings": self._embeddings,
                    },
                    f,
                )
        except Exception:
            pass

    def retrieve(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        """Embed user query and rank chunks by cosine similarity."""
        if not query or not query.strip():
            return []

        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        try:
            res = client.embeddings.create(model=self.model_name, input=query.strip())
            query_vector = res.data[0].embedding
        except Exception as e:
            raise RuntimeError(f"Error embedding query with '{self.model_name}': {e}") from e

        scores: list[tuple[Chunk, float]] = []
        for chunk, chunk_vector in zip(self.chunks, self._embeddings):
            sim = cosine_similarity(query_vector, chunk_vector)
            scores.append((chunk, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ── Global Engine Factory ────────────────────────────────────────────
_cached_chunks: list[Chunk] | None = None
_bm25_engine: BM25Engine | None = None
_vector_engines: dict[str, VectorEmbeddingEngine] = {}


def get_chunks() -> list[Chunk]:
    """Load and cache chunks across knowledge/ and data/."""
    global _cached_chunks
    if _cached_chunks is None:
        chunker = DocumentChunker(chunk_lines=6, overlap_lines=2)
        _cached_chunks = chunker.load_folders(KNOWLEDGE_DIR, DATA_DIR)
    return _cached_chunks


def get_engine(model_name: str | None = None):
    """
    Factory function to retrieve the appropriate search engine:
    - If model_name is 'bm25', 'none', or empty -> returns BM25Engine.
    - Otherwise -> returns VectorEmbeddingEngine using the specified model.
    """
    global _bm25_engine, _vector_engines

    load_dotenv(DAY01_DIR / ".env")

    # If model_name not passed, read from environment variable
    if model_name is None:
        model_name = os.getenv("EMBEDDING_MODEL", "bm25").strip()

    name_lower = model_name.lower().strip()

    if name_lower in ("bm25", "none", "", "keyword", "basic"):
        if _bm25_engine is None:
            _bm25_engine = BM25Engine(get_chunks())
        return _bm25_engine

    # Dense vector model (e.g. nomic-embed-text:latest or mxbai-embed-large:latest)
    if model_name not in _vector_engines:
        _vector_engines[model_name] = VectorEmbeddingEngine(get_chunks(), model_name=model_name)
    return _vector_engines[model_name]


def search_knowledge_base(query: str, top_k: int = 3, model_name: str | None = None) -> dict:
    """
    Search indexed knowledge files and return structured results with engine metadata.
    """
    engine = get_engine(model_name)
    results = engine.retrieve(query, top_k=top_k)
    return {
        "engine": getattr(engine, "engine_label", "Unknown Engine"),
        "results": [
            {
                "file": chunk.source_file,
                "lines": f"{chunk.line_start}-{chunk.line_end}",
                "score": round(score, 3),
                "text": chunk.text,
            }
            for chunk, score in results
        ],
    }


def format_search_results(query: str, top_k: int = 3, model_name: str | None = None) -> str:
    """Format search results into clean markdown with engine attribution."""
    search_data = search_knowledge_base(query, top_k=top_k, model_name=model_name)
    engine_label = search_data["engine"]
    results = search_data["results"]

    if not results:
        return f"[{engine_label}] No relevant facts found in knowledge base for query: '{query}'"

    output = [f"🔍 [{engine_label}] Found {len(results)} relevant passages for '{query}':\n"]
    for i, res in enumerate(results, 1):
        output.append(f"[{i}] Source: {res['file']} (Lines {res['lines']}, Score: {res['score']})")
        output.append(res["text"])
        output.append("-" * 50)

    return "\n".join(output)


def compare_engines(query: str, top_k: int = 3, vector_model: str = "nomic-embed-text:latest"):
    """
    Run BM25 and Vector Search side-by-side to directly compare keyword vs semantic retrieval.
    """
    print("=" * 70)
    print(f"🔬 RAG ENGINE COMPARISON FOR QUERY: \"{query}\"")
    print("=" * 70)

    # 1. BM25 Search
    bm25 = get_engine("bm25")
    bm25_res = bm25.retrieve(query, top_k=top_k)

    print(f"\n--- 1. {bm25.engine_label} ---")
    if not bm25_res:
        print("  (No exact keyword matches found — score: 0.0)")
    else:
        for i, (chunk, score) in enumerate(bm25_res, 1):
            print(f"  [{i}] {chunk.source_file} (Lines {chunk.line_start}-{chunk.line_end}) | Score: {score:.3f}")
            first_line = chunk.text.splitlines()[0] if chunk.text else ""
            print(f"      Excerpt: \"{first_line[:90]}...\"")

    # 2. Vector Search
    vector = get_engine(vector_model)
    vector_res = vector.retrieve(query, top_k=top_k)

    print(f"\n--- 2. {vector.engine_label} ---")
    if not vector_res:
        print("  (No vector matches found)")
    else:
        for i, (chunk, score) in enumerate(vector_res, 1):
            print(f"  [{i}] {chunk.source_file} (Lines {chunk.line_start}-{chunk.line_end}) | Cosine Sim: {score:.3f}")
            first_line = chunk.text.splitlines()[0] if chunk.text else ""
            print(f"      Excerpt: \"{first_line[:90]}...\"")

    print("\n" + "=" * 70)
    print("💡 Insight:")
    print("   • BM25 excels at exact keyword and term matching.")
    print("   • Vector embeddings excel at conceptual meaning, synonyms, and paraphrasing.")
    print("=" * 70 + "\n")


def ask_rag(question: str, top_k: int = 3, model_name: str | None = None) -> str:
    """
    End-to-end RAG question answering:
    1. Retrieves relevant passages using the active configured engine.
    2. Builds an augmented prompt with the passages as context.
    3. Calls local Ollama model to generate a concise, grounded answer.
    """
    from openai import OpenAI

    load_dotenv(DAY01_DIR / ".env")
    base_url = os.getenv("BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("API_KEY", "ollama")
    model = os.getenv("MODEL", "gemma4:e4b")

    context_snippets = format_search_results(question, top_k=top_k, model_name=model_name)

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
        print("  python rag.py \"<your question>\"                 -> Full RAG Q&A with AI (uses EMBEDDING_MODEL from .env)")
        print("  python rag.py --search \"<query>\"               -> Show retrieved chunks only")
        print("  python rag.py --compare \"<query>\"              -> Compare BM25 vs Vector search side-by-side")
        print("  python rag.py --model nomic-embed-text:latest \"<query>\"  -> Force specific embedding model")
        print("  python rag.py --model bm25 \"<query>\"           -> Force BM25 keyword search\n")
        sys.exit(0)

    # Comparison Mode
    if sys.argv[1] == "--compare":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "feline predators in freezing mountains"
        compare_engines(q)
        sys.exit(0)

    # Search Mode (Retrieval only)
    if sys.argv[1] == "--search":
        q = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else "Mount Fuji"
        print(format_search_results(q))
        sys.exit(0)

    # Custom Model Override
    selected_model = None
    args = sys.argv[1:]
    if len(args) >= 3 and args[0] in ("--model", "--engine"):
        selected_model = args[1]
        args = args[2:]

    q = " ".join(args)
    print(f"\n🔍 Searching knowledge base for: \"{q}\"...\n")
    print(format_search_results(q, top_k=2, model_name=selected_model))
    print("🤖 Generating AI response...\n")
    print(ask_rag(q, top_k=3, model_name=selected_model))
