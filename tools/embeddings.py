"""
Semantic dedup via URL-hash by default.
Drop in Voyage or OpenAI embeddings by setting VOYAGE_API_KEY.
"""
import hashlib
import os
from typing import Optional


def content_hash(text: str) -> str:
    """Stable 32-char hash of article content for dedup."""
    return hashlib.sha256(text.encode()).hexdigest()[:32]


def is_semantically_duplicate(
    text: str,
    existing_texts: list[str],
    threshold: float = 0.92,
) -> bool:
    """
    Returns True if `text` is likely a duplicate of any item in `existing_texts`.

    Default: exact hash comparison (free, no API).
    Upgrade: set VOYAGE_API_KEY to enable cosine-similarity check.
    """
    voyage_key = os.getenv("VOYAGE_API_KEY")
    if voyage_key:
        return _voyage_dedup(text, existing_texts, threshold, voyage_key)
    # Fallback: overlap on content hash only (URL dedup in history.py covers most cases)
    h = content_hash(text)
    return h in {content_hash(t) for t in existing_texts}


def _voyage_dedup(
    text: str, existing_texts: list[str], threshold: float, api_key: str
) -> bool:
    try:
        import voyageai  # pip install voyageai

        client = voyageai.Client(api_key=api_key)
        all_texts = [text] + existing_texts
        result = client.embed(all_texts, model="voyage-3-lite", input_type="document")
        embeddings = result.embeddings
        vec = embeddings[0]
        for other in embeddings[1:]:
            score = _cosine(vec, other)
            if score >= threshold:
                return True
        return False
    except Exception:
        return False


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x**2 for x in a) ** 0.5
    norm_b = sum(x**2 for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
