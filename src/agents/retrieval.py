"""
retrieval.py - Agent #2 (the RAG step).

Reads data/knowledge/*.md, splits each into sections, embeds them with Gemini's
free embedding model, and returns the most relevant sections for a query.

This version uses a tiny in-memory NumPy cosine-similarity search instead of a
vector database. For a knowledge base of this size (a handful of short markdown
files) that is more than fast enough, has no native dependencies, and avoids the
ChromaDB Rust-backend crash seen on some Windows machines. The public interface
is unchanged: RetrievalAgent().run(query, k) -> {"query":..., "hits":[...]}.
"""
import numpy as np

from agents.base import Agent
from config import KNOWLEDGE_DIR
from llm import _client  # reuse the one Gemini client

EMBED_MODEL = "gemini-embedding-001"  # free embedding model


def _embed(texts: list[str]) -> np.ndarray:
    """Embed a list of strings into a 2-D numpy array (one row per text)."""
    result = _client.models.embed_content(model=EMBED_MODEL, contents=texts)
    vecs = np.array([list(e.values) for e in result.embeddings], dtype=np.float32)
    # L2-normalise so a dot product == cosine similarity.
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


def _split_sections(markdown: str, source: str) -> list[dict]:
    """Split a markdown doc into chunks, one per '##' section."""
    chunks, buffer = [], []
    current_title = source

    def flush():
        text = "\n".join(buffer).strip()
        if text:
            chunks.append({"source": source, "title": current_title, "text": text})

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            buffer = [line]
            current_title = line.lstrip("# ").strip()
        else:
            buffer.append(line)
    flush()
    return chunks


class RetrievalAgent(Agent):
    name = "retrieval"

    def __init__(self):
        self._chunks: list[dict] = []     # the knowledge sections
        self._matrix: np.ndarray = None   # their embeddings (normalised)
        self._loaded = False

    def _ensure_index(self):
        if self._loaded:
            return
        chunks = []
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            chunks.extend(
                _split_sections(path.read_text(encoding="utf-8"), path.name)
            )
        self._chunks = chunks
        if chunks:
            self._matrix = _embed([c["text"] for c in chunks])
        self._loaded = True

    def run(self, query: str, k: int = 4) -> dict:
        self._ensure_index()
        if not self._chunks:
            return {"query": query, "hits": []}

        q = _embed([query])[0]                      # normalised query vector
        sims = self._matrix @ q                      # cosine similarity to each chunk
        k = min(k, len(self._chunks))
        top = np.argsort(-sims)[:k]                  # indices of the k best

        hits = [
            {
                "source": self._chunks[i]["source"],
                "title": self._chunks[i]["title"],
                "text": self._chunks[i]["text"],
                "distance": round(float(1.0 - sims[i]), 4),  # cosine distance
            }
            for i in top
        ]
        return {"query": query, "hits": hits}