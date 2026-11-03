"""
Health tips grounded in trusted sources (retrieval-augmented generation).

After a quest is suggested (core/ai.py), SafeSpace looks up the most relevant
passages in our NIH self-help knowledge base and asks the same local model
(Qwen/Qwen2.5-0.5B-Instruct) to write a short tip based only on them.
The quest suggestion never depends on this: if anything here fails, the
user still gets their quest.

Built from llm-test/rag_system.ipynb (A8):
    - knowledge base: core/data/knowledge_base.txt (6 NIH / NIMH documents)
    - chunking: hybrid, one "##" section per chunk, split at paragraph
      breaks above 250 words, with a "Document > Section" prefix
    - embeddings: BAAI/bge-small-en-v1.5 (as accurate as bge-large on our
      test questions, about 3x faster)
    - retrieval: cosine similarity, top 3, relevance threshold 0.55

Pipeline:
    1. Build the search query from how the user feels (or the chosen journal entry).
    2. Retrieve the 3 most similar chunks; stop if none scores above 0.55.
    3. Generate a 2-3 sentence tip from those chunks with the local model.
    4. Check the tip: not empty, short, safe. Otherwise show the sources only.
"""

import logging
import re
from functools import lru_cache
from pathlib import Path

from django.conf import settings

from . import ai

logger = logging.getLogger(__name__)


KNOWLEDGE_BASE_PATH = Path(__file__).resolve().parent / "data" / "knowledge_base.txt"

MAX_CHUNK_WORDS = 250
TOP_K = 3
# bge-small scores run higher than the bge-large scores the notebook's 0.5 was set on:
# off-topic inputs ("I spent too much money") reached 0.51, so 0.55 is the cut-off
MIN_SCORE = 0.55
MAX_TIP_CHARS = 400
MAX_TIP_SENTENCES = 3

# BGE models expect this in front of search queries (not in front of passages)
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

TIP_SYSTEM_PROMPT = (
    "You are SafeSpace, a brief and gentle self-care assistant. "
    "Using ONLY the health information you are given, write 2 or 3 short sentences "
    "of practical advice for how the user feels. "
    "Do not add advice that is not in the health information. Do not diagnose. "
    "Write plain sentences, with no lists, headings, or source numbers."
)


# ============================================================
# 1. Knowledge base and chunking
# ============================================================

def parse_knowledge_base(text):
    """
    Paragraph dicts (doc, url, section, text). A blank line ends a paragraph,
    "## " starts a section and "# Document:" starts a document.
    """

    paragraphs = []
    doc = url = section = None
    lines = []

    def flush():
        if lines:
            paragraphs.append({"doc": doc, "url": url, "section": section, "text": " ".join(lines)})
            lines.clear()

    for line in text.splitlines():
        line = line.strip()

        if line.startswith("# Document:"):
            flush()
            doc = line[len("# Document:"):].strip()
            url = None
        elif line.startswith("Source:"):
            found = re.search(r"https?://[^\s,]+", line)
            url = found.group(0) if found else None
        elif line.startswith("## "):
            flush()
            section = line[3:].strip()
        elif not line:
            flush()
        else:
            lines.append(line)

    flush()

    return paragraphs


def hybrid_chunks(paragraphs, max_words=MAX_CHUNK_WORDS):
    """
    One chunk per section, split at paragraph breaks when it is too long.
    Each chunk starts with "Document > Section" so it says what it is about.
    """

    sections = {}

    for paragraph in paragraphs:
        sections.setdefault((paragraph["doc"], paragraph["section"]), []).append(paragraph)

    chunks = []

    for (doc, section), section_paragraphs in sections.items():
        groups, current, words = [], [], 0

        for paragraph in section_paragraphs:
            length = len(paragraph["text"].split())

            if current and words + length > max_words:
                groups.append(current)
                current, words = [], 0

            current.append(paragraph)
            words += length

        groups.append(current)

        for group in groups:
            chunks.append({
                "doc": doc,
                "section": section,
                "url": group[0]["url"],
                "body": " ".join(paragraph["text"] for paragraph in group),
            })

    for chunk in chunks:
        chunk["text"] = f"{chunk['doc']} > {chunk['section']}\n{chunk['body']}"

    return chunks


def load_chunks():
    return hybrid_chunks(parse_knowledge_base(KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")))


# ============================================================
# 2. Embeddings and retrieval
# ============================================================

@lru_cache(maxsize=1)
def load_index():
    """
    The embedding model, the chunks and their embeddings (one row per chunk),
    built once and kept in memory. The model downloads on first use.
    """

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ai.AIUnavailable from exc

    model = SentenceTransformer(settings.AI_EMBEDDING_MODEL_NAME)
    chunks = load_chunks()
    embeddings = model.encode([chunk["text"] for chunk in chunks], normalize_embeddings=True)

    return model, chunks, embeddings


def retrieve(query, k=TOP_K):
    """
    The k most similar chunks as (score, chunk) pairs, best first.
    Vectors are normalized, so a dot product is the cosine similarity.
    """

    import numpy as np

    model, chunks, embeddings = load_index()
    query_vector = model.encode(BGE_QUERY_PREFIX + query, normalize_embeddings=True)
    scores = embeddings @ query_vector

    return [(float(scores[i]), chunks[i]) for i in np.argsort(scores)[::-1][:k]]


def search_query(feeling, journal=None):
    """
    The text we search with: what the user typed, or the journal entry they chose.
    """

    if feeling:
        return feeling

    if journal is not None:
        return ai.clean_text(f"{journal.summary} {journal.content}", ai.MAX_INPUT_CHARS)

    return ""


# ============================================================
# 3. Prompt and generation
# ============================================================

def build_messages(query, results):
    context = "\n\n".join(
        f"[{number}] {chunk['body']}"
        for number, (_, chunk) in enumerate(results, 1)
    )

    return [
        {"role": "system", "content": TIP_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Health information:\n{context}\n\n"
            f"How I feel: {query}\n\n"
            "Write 2 or 3 short sentences of advice using only the health information above."
        )},
    ]


# ============================================================
# 4. Output checks
# ============================================================

def safe_tip(answer, context=""):
    """
    The model's tip, cut to at most 3 whole sentences, or None if it is
    empty, looks broken, or contains words a self-care app should not show.
    A blocked word is allowed when the health information itself uses it
    (e.g. "avoid alcohol before bedtime").
    """

    if not isinstance(answer, str):
        return None

    tip = ai.clean_text(answer, 1000)

    # JSON, chat tokens or list formatting mean the model did not follow the prompt
    if not tip or re.search(r"[{}<>]|\[\d+\]|^\s*([-*#]|\d+[.)])", tip):
        return None

    sentences = re.split(r"(?<=[.!?])\s+", tip)
    tip = " ".join(sentences[:MAX_TIP_SENTENCES])

    if len(tip) > MAX_TIP_CHARS or not tip.endswith((".", "!", "?")):
        return None

    blocked = [word for word in ai.BLOCKED_OUTPUT_WORDS if not re.search(rf"\b{word}\b", context, re.IGNORECASE)]

    if ai.matches_any(tip, [rf"\b{word}\b" for word in blocked]):
        return None

    return tip


def source_links(results):
    """
    One link per source section, in ranking order, for the template.
    """

    links, seen = [], set()

    for _, chunk in results:
        key = (chunk["doc"], chunk["section"])

        if key not in seen:
            seen.add(key)
            links.append({
                "title": f"{chunk['doc']} › {chunk['section']}",
                "doc": chunk["doc"],
                "section": chunk["section"],
                "url": chunk["url"] or "",
            })

    return links


# ============================================================
# Main entry point (used by the view)
# ============================================================

def grounded_tip(feeling, journal=None):
    """
    A short health tip for how the user feels, based on our knowledge base.

    Returns a dict:
        status:  "ok", "sources_only", "no_match", "unavailable" or "error"
        tip:     the text shown to the user ("" when there is none)
        sources: list of {"title", "doc", "section", "url"} for the passages
                 the tip is based on, best match first
    """

    query = search_query(ai.clean_text(feeling, ai.MAX_INPUT_CHARS), journal)
    result = {"status": "no_match", "tip": "", "sources": []}

    if not query:
        return result

    try:
        results = retrieve(query)
    except ai.AIUnavailable:
        return {**result, "status": "unavailable"}
    except Exception:
        logger.exception("Health tip retrieval failed")
        return {**result, "status": "error"}

    # Nothing in the knowledge base is close enough: don't let the model guess
    if not results or results[0][0] < MIN_SCORE:
        return result

    result["sources"] = source_links(results)

    try:
        answer = ai.generate(build_messages(query, results), max_new_tokens=150)
    except ai.AIUnavailable:
        return {**result, "status": "unavailable", "sources": []}
    except Exception:
        logger.exception("Health tip generation failed")
        return {**result, "status": "sources_only"}

    tip = safe_tip(answer, context=" ".join(chunk["body"] for _, chunk in results))

    if tip is None:
        logger.warning("Health tip failed checks: %r", answer)
        return {**result, "status": "sources_only"}

    return {**result, "status": "ok", "tip": tip}
