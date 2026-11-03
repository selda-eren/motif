"""Journey: a reader-level synthesis of the stored MORe representation into 4-6 stages.

The model sees ONLY the stored representation (passage gists, units, relations, revisions,
change scores), never the source text. It must cite unit and relation ids for every stage and
transition; code validates those citations, repairs passage ranges, and stores the result.
Generated titles and sentences are interpretations; the evidence shown with them is the
quotations attached to the cited units.
"""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from . import graph
from .humanize import humanize
from .llm import StructuredClient
from .schema import require_all
from .store import Store


class JourneyStageOut(BaseModel):
    title: str = Field(description="2-6 plain words, no ids")
    summary: str = Field(description="One sentence a newcomer understands, no ids")
    first_passage: int = Field(description="1-based passage number where the stage begins")
    last_passage: int = Field(description="1-based passage number where the stage ends")
    key_units: list[str] = Field(description="2-4 unit ids that best evidence this stage")
    leads_to_next: str = Field(description="One sentence: why this stage leads to the next. Empty for the last stage.")
    bridge_relations: list[str] = Field(description="1-3 relation ids linking this stage to the next; empty for the last stage")
    key_meanings: list[str] = Field(default_factory=list, description="0-2 ids of constructed meanings (c..) formed in this stage that "
                                                "explain it; empty if none")


class JourneyOut(BaseModel):
    overview: str = Field(description="One sentence: the whole journey of ideas, for a newcomer, no ids")
    stages: list[JourneyStageOut]


SYSTEM = """You are the synthesis stage of MOTIF. You receive the representation MOTIF built while \
reading a text passage by passage: passage gists, elementary units (each grounded in a quotation \
you do not see), relations between units, revisions of earlier readings, and per-passage change \
scores. You do NOT see the text itself, and you must not add knowledge from outside this representation.

Group ALL passages into 4-6 consecutive, non-overlapping stages that trace how the author's ideas \
develop, for a reader who has never read the work. Prefer boundaries where the representation \
shifts: high change scores, reframings, contradictions and revisions.

For each stage give: a short title; one plain sentence explaining the stage; its passage range; \
2-4 key unit ids from inside the stage that best evidence it. For every stage except the last, \
give one sentence explaining why it leads to the next stage, and cite 1-3 relation ids that \
connect units of this stage to units of the next (or later units that revise this stage's units). \
Constructed meanings are higher-level interpretations MOTIF built from several units together, \
with their distinct support and the passages that reinforced them. Where one explains why a stage \
matters, why earlier events change significance, or how a recurring meaning becomes established, use it \
in the stage and in leads_to_next, and cite its id in key_meanings. Do not force one into an unrelated stage.

Write for a newcomer: plain words, no jargon, no ids in titles or sentences. Also write a \
one-sentence overview of the whole journey."""


def representation_digest(store: Store, book_id: str) -> str:
    """Compact text form of the stored representation (the model's only input)."""
    snap = graph.snapshot(store, book_id)
    units = {u["id"]: u for u in snap["units"]}
    lines = [f"Text: \"{snap['book']['title']}\" by {snap['book']['author']} "
             f"({len(snap['passages'])} passages)", "", "PASSAGES (gist, change score):"]
    for c in snap["changes"]:
        lines.append(f"P{c['passage'] + 1} [change {c['change_score']}]: {c['gist']}")
    lines += ["", "UNITS (id [kind, passage] label: content):"]
    for u in snap["units"]:
        line = f"{u['id']} [{u['kind']}, P{u['introduced_at'] + 1}] {u['label']}: {u['content']}"
        if u["reading"]:
            line += f" | current reading: {u['reading']}"
        for other in u.get("other_readings", []):
            line += f" | also read as: {other}"
        if u.get("state"):
            line += f" | current state: {u['state']}"
        lines.append(line)
    lines += ["", "RELATIONS (id, passage formed: source TYPE target, rationale):"]
    for r in snap["relations"]:
        lines.append(f"{r['id']} P{r['created_at'] + 1}: {r['source']} {r['type']} {r['target']}. "
                     f"{r['rationale'][:220]}")
    lines += ["", "REVISIONS (passage: unit revised, by unit, kind: new reading):"]
    for v in snap["revisions"]:
        kind = v.get("kind", "interpretive") + (", coexisting" if v.get("mode") == "coexists" else "")
        lines.append(f"P{v['passage'] + 1}: {v['unit_id']} ({units[v['unit_id']]['label']}) by "
                     f"{v['cause_unit']}, {kind}: {v['new_reading']}")
    established = [c for c in snap["constructions"] if c.get("status", "established") == "established"]
    if established:
        lines += ["", "CONSTRUCTED MEANINGS (id, passage formed, basis: statement | supported by units "
                      "| distinct support | reinforced at):"]
        for c in established:
            st = c.get("strength", {})
            again = ", ".join(f"P{r['passage'] + 1}" for r in c.get("reinforcements", [])) or "-"
            lines.append(f"{c['id']} P{c['passage'] + 1}, {c['basis']}: {c['statement']} | supported by "
                         + ", ".join(x["unit_id"] for x in c["contributors"])
                         + f" | {st.get('distinct_units', '?')} units across {st.get('distinct_passages', '?')} "
                           f"passages | {again}")
    return "\n".join(lines)


def validate(raw: JourneyOut, store: Store, book_id: str) -> dict:
    """Check citations and ranges; repair what can be repaired deterministically, and record warnings."""
    units = {u.id: u for u in store.units(book_id)}
    rels = {r.id: r for r in store.relations(book_id)}
    meanings = {c.id: c for c in store.constructions(book_id) if c.status == "established"}
    n = len(store.passages(book_id))
    warnings: list[str] = []
    if not 3 <= len(raw.stages) <= 7:
        raise ValueError(f"Journey has {len(raw.stages)} stages; expected 4-6.")

    stages = sorted(raw.stages, key=lambda s: s.first_passage)
    # Contiguous cover of passages 0..n-1, driven by each stage's stated start.
    starts = [max(0, min(n - 1, s.first_passage - 1)) for s in stages]
    starts[0] = 0
    for i in range(1, len(starts)):
        if starts[i] <= starts[i - 1]:
            starts[i] = starts[i - 1] + 1
    if starts[-1] > n - 1:
        raise ValueError("Journey stages cannot be fitted into the passages.")
    ranges = [(starts[i], (starts[i + 1] - 1) if i + 1 < len(starts) else n - 1) for i in range(len(starts))]
    for s, (a, b) in zip(stages, ranges):
        if (s.first_passage - 1, s.last_passage - 1) != (a, b):
            warnings.append(f"stage '{s.title}': passages {s.first_passage}-{s.last_passage} adjusted to {a + 1}-{b + 1}")

    temp: dict[str, str] = {}
    out = []
    for i, (s, (a, b)) in enumerate(zip(stages, ranges)):
        key = []
        for uid in s.key_units:
            if uid not in units:
                warnings.append(f"stage '{s.title}': unknown unit {uid} dropped")
            elif not a <= units[uid].introduced_at <= b:
                warnings.append(f"stage '{s.title}': unit {uid} lies outside passages {a + 1}-{b + 1}; dropped")
            else:
                key.append(uid)
        if not key:  # fall back to the stage's most connected units
            deg = {u.id: sum(u.id in (r.source, r.target) for r in rels.values())
                   for u in units.values() if a <= u.introduced_at <= b}
            key = sorted(deg, key=lambda k: -deg[k])[:3]
            warnings.append(f"stage '{s.title}': no valid key units; used the most connected units instead")
        bridges = []
        last = i == len(stages) - 1
        for rid in ([] if last else s.bridge_relations):
            r = rels.get(rid)
            if r is None:
                warnings.append(f"stage '{s.title}': unknown relation {rid} dropped")
                continue
            ends = sorted((units[r.source].introduced_at, units[r.target].introduced_at))
            if not (a <= ends[0] <= b and ends[1] > b):
                warnings.append(f"stage '{s.title}': relation {rid} does not link this stage to a later one")
            bridges.append(rid)
        cited = []
        for cid in s.key_meanings:
            if cid not in meanings:
                warnings.append(f"stage '{s.title}': unknown or pending constructed meaning {cid} dropped")
            elif not a <= meanings[cid].passage <= b:
                warnings.append(f"stage '{s.title}': constructed meaning {cid} was formed outside passages "
                                f"{a + 1}-{b + 1}; dropped")
            elif cid not in cited:
                cited.append(cid)
        out.append({
            "index": i,
            "title": humanize(s.title, units, temp),
            "summary": humanize(s.summary, units, temp),
            "first_passage": a,
            "last_passage": b,
            "key_units": key,
            "leads_to_next": "" if last else humanize(s.leads_to_next, units, temp),
            "bridge_relations": bridges,
            "key_meanings": cited[:2],
        })
    return {"overview": humanize(raw.overview, units, temp), "stages": out, "warnings": warnings}


def synthesize(client: StructuredClient, store: Store, book_id: str) -> dict:
    digest = representation_digest(store, book_id)
    raw = client.complete(task="journey", key=book_id, system=SYSTEM, user=digest,
                          schema_name="Journey", schema=require_all(JourneyOut.model_json_schema()))
    journey = validate(JourneyOut.model_validate(raw), store, book_id)
    journey |= {"provenance": client.provenance, "model": client.model, "generated_at": time.time(),
                "basis": {"units": len(store.units(book_id)), "relations": len(store.relations(book_id)),
                          "revisions": len(store.revisions(book_id)),
                          "constructed_meanings": sum(c.status == "established"
                                                      for c in store.constructions(book_id))}}
    store.save_journey(book_id, journey)
    return journey
