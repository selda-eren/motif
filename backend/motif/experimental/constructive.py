"""Experiment 4: constructive interpretation over frozen candidate sets. NOT part of the pipeline.

Experiment 3's propagation asked a revision-oriented question of each candidate: does this earlier
unit need to change? This harness asks a constructive one of the *same input*: do several of the
listed units, taken together, support a new higher-level interpretation that none states alone?

Controlled comparison:
  * The input is frozen: the exact user message each Experiment 3 propagation call sent, read from
    its raw export. Recall, traversal, depth and candidate selection are therefore identical.
  * Objective A re-sends Experiment 3's request byte for byte (system prompt, schema, settings),
    so it is answered from the cache and reproduces the recorded verdicts.
  * Objective B sends the same user message with a constructive system prompt and output schema.
  * Nothing is written to the representation. The client writes only its cache and usage log, and
    `representation_fingerprint` lets callers check that.

Proposals are validated by code: contributing units must be among the units shown to the model,
at least two must remain, and the quotations attached as evidence come from the stored units, limited
to passages already read.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from .. import propagate
from ..llm import StructuredClient
from ..schema import PropagationResult, require_all
from ..store import Store

SYSTEM = """You are the construction stage of MOTIF, which reads a text passage by passage. The \
passage just read changed some EARLIER units. You see each CHANGE, a few CANDIDATE units that MOTIF's \
memory links to a changed unit, and the NEW units of the passage. Units are fixed observations: you \
do not change them or their readings.

Your question: given the new information, does any earlier unit acquire additional significance \
through its relationships with the other listed units? Can several listed units, taken together, \
support a new higher-level interpretation that none of them states on its own?

For each such interpretation:
- statement: the emerging meaning, in one sentence.
- contributing: ids of the listed units that jointly support it (at least two, each one necessary).
- support: for each contributing unit, what it contributes.
- relationship: how the contributing units relate to one another (for example parallel, contrast, \
cause and consequence, part and whole).
- kind: "emergent_meaning" if a new significance arises from the units taken together; \
"state_consequence" if it only states a factual consequence of the change (something is now lost, \
impossible or different).
- relation_to_existing: "supplements" if it adds to an existing reading, which stays valid; \
"challenges" if it gives reason to doubt an existing reading (explain why); "new" if no existing \
reading addresses it. existing_reading_of: the id of the unit whose reading it supplements or \
challenges, or "".
- justification and limitations: why the listed units support it, and what they do not show.
- confidence: 0.0-1.0.

Rules: units that are merely associated or share a topic do not make an interpretation. Use only what \
the listed units say; do not use knowledge of how the text continues or of other works. Existing \
readings remain valid unless you explicitly challenge one. Prefer zero to three interpretations. If \
the evidence supports no new interpretation, return an empty list and say why in no_new_meaning. In \
prose, refer to units by label, never by id."""


class Support(BaseModel):
    unit: str = Field(description="id of a contributing unit")
    contributes: str


class ProposedInterpretation(BaseModel):
    statement: str
    contributing: list[str] = Field(description="ids of at least two listed units")
    support: list[Support]
    relationship: str
    kind: Literal["emergent_meaning", "state_consequence"]
    relation_to_existing: Literal["supplements", "challenges", "new"]
    existing_reading_of: str = Field(description="unit id, or empty string")
    justification: str
    limitations: str
    confidence: float


class ConstructiveResult(BaseModel):
    interpretations: list[ProposedInterpretation]
    no_new_meaning: str = Field(description="why no (further) interpretation is supported; may be empty")


@dataclass(frozen=True)
class FrozenCase:
    name: str      # e.g. "magi_p6"
    book_id: str
    passage: int   # 0-based passage index at which the candidate set was formed
    user: str      # the exact user message Experiment 3 sent


_PASSAGE = re.compile(r"^Passage (\d+) just read:")
_LISTED = re.compile(r'"id": "(u\d{2}_\d+)"')


def cases_from_export(raw_export: dict, book_id: str, prefix: str) -> list[FrozenCase]:
    """Frozen inputs: the user message of every propagation call in an Experiment 3 raw export."""
    out = []
    for call in raw_export["llm_calls_since_start"]:
        if call["task"] != "propagation":
            continue
        user = call["request"]["messages"][1]["content"]
        idx = int(_PASSAGE.match(user).group(1)) - 1
        out.append(FrozenCase(f"{prefix}_p{idx + 1}", book_id, idx, user))
    return sorted(out, key=lambda c: c.passage)


def listed_ids(case: FrozenCase) -> set[str]:
    """Every unit id the model was shown for this case."""
    return set(_LISTED.findall(case.user))


def run_revision(client: StructuredClient, case: FrozenCase) -> dict:
    """Objective A: Experiment 3's propagation request, unchanged."""
    return client.complete(task="propagation", key=f"p{case.passage}", system=propagate.SYSTEM, user=case.user,
                           schema_name="Propagation", schema=require_all(PropagationResult.model_json_schema()))


def run_constructive(client: StructuredClient, case: FrozenCase) -> dict:
    """Objective B: same user message, constructive question."""
    return client.complete(task="constructive", key=case.name, system=SYSTEM, user=case.user,
                           schema_name="Constructive", schema=require_all(ConstructiveResult.model_json_schema()))


def validate(raw: dict, case: FrozenCase, store: Store) -> dict:
    """Check a constructive answer against the frozen input and attach stored quotations."""
    result = ConstructiveResult.model_validate(raw)
    shown = listed_ids(case)
    units = {u.id: u for u in store.units(case.book_id)}
    accepted, rejected = [], []
    for p in result.interpretations:
        valid = [uid for uid in dict.fromkeys(p.contributing) if uid in shown and uid in units]
        unknown = [uid for uid in p.contributing if uid not in shown or uid not in units]
        item = p.model_dump() | {"contributing_valid": valid, "contributing_unknown": unknown}
        if p.existing_reading_of and p.existing_reading_of not in shown:
            item["existing_reading_of_unknown"] = True
        if len(valid) < 2:
            rejected.append(item | {"reason": "fewer than two contributing units from the frozen set"})
            continue
        item["evidence"] = [
            {"unit": uid, "label": units[uid].label, "introduced_at": units[uid].introduced_at,
             "quotes": [{"passage": e.passage, "quote": e.quote}
                        for e in units[uid].evidence if e.passage <= case.passage]}
            for uid in valid]
        accepted.append(item)
    return {"accepted": accepted, "rejected": rejected, "no_new_meaning": result.no_new_meaning}


def summarize_revision(raw: dict) -> dict:
    result = PropagationResult.model_validate(raw)
    verdicts = [r.model_dump() for r in result.reconsiderations]
    return {"verdicts": verdicts,
            "non_unchanged": [v for v in verdicts if v["verdict"] != "unchanged"]}


_REPRESENTATION_TABLES = ("books", "passages", "units", "evidence", "activations", "relations", "revisions",
                          "journeys")


def representation_fingerprint(store: Store) -> str:
    """Hash of every representation table (not the cache or usage log), to show nothing was modified."""
    h = hashlib.sha256()
    for table in _REPRESENTATION_TABLES:
        cols = [r["name"] for r in store.db.execute(f"PRAGMA table_info({table})")]
        for row in store.db.execute(f"SELECT * FROM {table} ORDER BY {', '.join(cols)}"):
            h.update(json.dumps([table, *row], default=str).encode())
    return h.hexdigest()
