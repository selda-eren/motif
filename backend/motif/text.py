"""Loading texts, segmenting them into passages, and grounding quotes in passages."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Passage:
    index: int
    text: str
    start: int  # character offset in the full text
    end: int


@dataclass(frozen=True)
class Book:
    id: str
    title: str
    author: str
    genre: str
    meta: dict
    text: str


def load_book(texts_dir: Path, book_id: str) -> Book:
    meta = json.loads((texts_dir / f"{book_id}.json").read_text())
    text = (texts_dir / meta["text_file"]).read_text()
    return Book(
        id=meta["id"], title=meta["title"], author=meta.get("author", ""),
        genre=meta.get("genre", "nonfiction"), meta=meta, text=text,
    )


def list_book_ids(texts_dir: Path) -> list[str]:
    return sorted(p.stem for p in texts_dir.glob("*.json"))


def segment(text: str, target_words: int = 300, min_tail_words: int = 120) -> list[Passage]:
    """Greedy paragraph grouping into passages of roughly `target_words` words.

    Paragraphs are never split, so passage boundaries are stable and readable.
    A short trailing group is merged into the previous passage.
    """
    spans = [(m.start(), m.end()) for m in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\s*\Z)", text, re.S)]
    groups: list[list[tuple[int, int]]] = []
    current: list[tuple[int, int]] = []
    words = 0
    for s, e in spans:
        para = text[s:e]
        # Keep short replies ("True, he said.") and lowercase continuations with what precedes them.
        attaches = len(para.split()) < 15 or para[:1].islower()
        if words >= target_words and not attaches:
            groups.append(current)
            current, words = [], 0
        current.append((s, e))
        words += len(para.split())
    if current:
        if groups and words < min_tail_words:
            groups[-1].extend(current)
        else:
            groups.append(current)
    return [
        Passage(index=i, text=text[g[0][0]:g[-1][1]], start=g[0][0], end=g[-1][1])
        for i, g in enumerate(groups)
    ]


_CHAR_MAP = {"‘": "'", "’": "'", "“": '"', "”": '"', "—": "-", "–": "-"}


def _normalize_with_map(s: str) -> tuple[str, list[int]]:
    """Lower-case, unify quotes/dashes, collapse whitespace; keep a map back to original offsets."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(s):
        ch = _CHAR_MAP.get(ch, ch)
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch.lower())
        idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def locate_quote(passage_text: str, quote: str) -> tuple[int, int] | None:
    """Find `quote` verbatim (modulo case, whitespace, quote/dash style) in the passage.

    Returns (start, end) character offsets into `passage_text`, or None if not grounded.
    Leading/trailing punctuation and ellipses in the quote are tolerated.
    """
    q = quote.strip().strip("\"'‘’“”").strip(" .,;:…").strip()
    if len(q) < 3:
        return None
    norm_p, pmap = _normalize_with_map(passage_text)
    norm_q, _ = _normalize_with_map(q)
    pos = norm_p.find(norm_q)
    if pos < 0:
        return None
    return pmap[pos], pmap[pos + len(norm_q) - 1] + 1
