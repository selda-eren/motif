"""Journey explanations: a lightweight interpretive layer over the Journey.

For each stage it explains what changes and why it matters, with 2-3 quotations and how each
supports the reading. For each transition it classifies the kind of intellectual move.

Grounding rules (enforced in code, not left to the model):
  * Evidence candidates are gathered deterministically from the stored representation:
    relations linking the later stage to earlier stages, and revisions in the later stage of
    earlier units. The model may cite only these candidates (E1, E2, ...) and only the key-unit
    quotations of a stage (Q1, Q2, ...).
  * A transition that cites no valid evidence becomes "unclassified" (unless it is plain
    "succession") and tentative.
  * A transition whose evidence is not of a type that can show its kind is marked tentative,
    with a note saying so.
The MORe relation ontology is not changed; this is an interpretation of it.
"""
from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, Field

from . import graph
from .llm import StructuredClient
from .schema import require_all
from .store import Store

TransitionKind = Literal["development", "reinterpretation", "contradiction", "consequence",
                         "analogy", "succession", "unclassified"]

KIND_DEFINITIONS = {
    "development": "the later stage extends or deepens an earlier idea",
    "reinterpretation": "the later stage changes what an earlier idea or image means",
    "contradiction": "the later stage challenges, opposes or answers an objection to an earlier idea",
    "consequence": "the later stage draws an implication or practical consequence from an earlier idea",
    "analogy": "the later stage sets up a structural parallel with an earlier idea",
    "succession": "the later stage simply comes next in the narrative or argument; no stronger link is shown",
    "unclassified": "the evidence does not allow a confident classification",
}

# Which stored evidence can, on its face, show each kind of transition. A constructed meaning is not
# listed here: what it can show depends on its own content (see construction_supports).
KIND_SUPPORT: dict[str, set[str]] = {
    "development": {"REFINES", "SUPPORTS"},
    "reinterpretation": {"REFRAMES", "REVISION"},
    "contradiction": {"CONTRADICTS"},
    "consequence": {"CAUSES", "SUPPORTS", "CHANGES_STATE", "STATE_UPDATE"},
    "analogy": {"REFRAMES", "RELATES_TO"},
}

# Words in a constructed meaning's recorded relationship (and, for reinterpretation, its statement) that
# show which kind of move it can evidence. A deliberately simple, inspectable heuristic.
_RELATIONSHIP_CUES = {
    "consequence": ("cause", "consequen", "result", "lead", "because", "therefore", "enabl", "necessit", "produc"),
    "reinterpretation": ("reinterpret", "refram", "revalu", "revers", "invert", "redefin", "reread", "recast",
                         "transform", "contrast"),
    "development": ("extend", "develop", "refin", "elaborat", "part and whole", "specif", "progress", "culminat",
                    "deepen", "build"),
    "analogy": ("parallel", "mirror", "analog", "symmetr", "reciproc", "resembl", "likeness"),
    "contradiction": ("contradict", "oppos", "conflict", "challeng"),
}
_STATEMENT_REINTERPRETATION = ("rather than", "reframe", "revalue", "reinterpret", "not merely", "not mere",
                               "turns into", "turning", "becomes", "is revealed", "redefin")


def construction_supports(c) -> set[str]:
    """The kinds of transition a constructed meaning can show, from its own recorded content."""
    rel, statement = c.relationship.lower(), c.statement.lower()
    kinds = {k for k, cues in _RELATIONSHIP_CUES.items() if any(cue in rel for cue in cues)}
    if any(cue in statement for cue in _STATEMENT_REINTERPRETATION):
        kinds.add("reinterpretation")
    if c.relation_to_existing in ("extends", "overlaps", "supplements"):
        kinds.add("development")
    if c.relation_to_existing == "challenges":
        kinds.add("contradiction")
    return kinds


def shows(evidence: dict, kind: str) -> bool:
    if evidence["type"] == "CONSTRUCTED":
        return kind in evidence.get("supports_kinds", ())
    return evidence["type"] in KIND_SUPPORT.get(kind, set())

MAX_CANDIDATES = 12


class QuoteNote(BaseModel):
    ref: str = Field(description="Q-number of a quotation listed for this stage")
    how_it_supports: str = Field(description="One short sentence: how this quotation supports the stage's reading")


class StageExplanationOut(BaseModel):
    stage: int = Field(description="Stage number, 1-based")
    what_changes: str = Field(description="One sentence: what changes in the reader's understanding at this stage")
    why_it_matters: str = Field(description="One sentence: why this stage matters for the whole journey")
    quotes: list[QuoteNote] = Field(description="2-3 of this stage's quotations")


class EvidenceNote(BaseModel):
    ref: str = Field(description="E-number of a candidate listed for this transition")
    how_it_supports: str = Field(description="One short sentence: what this link shows about the transition")


class TransitionOut(BaseModel):
    from_stage: int = Field(description="1-based number of the earlier stage")
    kind: TransitionKind
    certainty: Literal["supported", "tentative"]
    what_changes: str = Field(description="One sentence: what changes intellectually between the two stages")
    why: str = Field(description="One sentence: why the text moves from the one to the other, as far as the evidence shows")
    evidence: list[EvidenceNote] = Field(description="0-3 candidates that show this transition")
    limitation: str = Field(description="What the evidence does not show; required for succession, unclassified or tentative")
    beyond_evidence: str = Field("", description="Anything in what_changes or why that is your own synthesis, "
                                                 "not shown by the cited evidence; empty if none")


class ExplainOut(BaseModel):
    stages: list[StageExplanationOut]
    transitions: list[TransitionOut]


SYSTEM = """You explain a Journey of ideas that MOTIF derived from its stored representation of a \
text. You see each stage with its numbered quotations (Q), and for each transition between \
neighbouring stages a numbered list of candidate evidence (E): links, revised readings and \
constructed meanings (built from several units) that MOTIF recorded, each with quotations from both ends.

For each stage: say what changes in the reader's understanding there, why it matters for the \
whole journey, and pick 2-3 quotations (by Q-number) with one sentence on how each supports the reading.

For each transition, classify the intellectual move:
{kinds}

Rules:
- Cite only listed E-numbers, and only those that actually show the move you describe.
- Do not invent logical connections. If the evidence only shows that one stage follows the other, \
choose "succession" and say so. If you cannot tell, choose "unclassified".
- Use certainty "tentative" when the evidence is indirect or partial, and explain the gap in `limitation`.
- A stored constructed meaning may explain a transition when its supporting units span both stages; \
cite it then, and do not force it into a transition it does not explain. Say in beyond_evidence what \
your explanation adds beyond the cited evidence.
- Write plain sentences for a reader who does not know the work. No ids or reference numbers in sentences."""


def _side(unit, passage_texts) -> dict:
    ev = unit.evidence[0]
    return {"unit_id": unit.id, "label": unit.label, "passage": ev.passage, "quote": ev.quote,
            "start": ev.start, "end": ev.end}


def gather_candidates(store: Store, book_id: str, journey: dict, i: int) -> list[dict]:
    """Evidence that could explain the move from stage i to stage i+1 (deterministic)."""
    stages = journey["stages"]
    a, b = stages[i], stages[i + 1]
    units = {u.id: u for u in store.units(book_id)}
    in_b = lambda p: b["first_passage"] <= p <= b["last_passage"]  # noqa: E731
    in_a = lambda p: a["first_passage"] <= p <= a["last_passage"]  # noqa: E731
    readable = {r["id"]: r for r in graph.readable_relations(store, book_id)}
    cands = []
    for r in store.relations(book_id):
        s, t = units[r.source], units[r.target]
        early, late = sorted((s, t), key=lambda u: u.introduced_at)
        if in_b(late.introduced_at) and early.introduced_at < b["first_passage"]:
            cands.append({
                "kind": "relation", "relation_id": r.id, "type": r.type, "confidence": r.confidence,
                "source_label": s.label, "target_label": t.label,
                "rationale": readable[r.id]["rationale"],
                "earlier": _side(early, None), "later": _side(late, None),
                "adjacent": in_a(early.introduced_at),
            })
    for v in graph.readable_revisions(store, book_id):
        u = units[v["unit_id"]]
        cause = units.get(v["cause_unit"]) if v["cause_unit"] else None
        if in_b(v["passage"]) and u.introduced_at < b["first_passage"] and cause:
            cands.append({
                "kind": "revision", "type": "REVISION" if v.get("kind", "interpretive") == "interpretive" else "STATE_UPDATE",
                "unit_id": u.id, "passage": v["passage"],
                "confidence": 0.8, "new_reading": v["new_reading"], "rationale": v["rationale"],
                "earlier": _side(u, None), "later": _side(cause, None),
                "adjacent": in_a(u.introduced_at),
            })
    for c in store.constructions(book_id):
        if c.status != "established":
            continue
        # A constructed meaning explains the move into stage b if it was formed, or reinforced with new
        # evidence, in stage b and rests on evidence from before it.
        reinforced = [r.passage for r in c.reinforcements if in_b(r.passage)]
        ev = sorted((e for e in c.evidence if e.passage <= b["last_passage"]), key=lambda e: e.passage)
        if (in_b(c.passage) or reinforced) and ev and ev[0].passage < b["first_passage"]:
            first, last = ev[0], ev[-1]
            side = lambda e: {"unit_id": e.unit_id, "label": units[e.unit_id].label, "passage": e.passage,  # noqa: E731
                              "quote": e.quote, "start": 0, "end": 0}
            cands.append({
                "kind": "construction", "type": "CONSTRUCTED", "construction_id": c.id, "confidence": 0.8,
                "statement": c.statement, "rationale": c.justification, "basis": c.basis,
                "support": f"{c.strength['distinct_units']} units across {c.strength['distinct_passages']} passages",
                "reinforced_at": reinforced, "formed_at": c.passage,
                "supports_kinds": sorted(construction_supports(c)),
                "earlier": side(first), "later": side(last), "adjacent": in_a(first.passage),
            })
    # Prefer links to the adjacent stage, then the types that carry the most meaning.
    weight = {"CONSTRUCTED": 3, "REFRAMES": 3, "REVISION": 3, "CONTRADICTS": 3, "CAUSES": 2, "REFINES": 2, "CHANGES_STATE": 2,
              "STATE_UPDATE": 1, "SUPPORTS": 1, "RELATES_TO": 0}
    cands.sort(key=lambda c: (-c["adjacent"], -weight[c["type"]], -c["confidence"]))
    return cands[:MAX_CANDIDATES]


def stage_quotes(store: Store, book_id: str, stage: dict) -> list[dict]:
    units = {u.id: u for u in store.units(book_id)}
    return [_side(units[uid], None) for uid in stage["key_units"] if uid in units and units[uid].evidence]


def build_prompt(store: Store, book_id: str, journey: dict) -> tuple[str, list[list[dict]], list[list[dict]]]:
    book = store.get_book(book_id)
    lines = [f"Text: \"{book['title']}\" by {book['author']}", f"Journey overview: {journey['overview']}", ""]
    quotes, cands = [], []
    for i, s in enumerate(journey["stages"]):
        qs = stage_quotes(store, book_id, s)
        quotes.append(qs)
        lines.append(f"STAGE {i + 1}: {s['title']} (passages {s['first_passage'] + 1}-{s['last_passage'] + 1})")
        lines.append(f"  Summary: {s['summary']}")
        for k, q in enumerate(qs, 1):
            lines.append(f"  Q{k} [{q['label']}, passage {q['passage'] + 1}]: \"{q['quote']}\"")
        lines.append("")
    for i in range(len(journey["stages"]) - 1):
        cs = gather_candidates(store, book_id, journey, i)
        cands.append(cs)
        lines.append(f"TRANSITION {i + 1} -> {i + 2}: candidate evidence")
        if not cs:
            lines.append("  (none: MOTIF recorded no link between these stages)")
        for k, c in enumerate(cs, 1):
            where = "adjacent stage" if c["adjacent"] else "an earlier stage"
            if c["kind"] == "relation":
                head = f"‘{c['source_label']}’ {c['type']} ‘{c['target_label']}’ (link to {where})"
            elif c["kind"] == "construction":
                when = (f"reinforced in passage {', '.join(str(p + 1) for p in c['reinforced_at'])}"
                        if c["reinforced_at"] else f"formed in passage {c['formed_at'] + 1}")
                can = ", ".join(c["supports_kinds"]) or "no particular kind"
                head = (f"stored constructed meaning ({c['basis']}, {c['support']}, {when}; reaching back to "
                        f"{where}; its recorded relationship can show: {can}): {c['statement']}")
            else:
                head = f"revised reading of ‘{c['earlier']['label']}’ (from {where}): {c['new_reading']}"
            lines.append(f"  E{k} {head}")
            lines.append(f"     earlier, passage {c['earlier']['passage'] + 1}: \"{c['earlier']['quote']}\"")
            lines.append(f"     later, passage {c['later']['passage'] + 1}: \"{c['later']['quote']}\"")
            lines.append(f"     recorded rationale: {c['rationale'][:240]}")
        lines.append("")
    return "\n".join(lines), quotes, cands


def _num(ref: str, prefix: str) -> int | None:
    ref = ref.strip().upper()
    return int(ref[1:]) - 1 if ref.startswith(prefix) and ref[1:].isdigit() else None


def validate(raw: ExplainOut, journey: dict, quotes: list[list[dict]], cands: list[list[dict]]) -> dict:
    warnings: list[str] = []
    n = len(journey["stages"])
    stages_out = []
    by_stage = {s.stage - 1: s for s in raw.stages}
    for i in range(n):
        s = by_stage.get(i)
        chosen = []
        for qn in (s.quotes if s else []):
            k = _num(qn.ref, "Q")
            if k is None or not 0 <= k < len(quotes[i]):
                warnings.append(f"stage {i + 1}: quotation {qn.ref} is not one of this stage's quotations; dropped")
            elif all(c["unit_id"] != quotes[i][k]["unit_id"] for c in chosen):
                chosen.append(quotes[i][k] | {"how_it_supports": qn.how_it_supports.strip()})
        if not chosen:  # show the stage's own quotations without commentary
            chosen = [q | {"how_it_supports": ""} for q in quotes[i][:2]]
            if s:
                warnings.append(f"stage {i + 1}: no valid quotation choices; showing key quotations")
        stages_out.append({
            "index": i,
            "what_changes": s.what_changes.strip() if s else "",
            "why_it_matters": s.why_it_matters.strip() if s else "",
            "quotes": chosen[:3],
        })
        if not s:
            warnings.append(f"stage {i + 1}: no explanation returned")

    trans_out = []
    by_from = {t.from_stage - 1: t for t in raw.transitions}
    for i in range(n - 1):
        t = by_from.get(i)
        if t is None:
            trans_out.append({"from_index": i, "to_index": i + 1, "kind": "unclassified", "certainty": "tentative",
                              "what_changes": "", "why": "", "evidence": [],
                              "limitation": "No explanation was produced for this transition.", "grounding_note": "",
                              "beyond_evidence": ""})
            warnings.append(f"transition {i + 1}: missing")
            continue
        evidence = []
        for en in t.evidence:
            k = _num(en.ref, "E")
            if k is None or not 0 <= k < len(cands[i]):
                warnings.append(f"transition {i + 1}: evidence {en.ref} was not a candidate; dropped")
                continue
            if any(e["ref_index"] == k for e in evidence):
                continue
            evidence.append(cands[i][k] | {"ref_index": k, "how_it_supports": en.how_it_supports.strip()})
        kind, certainty, note = t.kind, t.certainty, ""
        limitation = t.limitation.strip()
        if not evidence and kind not in ("succession", "unclassified"):
            note = (f"Proposed as {kind}, but no recorded link between these stages was cited, "
                    f"so MOTIF does not present it as an established connection.")
            kind, certainty = "unclassified", "tentative"
        elif kind in KIND_SUPPORT and not any(shows(e, kind) for e in evidence):
            types = ", ".join(sorted({e["type"].lower() for e in evidence}))
            note = f"The cited links are of type {types}, which do not directly show a {kind}; treat this as tentative."
            certainty = "tentative"
        if kind in ("succession", "unclassified"):
            certainty = "tentative" if kind == "unclassified" else certainty
        if (kind in ("succession", "unclassified") or certainty == "tentative") and not (limitation or note):
            limitation = "The stored representation does not show a stronger link between these stages."
        trans_out.append({"from_index": i, "to_index": i + 1, "kind": kind, "certainty": certainty,
                          "what_changes": t.what_changes.strip(), "why": t.why.strip(), "evidence": evidence[:3],
                          "limitation": limitation, "grounding_note": note,
                          "beyond_evidence": t.beyond_evidence.strip()})
    return {"stages": stages_out, "transitions": trans_out, "warnings": warnings}


def explain(client: StructuredClient, store: Store, book_id: str) -> dict:
    journey = store.get_journey(book_id)
    if journey is None:
        raise ValueError(f"No Journey stored for {book_id!r}; run the journey command first.")
    prompt, quotes, cands = build_prompt(store, book_id, journey)
    kinds = "\n".join(f"  {k}: {v}" for k, v in KIND_DEFINITIONS.items())
    raw = client.complete(task="explain", key=book_id, system=SYSTEM.format(kinds=kinds), user=prompt,
                          schema_name="JourneyExplanation", schema=require_all(ExplainOut.model_json_schema()))
    result = validate(ExplainOut.model_validate(raw), journey, quotes, cands)
    result |= {"provenance": client.provenance, "model": client.model, "generated_at": time.time()}
    journey["explanation"] = result
    store.save_journey(book_id, journey)
    return result
