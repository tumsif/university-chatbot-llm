"""Chunk and retrieve relevant sections from uploaded user documents."""

from __future__ import annotations

import re
import string
from typing import List, Tuple

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120
TOP_K = 3


def _tokenize(text: str) -> set[str]:
    text = text.lower()
    for char in string.punctuation:
        text = text.replace(char, " ")
    stopwords = {
        "is", "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "of",
        "with", "do", "does", "how", "what", "where", "when", "why", "my", "your",
        "i", "you", "me", "he", "she", "it", "they", "we", "can", "could", "should",
        "would", "am", "are", "was", "were", "be", "been", "being", "have", "has",
        "had", "that", "this", "there", "from", "about", "into", "any", "all", "some",
    }
    return {w for w in text.split() if w not in stopwords and len(w) > 1}


def chunk_text(content: str) -> List[str]:
    """Split document text into overlapping chunks."""
    normalized = re.sub(r"\r\n?", "\n", content.strip())
    if not normalized:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    chunks: List[str] = []
    current = ""

    for para in paragraphs:
        if len(para) > CHUNK_SIZE:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(para):
                piece = para[start : start + CHUNK_SIZE]
                chunks.append(piece.strip())
                start += CHUNK_SIZE - CHUNK_OVERLAP
            continue

        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= CHUNK_SIZE:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = para

    if current:
        chunks.append(current.strip())

    return chunks or [normalized[:CHUNK_SIZE]]


def retrieve_document_chunks(question: str, content: str, top_k: int = TOP_K) -> List[str]:
    """Return the most relevant text chunks for a question."""
    chunks = chunk_text(content)
    if not chunks:
        return []

    question_tokens = _tokenize(question)
    if not question_tokens:
        return chunks[:top_k]

    scored: List[Tuple[float, str]] = []
    for chunk in chunks:
        chunk_tokens = _tokenize(chunk)
        if not chunk_tokens:
            continue
        intersection = question_tokens.intersection(chunk_tokens)
        union = question_tokens.union(chunk_tokens)
        jaccard = len(intersection) / len(union) if union else 0.0
        recall = len(intersection) / len(question_tokens)
        scored.append((max(jaccard, recall * 0.85), chunk))

    if not scored:
        return chunks[:top_k]

    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for score, chunk in scored[:top_k] if score > 0.02] or chunks[:top_k]
