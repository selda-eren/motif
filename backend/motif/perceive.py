"""Perception: read ONE passage and propose elementary units, each anchored to a verbatim quote."""
from __future__ import annotations

from .llm import StructuredClient
from .schema import Evidence, PerceivedUnit, PerceptionResult, Unit
from .text import Book, Passage, locate_quote

SYSTEM = """You are the perception stage of MOTIF, a system that reads a text incrementally, \
passage by passage, the way a careful reader builds understanding.

Read ONLY the passage given. Propose 3-6 elementary units that carry its meaning:
- concept: an idea or notion the passage introduces or uses
- claim: an assertion or argumentative step
- event: something that happens
- situation: a state of affairs or scene
- entity: a person, group or thing that matters
- image: a figure, metaphor or recurring motif

Rules:
- `quote` MUST be copied character-for-character from the passage (5-40 words). Do not paraphrase \
inside `quote`, do not join non-adjacent text, do not add ellipses.
- `content` states the unit in one plain sentence, as this passage presents it.
- basis "explicit" = directly stated by the quote; "inferred" = your interpretation, anchored by the quote.
- When the text is figurative, record the literal image as presented; do not import knowledge of \
how the work continues or what it is famous for.
- Prefer units that later passages could build on, challenge or reinterpret."""


def perception_prompt(book: Book, passage: Passage, n_passages: int, prev_gist: str | None) -> str:
    context = f"Previous passage, in one sentence: {prev_gist}\n\n" if prev_gist else ""
    return (
        f"Text: \"{book.title}\" by {book.author} ({book.genre}).\n"
        f"{context}"
        f"Passage {passage.index + 1} of {n_passages}:\n<<<\n{passage.text}\n>>>"
    )


def perceive(client: StructuredClient, book: Book, passage: Passage, n_passages: int,
             prev_gist: str | None) -> PerceptionResult:
    raw = client.complete(
        task="perception", key=f"p{passage.index}", system=SYSTEM,
        user=perception_prompt(book, passage, n_passages, prev_gist),
        schema_name="Perception", schema=PerceptionResult.model_json_schema(),
    )
    return PerceptionResult.model_validate(raw)


def ground(perceived: list[PerceivedUnit], passage: Passage) -> tuple[list[Unit], list[dict]]:
    """Keep only units whose quote is found verbatim in the passage.

    Returns provisional Units with temporary ids n1, n2, ... and a list of rejected proposals.
    """
    grounded: list[Unit] = []
    rejected: list[dict] = []
    for pu in perceived:
        span = locate_quote(passage.text, pu.quote)
        if span is None:
            rejected.append({"label": pu.label, "quote": pu.quote, "reason": "quote not found in passage"})
            continue
        start, end = span
        grounded.append(Unit(
            id=f"n{len(grounded) + 1}", kind=pu.kind, label=pu.label.strip(), content=pu.content.strip(),
            participants=[p.strip() for p in pu.participants if p.strip()],
            layer="observation" if pu.basis == "explicit" else "interpretation",
            confidence=min(1.0, max(0.0, pu.confidence)),
            introduced_at=passage.index, last_active_at=passage.index,
            evidence=[Evidence(passage=passage.index, quote=passage.text[start:end], start=start, end=end)],
        ))
    return grounded, rejected
