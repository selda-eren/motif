"""Propagation: after a passage changes an earlier unit, reconsider the units whose meaning depends on it.

Integration judges each new unit against earlier units one at a time, so a change to one unit
never reaches the units built on it. Here, every change made while integrating a passage (a
state or interpretive revision, or a CHANGES_STATE / CONTRADICTS / REFRAMES link to an earlier
unit) reactivates that unit's direct neighbours in the relation graph, even if lexical recall
did not bring them back. The model judges each candidate; being linked is not a reason to
revise, and "unchanged" is the default.

Code bounds the work and decides what is stored:
  * one model call per passage, at most MAX_PER_CHANGE neighbours per changed unit and
    MAX_CANDIDATES in total;
  * one level only: revisions made here never trigger further propagation;
  * only units from passages already read are candidates, so nothing is revised before it is read;
  * every revision must cite a unit from the triggering change as evidence, and evidence ids are
    checked; content and quotations never change.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .integrate import _unit_brief, record_revision
from .llm import StructuredClient
from .schema import PropagationResult, Relation, Unit, require_all
from .store import Store

TRIGGER_TYPES = {"CHANGES_STATE", "CONTRADICTS", "REFRAMES"}
MAX_PER_CHANGE = 4
MAX_CANDIDATES = 8

SYSTEM = """You are the reconsideration stage of MOTIF, which reads a text passage by passage. \
The passage just read changed one or more EARLIER units. You see each CHANGE and a few CANDIDATE \
units that MOTIF's memory links to a changed unit. For each candidate, decide whether its current \
reading still holds now that the change is known.

verdict:
- "unchanged": the candidate's reading still holds. This is the default. Being linked to a changed \
unit is not by itself a reason to revise.
- "state_update": only the facts of the candidate's situation have changed over time (for example, \
something it depends on no longer exists or can no longer be used), while what it means is the same.
- "reinterpretation": what the candidate signifies is now different: its role, motive, value or \
point is understood differently in light of the change.

For state_update and reinterpretation:
- new_reading: the candidate's new state or new reading, in one sentence.
- coexists: true if the new reading adds to the current reading instead of replacing it (for \
example, its practical value is lost but its symbolic value remains). Always false for state_update.
- evidence: ids of listed units whose quotations support the new reading. Include at least one unit \
from a CHANGE (the changed unit or what caused the change).

Use only what the listed units say; do not use knowledge of how the text continues or of other \
works. Units and their quotations are fixed evidence; only readings change. In new_reading and \
rationale, refer to units by label, never by id."""


@dataclass
class Change:
    unit_id: str     # the earlier unit that changed
    cause_unit: str  # the unit in the current passage responsible for the change
    how: str         # "state revision", "interpretive revision", or a relation type
    detail: str      # the new reading or the relation's rationale


def find_changes(store: Store, book_id: str, passage_idx: int) -> list[Change]:
    """Changes integration made to earlier units at this passage. Propagation's own revisions are
    excluded, which is what keeps propagation to one level."""
    units = {u.id: u for u in store.units(book_id)}
    changes = [Change(v.unit_id, v.cause_unit or "", f"{v.kind} revision", v.new_reading)
               for v in store.revisions(book_id)
               if v.passage == passage_idx and v.source == "integration"]
    for r in store.relations(book_id):
        if r.created_at != passage_idx or r.type not in TRIGGER_TYPES:
            continue
        early, late = sorted((units[r.source], units[r.target]), key=lambda u: u.introduced_at)
        if early.introduced_at < passage_idx == late.introduced_at:
            changes.append(Change(early.id, late.id, r.type, r.rationale))
    return changes


def find_candidates(store: Store, book_id: str, passage_idx: int,
                    changes: list[Change]) -> dict[str, list[tuple[Relation, str]]]:
    """Direct graph neighbours of each changed unit, from earlier passages only, strongest links
    first. Returns candidate id -> [(linking relation, changed unit id)], in round-robin order
    across changed units so one change cannot take every slot."""
    units = {u.id: u for u in store.units(book_id)}
    changed = list(dict.fromkeys(c.unit_id for c in changes))
    excluded = set(changed) | {c.cause_unit for c in changes}
    rels = store.relations(book_id)
    per_change: list[list[tuple[str, Relation, str]]] = []
    for cid in changed:
        seen: set[str] = set()
        nbrs = []
        for r in sorted(rels, key=lambda r: -r.confidence):
            if cid not in (r.source, r.target):
                continue
            other = r.target if r.source == cid else r.source
            u = units.get(other)
            if u is None or other in excluded or other in seen or u.introduced_at >= passage_idx:
                continue
            seen.add(other)
            nbrs.append((other, r, cid))
        per_change.append(nbrs[:MAX_PER_CHANGE])
    out: dict[str, list[tuple[Relation, str]]] = {}
    for rank in range(MAX_PER_CHANGE):
        for nbrs in per_change:
            if rank < len(nbrs):
                other, r, cid = nbrs[rank]
                if other in out:
                    out[other].append((r, cid))
                elif len(out) < MAX_CANDIDATES:
                    out[other] = [(r, cid)]
    return out


def propagation_prompt(passage_idx: int, gist: str, changes: list[Change],
                       candidates: dict[str, list[tuple[Relation, str]]], units: dict[str, Unit],
                       new_units: list[Unit]) -> str:
    def link(r: Relation) -> str:
        return f"{units[r.source].label} {r.type} {units[r.target].label}: {r.rationale}"

    change_list = [{"changed": _unit_brief(units[c.unit_id]), "how": c.how, "detail": c.detail,
                    "caused_by": _unit_brief(units[c.cause_unit]) if c.cause_unit in units else None}
                   for c in changes]
    cand_list = [_unit_brief(units[cid]) | {"linked_to_change_by": [link(r) for r, _ in links]}
                 for cid, links in candidates.items()]
    return (
        f"Passage {passage_idx + 1} just read: {gist}\n\n"
        f"CHANGES:\n{json.dumps(change_list, indent=1)}\n\n"
        f"CANDIDATES:\n{json.dumps(cand_list, indent=1)}\n\n"
        f"Other NEW units in passage {passage_idx + 1} (may be cited as evidence):\n"
        f"{json.dumps([_unit_brief(u) for u in new_units], indent=1)}"
    )


def propagate(client: StructuredClient, store: Store, book_id: str, passage_idx: int, gist: str) -> dict:
    """Reconsider units linked to this passage's changes. Returns notes for the passage record."""
    notes: dict = {"changes": [], "candidates": [], "decisions": [], "rejected": [], "revisions": []}
    changes = find_changes(store, book_id, passage_idx)
    notes["changes"] = [asdict(c) for c in changes]
    if not changes:
        return notes
    candidates = find_candidates(store, book_id, passage_idx, changes)
    notes["candidates"] = [{"unit_id": cid, "via": [{"relation": r.id, "changed": ch} for r, ch in links]}
                           for cid, links in candidates.items()]
    if not candidates:
        return notes

    units = {u.id: u for u in store.units(book_id)}
    new_units = [u for u in units.values() if u.introduced_at == passage_idx]
    raw = client.complete(
        task="propagation", key=f"p{passage_idx}", system=SYSTEM,
        user=propagation_prompt(passage_idx, gist, changes, candidates, units, new_units),
        schema_name="Propagation", schema=require_all(PropagationResult.model_json_schema()),
    )
    result = PropagationResult.model_validate(raw)

    trigger_side = {c.unit_id for c in changes} | {c.cause_unit for c in changes} | {u.id for u in new_units}
    citable = trigger_side | set(candidates)
    done: set[str] = set()
    for rc in result.reconsiderations:
        cid = rc.candidate
        decision = {"unit_id": cid, "verdict": rc.verdict, "rationale": rc.rationale}
        if cid not in candidates or cid in done:
            notes["rejected"].append(decision | {"reason": "not a candidate, or judged twice"})
            continue
        done.add(cid)
        notes["decisions"].append(decision)
        if rc.verdict == "unchanged":
            continue
        evidence = list(dict.fromkeys(e for e in rc.evidence if e in citable))
        if not rc.new_reading.strip() or not trigger_side & set(evidence):
            notes["rejected"].append(decision | {"reason": "no new reading, or no evidence from the change"})
            continue
        changed_by = candidates[cid][0][1]
        cause = next((c.cause_unit for c in changes if c.unit_id == changed_by), None)
        record_revision(store, book_id, units[cid], passage_idx,
                        kind="state" if rc.verdict == "state_update" else "interpretive",
                        coexists=rc.verdict == "reinterpretation" and rc.coexists,
                        new_reading=rc.new_reading, rationale=rc.rationale, cause_unit=cause,
                        source="propagation", trigger_unit=changed_by, evidence_units=evidence)
        notes["revisions"].append(cid)
    return notes
