"""Replace internal identifiers in model-written explanations with human-readable references.

The integration model sometimes refers to units by id ("u00_5", "n3") or by role words
("NEW", "TARGET"). Stored text is left untouched (it is research data); this runs at display time.
"""
from __future__ import annotations

import re

from .schema import Relation, Revision, Unit

_ID = re.compile(r"\b(u\d{2}_\d+|n\d+|NEW|TARGET)\b('s)?")


def temp_id_map(passage_notes: dict) -> dict[str, str]:
    """Map temporary ids (n1, n2, ...) used while integrating a passage to final unit ids."""
    if "temp_ids" in passage_notes:
        return dict(passage_notes["temp_ids"])
    if passage_notes.get("merged"):
        return {}  # legacy notes with merges: order is ambiguous, so don't guess
    return {f"n{i + 1}": uid for i, uid in enumerate(passage_notes.get("added", []))}


def _ref(unit: Unit | None) -> str:
    return f"‘{unit.label}’" if unit else "a unit in this passage"


def humanize(text: str, units: dict[str, Unit], temp: dict[str, str],
             new_id: str | None = None, target_id: str | None = None) -> str:
    def sub(m: re.Match) -> str:
        token, poss = m.group(1), m.group(2) or ""
        if token == "NEW":
            uid = new_id
        elif token == "TARGET":
            uid = target_id
        elif token.startswith("n"):
            uid = temp.get(token)
        else:
            uid = token
        if uid is None and token in ("NEW", "TARGET"):
            return m.group(0)
        return _ref(units.get(uid)) + poss

    return _ID.sub(sub, text)


def humanize_relation(r: Relation, units: dict[str, Unit], notes_by_passage: dict[int, dict]) -> str:
    temp = temp_id_map(notes_by_passage.get(r.created_at, {}))
    s, t = units.get(r.source), units.get(r.target)
    # The "new" side is the unit first perceived in the passage where the link formed.
    if s and t and s.introduced_at == r.created_at and t.introduced_at < r.created_at:
        new_id, target_id = s.id, t.id
    elif s and t and t.introduced_at == r.created_at and s.introduced_at < r.created_at:
        new_id, target_id = t.id, s.id
    else:
        new_id, target_id = r.source, r.target
    return humanize(r.rationale, units, temp, new_id, target_id)


def humanize_revision(v: Revision, units: dict[str, Unit], notes_by_passage: dict[int, dict]) -> tuple[str, str]:
    temp = temp_id_map(notes_by_passage.get(v.passage, {}))
    return (humanize(v.new_reading, units, temp, v.cause_unit, v.unit_id),
            humanize(v.rationale, units, temp, v.cause_unit, v.unit_id))
