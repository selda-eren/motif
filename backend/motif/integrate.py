"""Integration: relate newly perceived units to activated memory, then apply the result.

The model *proposes*; this module *decides* what enters the representation. It checks
every id, rejects self-links and duplicates, clamps confidences, and logs revisions, so
the stored representation never references anything that does not exist.
"""
from __future__ import annotations

import json

from .llm import StructuredClient
from .schema import RELATION_DEFINITIONS, IntegrationResult, Relation, Revision, Unit, require_all
from .store import Store

SYSTEM = """You are the integration stage of MOTIF. A reader has just finished a new passage. \
You see the NEW units perceived in it and EXISTING units from earlier passages that the new \
material brought back to mind.

For each new unit, decide:
- action "merge": it restates an existing unit (same idea, same referent). Set merge_into to that id.
- action "add": it is new information. Set merge_into to "".
- relations: links between this new unit and an existing unit or another new unit. Each reads \
"A <TYPE> B"; set direction to say whether the new unit is A ("new_to_target") or B ("target_to_new"):
{definitions}
- revisions: only when this new passage changes an EXISTING unit. Say which kind:
  "state": only the facts changed over time (something is now lost, sold, ended); give what is now the case.
  "interpretive": what the earlier unit means or signifies has changed (for example, a literal image \
is now explained as standing for something else, or an earlier claim is qualified); give the new reading. \
Set coexists to true if the new reading adds to the current one instead of replacing it.

Write rationales and readings for a human reader: refer to units by their label in plain words, \
never by id (no "u00_1", "n2", "NEW" or "TARGET").

Be selective: prefer zero to three relations per unit, and only relations you could defend by \
pointing at both texts. The rationale must say what each side says. Earlier passages are fixed \
evidence; your readings of them may change."""


def _unit_brief(u: Unit) -> dict:
    d = {"id": u.id, "kind": u.kind, "label": u.label, "content": u.content,
         "passage": u.introduced_at + 1, "quote": u.evidence[0].quote if u.evidence else ""}
    if u.reading:
        d["current_reading"] = u.reading
    if u.other_readings:
        d["other_readings"] = u.other_readings
    if u.state:
        d["current_state"] = u.state
    return d


def integration_prompt(passage_idx: int, gist: str, new_units: list[Unit], existing: list[Unit]) -> str:
    return (
        f"New passage {passage_idx + 1}: {gist}\n\n"
        f"NEW units:\n{json.dumps([_unit_brief(u) for u in new_units], indent=1)}\n\n"
        f"EXISTING units (activated from memory):\n"
        f"{json.dumps([_unit_brief(u) for u in existing], indent=1) if existing else '[] (nothing yet)'}"
    )


def propose(client: StructuredClient, passage_idx: int, gist: str, new_units: list[Unit],
            existing: list[Unit]) -> IntegrationResult:
    definitions = "\n".join(f"  {k}: {v}" for k, v in RELATION_DEFINITIONS.items())
    raw = client.complete(
        task="integration", key=f"p{passage_idx}", system=SYSTEM.format(definitions=definitions),
        user=integration_prompt(passage_idx, gist, new_units, existing),
        schema_name="Integration", schema=require_all(IntegrationResult.model_json_schema()),
    )
    return IntegrationResult.model_validate(raw)


def _clamp(x: float) -> float:
    return min(1.0, max(0.0, x))


def record_revision(store: Store, book_id: str, unit: Unit, passage_idx: int, *, kind: str, coexists: bool,
                    new_reading: str, rationale: str, cause_unit: str | None, source: str = "integration",
                    trigger_unit: str | None = None, evidence_units: list[str] | None = None) -> Revision:
    """Change a unit's state or reading and log it. Content and evidence are never touched.

    A state update replaces `state` and leaves the reading alone. An interpretive revision replaces
    `reading`, or, when it coexists with an existing reading, is added to `other_readings`.
    """
    text = new_reading.strip()
    if kind == "state":
        old, unit.state, mode = unit.state, text, "replaces"
    elif coexists and unit.reading:
        old, mode = unit.reading, "coexists"
        unit.other_readings = [*unit.other_readings, text]
    else:
        old, unit.reading, mode = unit.reading, text, "replaces"
    rev = Revision(unit_id=unit.id, passage=passage_idx, old_reading=old, new_reading=text,
                   rationale=rationale.strip(), cause_unit=cause_unit, kind=kind, mode=mode, source=source,
                   trigger_unit=trigger_unit, evidence_units=evidence_units or [])
    store.add_revision(book_id, rev)
    unit.last_active_at = passage_idx
    store.update_unit(book_id, unit)
    store.add_activation(book_id, unit.id, passage_idx, "revised")
    return rev


def apply(store: Store, book_id: str, passage_idx: int, new_units: list[Unit],
          result: IntegrationResult, memory: dict[str, Unit], allowed: set[str] | None = None) -> dict:
    """Apply validated integration decisions.

    `memory` maps id -> every existing unit. `allowed` is the set of existing unit ids that were
    activated (shown to the model); links to anything else are rejected. None allows all.
    """
    notes: dict = {"added": [], "merged": [], "relations": [], "revisions": [], "warnings": []}
    visible = dict(memory) if allowed is None else {k: v for k, v in memory.items() if k in allowed}
    memory = visible
    new_by_tmp = {u.id: u for u in new_units}
    decisions = {d.new_unit: d for d in result.decisions if d.new_unit in new_by_tmp}
    for d in result.decisions:
        if d.new_unit not in new_by_tmp:
            notes["warnings"].append(f"decision for unknown new unit {d.new_unit!r} ignored")

    # 1. Resolve each new unit to a final id: either a fresh unit or an existing one it restates.
    final_id: dict[str, str] = {}
    taken = {u.id for u in store.units(book_id)}
    counter = 0
    for tmp, unit in new_by_tmp.items():
        d = decisions.get(tmp)
        if d and d.action == "merge" and d.merge_into in memory:
            target = memory[d.merge_into]
            for ev in unit.evidence:
                target.evidence.append(ev)
                store.add_evidence(book_id, target.id, ev)
            target.confidence = _clamp(target.confidence + (1 - target.confidence) * 0.3 * unit.confidence)
            target.last_active_at = passage_idx
            store.update_unit(book_id, target)
            store.add_activation(book_id, target.id, passage_idx, "reinforced")
            final_id[tmp] = target.id
            notes["merged"].append({"new": unit.label, "into": target.id})
            continue
        if d and d.action == "merge":
            notes["warnings"].append(f"{tmp}: merge target {d.merge_into!r} not in working memory; added instead")
        counter += 1
        while f"u{passage_idx:02d}_{counter}" in taken:
            counter += 1
        unit = unit.model_copy(update={"id": f"u{passage_idx:02d}_{counter}"})
        store.add_unit(book_id, unit)
        memory[unit.id] = unit
        final_id[tmp] = unit.id
        notes["added"].append(unit.id)

    notes["temp_ids"] = dict(final_id)

    # 2. Relations and revisions.
    existing_rels = store.relations(book_id)
    seen: set[tuple[str, str, str]] = {(r.source, r.target, r.type) for r in existing_rels}
    taken_rels = {r.id for r in existing_rels}
    rel_counter = 0
    for tmp, d in decisions.items():
        source = final_id[tmp]
        for pr in d.relations:
            target = final_id.get(pr.target, pr.target)
            if target not in memory:
                notes["warnings"].append(f"relation {source}->{pr.target}: target unknown or not in working memory")
                continue
            if target == source:
                continue
            a, b = (source, target) if pr.direction == "new_to_target" else (target, source)
            if (a, b, pr.type) in seen:
                continue
            seen.add((a, b, pr.type))
            rel_counter += 1
            while f"r{passage_idx:02d}_{rel_counter}" in taken_rels:
                rel_counter += 1
            rel = Relation(id=f"r{passage_idx:02d}_{rel_counter}", source=a, target=b, type=pr.type,
                           rationale=pr.rationale.strip(), confidence=_clamp(pr.confidence),
                           created_at=passage_idx)
            store.add_relation(book_id, rel)
            notes["relations"].append(rel.id)
            tgt = memory[target]
            if tgt.introduced_at < passage_idx:
                store.add_activation(book_id, target, passage_idx, "related")
                if pr.type == "CONTRADICTS" and tgt.status != "contested":
                    tgt.status = "contested"
                    store.update_unit(book_id, tgt)
        for rv in d.revisions:
            target = memory.get(rv.target)
            if target is None or target.introduced_at >= passage_idx:
                notes["warnings"].append(f"revision of {rv.target!r} ignored (not an earlier unit in working memory)")
                continue
            record_revision(store, book_id, target, passage_idx, kind=rv.kind, coexists=rv.coexists,
                            new_reading=rv.new_reading, rationale=rv.rationale, cause_unit=source,
                            evidence_units=[source, target.id])
            notes["revisions"].append(target.id)
    return notes
