"""Construction: higher-level meaning from the joint activation of existing units.

Revision changes how one unit is read. Construction leaves every unit as it is and records a
new representation, a Constructed Meaning, that several units support together (for example two
separate sales that together amount to a mutual sacrifice). Started from Experiment 4's
constructive objective (docs/experiments/exp4_constructive/), refined in Milestone 5.

When it runs. Once per passage, after integration (and propagation), and only if one of these
rules fires for the passage just read (p). A long-range link on its own no longer triggers.
  R1 reinterpretation  an interpretive revision of an earlier unit, or a REFRAMES or CONTRADICTS
                       relation from a new unit to an earlier unit
  R2 bridging          a new unit linked (not RELATES_TO) to two earlier units from different
                       passages that were previously separate: no relation path of length one or
                       two joined them before p
  R3 consequential state change
                       a state revision or CHANGES_STATE of an earlier unit that already had at least
                       two established relations (not RELATES_TO or CHANGES_STATE) before p
  R4 extension         a new unit linked (not RELATES_TO) to at least two contributors of one existing
                       constructed meaning: the passage touches that meaning, not just one of its parts

What it sees. The new units, the earlier units named by the triggers or just linked to the new
units, their direct neighbours (strongest links first, at most MAX_CONTEXT earlier units), the links
among all of these, and up to MAX_PRIOR earlier constructed meanings that share contributors with this
context (reactivation), each with its distinct support. Everything comes from passages already read.

What code accepts. Objectively invalid proposals are rejected: fewer than two distinct listed
contributors with roles and quotations from passages read; no contributor new in, or changed at, this
passage; no justification; or speculative (basis "speculative", or assumptions declared).

The model's own category is not trusted on its own (Milestone 5.1). A proposal labelled
"state_consequence" is resolved deterministically:
  * pure fact: relation "new" and every contributor an event, situation or entity. Withheld as a
    factual state consequence, as before;
  * ambiguous: it relates to an existing interpretation (extends, reinforces, supplements or challenges)
    or draws on a claim, concept or image. Kept with status "pending": stored and inspectable, but never
    presented as established (not reactivated, not used by the Journey). A pending meaning is promoted
    when a later valid proposal duplicates it.

"explicit" is kept only if `stated_quote` occurs verbatim in a passage already read that one of the
contributors comes from, and the meaning echoes at least half of the quotation's content words
(MIN_QUOTE_OVERLAP, MIN_QUOTE_ECHO): constructed statements elaborate, so the test is whether the quoted
words reappear in the meaning, not the reverse. This checks that the words exist and that the meaning
restates them, not that they state it in full. Otherwise the basis is "inferred", and the note says so.

Redundancy (meaningful consolidation, not maximum compression):
  * genuine duplicate: declared "reinforces" an existing meaning, or any proposal whose wording
    nearly matches one (word overlap >= DUP_TEXT). It is consolidated into the existing meaning:
    contributors and quotations not already there are added, with the passage, and the new wording
    is kept in the reinforcement record. Without new contributors it is only noted as a repeat, which
    adds no strength.
  * overlapping: shares most contributors and some wording (SAME_UNITS, DUP_TEXT_SAME_UNITS) but is
    not a near-duplicate. Stored as its own meaning, linked as "overlaps" (or "extends", if declared).
  * independent: stored as a new meaning.
  * restating a contributor's stored reading (word overlap >= DUP_TEXT): rejected; the reading
    already holds it.
Strength is the distinct support (units, passages, reinforcements); never the model's confidence.

Bounds. One model call per triggered passage; at most MAX_ACCEPTED new meanings (established or pending)
stored per passage.
Constructed meanings are never contributors and never triggers, so construction cannot build on its
own output or chain.
"""
from __future__ import annotations

import json

from .activation import tokens
from .integrate import _unit_brief
from .llm import StructuredClient
from .schema import (Construction, ConstructionEvidence, ConstructionResult, Contributor, Reinforcement, Relation,
                     Unit, require_all)
from .store import Store
from .text import locate_quote

MAX_CONTEXT = 14     # earlier units shown (new units are always shown)
MAX_LINKS = 30
MAX_PRIOR = 4
MAX_ACCEPTED = 2
ESTABLISHED = 2      # R3: relations an earlier unit needs before its state change counts
FACT_KINDS = {"event", "situation", "entity"}
MIN_QUOTE_OVERLAP = 2      # content-word stems an explicit quotation must share with the meaning...
MIN_QUOTE_ECHO = 0.5       # ...and the share of the quotation's own content words the meaning must echo

# Duplicate rules (word overlap is Jaccard over content-word stems). Fixed in Milestone 4.
DUP_TEXT = 0.5
DUP_TEXT_SAME_UNITS = 0.25
SAME_UNITS = 0.67

SYSTEM = """You are the construction stage of MOTIF, which reads a text passage by passage. The \
passage just read reinterpreted, connected or changed some EARLIER units. You see those units, the \
units new in this passage, nearby units linked to them, the recorded links among all of these, and \
meanings MOTIF already constructed. Units are fixed observations: you do not change them or their readings.

Your question: given the new information, do several of the listed units, taken together, support \
a higher-level meaning that none of them states on its own? Does an earlier unit acquire additional \
significance through its relationships with the others? It is normal that no new meaning is warranted.

For each meaning:
- statement: the meaning, in one sentence.
- contributors: the listed units that jointly support it (at least two, each one necessary), each \
with the role it plays.
- relationship: how the contributors relate (for example parallel, contrast, cause and consequence, \
part and whole).
- basis: "explicit" if a narrator or speaker states the central meaning outright; copy those exact \
words into stated_quote. It is not explicit merely because the facts it combines are stated. \
"inferred" if it is constructed from several observations or relationships; implicit meaning is \
legitimate when the units support it. "speculative" if it needs assumptions the evidence does not \
sufficiently support (for example how people feel, or what something symbolizes, when no unit shows it).
- kind: "emergent_meaning" if a new significance arises from the units together; \
"state_consequence" if it only states a factual consequence (something is now lost, impossible or \
different).
- relation_to_existing and related_to:
  "reinforces" an existing constructed meaning when it is the same meaning, now supported by further \
units (list them among the contributors); repeating a meaning without new support adds nothing;
  "extends" an existing constructed meaning when it adds a distinct aspect or perspective;
  "supplements" or "challenges" an existing reading of a unit (give that unit's id);
  "new" otherwise (related_to "").
- justification: how the contributors jointly support it.
- assumptions: anything it needs that no listed unit states or clearly implies; empty if none.
- limitations: what the units do not show. confidence: 0.0-1.0.

Rules: units that are merely associated or share a topic do not make a meaning. Keep distinct \
interpretations distinct even when they share evidence. Use only what the listed units say; do not \
use knowledge of how the text continues or of other works. Prefer zero to two meanings. If none is \
warranted, return an empty list and say why in no_new_meaning. In prose, refer to units by label, \
never by id."""


# ---------- triggers and context ----------

def _established_before(rels: list[Relation], uid: str, p: int) -> int:
    return sum(1 for r in rels if r.created_at < p and uid in (r.source, r.target)
               and r.type not in ("RELATES_TO", "CHANGES_STATE"))


def _near_before(rels: list[Relation], p: int) -> dict[str, set[str]]:
    """Neighbours of each unit through relations formed before p (undirected)."""
    nb: dict[str, set[str]] = {}
    for r in rels:
        if r.created_at < p:
            nb.setdefault(r.source, set()).add(r.target)
            nb.setdefault(r.target, set()).add(r.source)
    return nb


def find_triggers(store: Store, book_id: str, p: int) -> list[dict]:
    """The rules that fire for passage p, each with the earlier and new units it involves."""
    units = {u.id: u for u in store.units(book_id)}
    rels = store.relations(book_id)
    new = {uid for uid, u in units.items() if u.introduced_at == p}
    nb = _near_before(rels, p)
    out: list[dict] = []
    partners: dict[str, set[str]] = {}
    for r in rels:
        if r.created_at != p:
            continue
        ends = (r.source, r.target)
        nu = next((e for e in ends if e in new), None)
        old = next((e for e in ends if e in units and units[e].introduced_at < p), None)
        if nu is None or old is None:
            continue
        if r.type in ("REFRAMES", "CONTRADICTS"):
            out.append({"rule": "R1 reinterpretation", "units": [old, nu], "detail": f"{r.id} {r.type}"})
        if r.type == "CHANGES_STATE" and _established_before(rels, old, p) >= ESTABLISHED:
            out.append({"rule": "R3 consequential state change", "units": [old, nu], "detail": r.id})
        if r.type != "RELATES_TO":
            partners.setdefault(nu, set()).add(old)
    for nu, olds in partners.items():
        olds_sorted = sorted(olds)
        for i, a in enumerate(olds_sorted):
            for b in olds_sorted[i + 1:]:
                na, nb_ = nb.get(a, set()), nb.get(b, set())
                separate = b not in na and not (na & nb_)
                if units[a].introduced_at != units[b].introduced_at and separate:
                    out.append({"rule": "R2 bridging", "units": [a, b, nu], "detail": f"{nu} joins {a} and {b}"})
    for v in store.revisions(book_id):
        if v.passage != p:
            continue
        cause = [v.cause_unit] if v.cause_unit in units else []
        if v.kind == "interpretive":
            out.append({"rule": "R1 reinterpretation", "units": [v.unit_id, *cause], "detail": f"{v.source} revision"})
        elif _established_before(rels, v.unit_id, p) >= ESTABLISHED:
            out.append({"rule": "R3 consequential state change", "units": [v.unit_id, *cause],
                        "detail": f"{v.source} state revision"})
    for c in store.constructions(book_id):
        if c.passage >= p or c.status != "established":
            continue
        members = {x.unit_id for x in c.contributors}
        for nu, olds in partners.items():
            touched = sorted(olds & members)
            if len(touched) >= 2:
                out.append({"rule": "R4 extension", "units": [*touched, nu], "detail": f"{nu} touches {c.id}"})
    return out


def build_context(store: Store, book_id: str, p: int, triggers: list[dict]) -> tuple[list[Unit], list[Relation]]:
    """New units, trigger units, then their direct neighbours; all from passages read so far."""
    units = {u.id: u for u in store.units(book_id) if u.introduced_at <= p}
    rels = [r for r in store.relations(book_id) if r.created_at <= p and r.source in units and r.target in units]
    new = [u for u in units.values() if u.introduced_at == p]
    earlier: list[str] = []
    for t in triggers:
        for uid in t["units"]:
            if uid in units and units[uid].introduced_at < p and uid not in earlier:
                earlier.append(uid)
    # Earlier units this passage's new units were just linked to: what the passage brought into play.
    new_ids = {u.id for u in new}
    for r in sorted(rels, key=lambda r: -r.confidence):
        if r.created_at == p:
            for a, b in ((r.source, r.target), (r.target, r.source)):
                if a in new_ids and units[b].introduced_at < p and b not in earlier:
                    earlier.append(b)
    focus = list(earlier)
    for r in sorted(rels, key=lambda r: -r.confidence):
        if len(earlier) >= MAX_CONTEXT:
            break
        for a, b in ((r.source, r.target), (r.target, r.source)):
            if a in focus and b not in earlier and units[b].introduced_at < p:
                earlier.append(b)
    shown = {u.id for u in new} | set(earlier[:MAX_CONTEXT])
    links = sorted((r for r in rels if r.source in shown and r.target in shown), key=lambda r: -r.confidence)
    ordered = sorted((units[uid] for uid in shown), key=lambda u: (u.introduced_at, u.id))
    return ordered, links[:MAX_LINKS]


def reactivate(store: Store, book_id: str, p: int, context: list[Unit]) -> list[Construction]:
    """Earlier constructed meanings that share contributors with the current context."""
    ids = {u.id for u in context}
    prior = [c for c in store.constructions(book_id) if c.passage < p and c.status == "established"]
    scored = [(len(ids & {x.unit_id for x in c.contributors}), c) for c in prior]
    return [c for n, c in sorted(scored, key=lambda x: (-x[0], x[1].passage)) if n > 0][:MAX_PRIOR]


def construction_prompt(p: int, gist: str, triggers: list[dict], context: list[Unit], links: list[Relation],
                        prior: list[Construction], labels: dict[str, str]) -> str:
    units = [_unit_brief(u) | ({"new": True} if u.introduced_at == p else {}) for u in context]
    link_lines = [f"- {labels[r.source]} {r.type} {labels[r.target]}: {r.rationale[:200]}" for r in links]
    trig_lines = [f"- {t['rule']}: " + ", ".join(labels.get(u, u) for u in t["units"]) for t in triggers]
    prior_list = [{"id": c.id, "statement": c.statement, "first_formed_in_passage": c.passage + 1,
                   "supported_by": [labels.get(x.unit_id, x.unit_id) for x in c.contributors],
                   "distinct_passages": c.strength["distinct_passages"]} for c in prior]
    return (
        f"Passage {p + 1} just read: {gist}\n\n"
        f"WHY CONSTRUCTION RUNS NOW:\n" + "\n".join(trig_lines) + "\n\n"
        f"UNITS (\"new\": true marks units from passage {p + 1}):\n{json.dumps(units, indent=1)}\n\n"
        f"RECORDED LINKS among these units:\n" + ("\n".join(link_lines) or "(none)") + "\n\n"
        f"EXISTING CONSTRUCTED MEANINGS (reinforce one only with new supporting units; extend one only with a "
        f"distinct aspect):\n{json.dumps(prior_list, indent=1) if prior_list else '(none yet)'}"
    )


# ---------- duplicate detection ----------

def _jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def _containment(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def compare(statement: str, contributor_ids: set[str], earlier: list[Construction]) -> dict | None:
    """Closest earlier meaning: 'duplicate' if the wording nearly matches, 'overlap' if most
    contributors and some wording are shared, else None (deterministic)."""
    words = tokens(statement)
    best = None
    for c in earlier:
        t = _jaccard(words, tokens(c.statement))
        u = _containment(contributor_ids, {x.unit_id for x in c.contributors})
        kind = "duplicate" if t >= DUP_TEXT else "overlap" if (u >= SAME_UNITS and t >= DUP_TEXT_SAME_UNITS) else None
        rank = (kind == "duplicate", t)
        if kind and (best is None or rank > best["_rank"]):
            best = {"kind": kind, "of": c.id, "text_overlap": round(t, 2), "unit_overlap": round(u, 2), "_rank": rank}
    if best:
        best.pop("_rank")
    return best


def restates_reading(statement: str, readings: dict[str, list[str]]) -> dict | None:
    words = tokens(statement)
    for uid, texts in readings.items():
        for text in texts:
            t = _jaccard(words, tokens(text))
            if t >= DUP_TEXT:
                return {"of": uid, "text_overlap": round(t, 2)}
    return None


def _empty(s: str) -> bool:
    return s.strip().strip(".").lower() in ("", "none", "n/a", "no", "nothing")


# ---------- the operation ----------

def construct(client: StructuredClient, store: Store, book_id: str, p: int, gist: str) -> dict:
    """Run construction for passage p if a trigger fires. Returns notes for the passage record."""
    notes: dict = {"triggers": [], "context": [], "reactivated": [], "accepted": [], "pending": [],
                   "consolidated": [], "repeated": [], "rejected": [], "state_consequences": [],
                   "basis_downgraded": [], "no_new_meaning": ""}
    triggers = find_triggers(store, book_id, p)
    notes["triggers"] = triggers
    if not triggers:
        return notes
    context, links = build_context(store, book_id, p, triggers)
    prior = reactivate(store, book_id, p, context)
    labels = {u.id: u.label for u in store.units(book_id) if u.introduced_at <= p}
    notes["context"] = [u.id for u in context]
    notes["reactivated"] = [c.id for c in prior]
    raw = client.complete(
        task="construction", key=f"p{p}", system=SYSTEM,
        user=construction_prompt(p, gist, triggers, context, links, prior, labels),
        schema_name="Construction", schema=require_all(ConstructionResult.model_json_schema()),
    )
    result = ConstructionResult.model_validate(raw)
    notes["no_new_meaning"] = result.no_new_meaning
    notes |= apply(store, book_id, p, result, triggers, context, prior)
    return notes


def _evidence(units: dict[str, Unit], uids: list[str], p: int) -> list[ConstructionEvidence]:
    return [ConstructionEvidence(unit_id=uid, passage=e.passage, quote=e.quote)
            for uid in uids for e in units[uid].evidence if e.passage <= p]


def _consolidate(store: Store, book_id: str, target: Construction, p: int, roles: dict[str, str],
                 grounded: list[str], by_id: dict[str, Unit], statement: str, via: str) -> list[str]:
    """Add distinct new support to an existing meaning. Returns the units added (empty: a mere repeat)."""
    have = {x.unit_id for x in target.contributors}
    added = [uid for uid in grounded if uid not in have]
    if added:
        target.contributors += [Contributor(unit_id=uid, role=roles[uid], added_at=p) for uid in added]
        target.evidence += _evidence(by_id, added, p)
        target.reinforcements.append(Reinforcement(passage=p, new_units=added, statement=statement.strip(), via=via))
    elif p not in target.repeated_at:
        target.repeated_at.append(p)
    store.update_construction(book_id, target)
    return added


def classify_state_consequence(m, grounded: list[str], by_id: dict[str, Unit]) -> str | None:
    """For a proposal the model labelled a state consequence: None if it is plainly a factual
    consequence, else the reason it is ambiguous (and should be kept as pending)."""
    if m.relation_to_existing != "new":
        return f"labelled a state consequence, yet it {m.relation_to_existing} an existing interpretation"
    interpretive = [uid for uid in grounded if by_id[uid].kind not in FACT_KINDS]
    if interpretive:
        return "labelled a state consequence, yet it draws on " + ", ".join(
            f"a {by_id[uid].kind} ({by_id[uid].label})" for uid in interpretive)
    return None


def verify_explicit_quote(store: Store, book_id: str, quote: str, statement: str, grounded: list[str],
                          by_id: dict[str, Unit], p: int) -> ConstructionEvidence | None:
    """The quotation, if it occurs verbatim in a contributor's passage (already read) and the meaning echoes
    it: at least MIN_QUOTE_OVERLAP shared content words, and MIN_QUOTE_ECHO of the quotation's own."""
    quoted = tokens(quote)
    shared = quoted & tokens(statement)
    if len(shared) < MIN_QUOTE_OVERLAP or len(shared) < MIN_QUOTE_ECHO * len(quoted):
        return None
    texts = {q["idx"]: q["text"] for q in store.passages(book_id)}
    for uid in grounded:
        for passage in sorted({e.passage for e in by_id[uid].evidence if e.passage <= p}):
            span = locate_quote(texts.get(passage, ""), quote)
            if span:
                return ConstructionEvidence(unit_id=uid, passage=passage, quote=texts[passage][span[0]:span[1]])
    return None


def apply(store: Store, book_id: str, p: int, result: ConstructionResult, triggers: list[dict],
          context: list[Unit], prior: list[Construction]) -> dict:
    """Validate proposals, consolidate or store them. Never modifies units, relations or revisions."""
    by_id = {u.id: u for u in context}
    anchors = {uid for t in triggers for uid in t["units"]} | {u.id for u in context if u.introduced_at == p}
    shown_prior = {c.id for c in prior}
    existing = {c.id: c for c in store.constructions(book_id) if c.passage <= p}
    out: dict = {"accepted": [], "pending": [], "consolidated": [], "repeated": [], "rejected": [],
                 "state_consequences": [], "basis_downgraded": []}
    stored_now: list[Construction] = []
    taken = {c.id for c in store.constructions(book_id)}

    for m in result.meanings:
        rec = {"statement": m.statement, "contributors": [r.unit for r in m.contributors]}
        roles: dict[str, str] = {}
        for r in m.contributors:
            if r.unit in by_id and r.unit not in roles and r.role.strip():
                roles[r.unit] = r.role.strip()
        grounded = [uid for uid in roles if any(e.passage <= p for e in by_id[uid].evidence)]
        # 1. Objectively invalid or speculative: rejected, whatever the category.
        reason = None
        if len(grounded) < 2:
            reason = "fewer than two listed contributors with roles and textual evidence"
        elif not anchors & set(grounded):
            reason = "no contributor new in, or changed at, this passage"
        elif not m.justification.strip():
            reason = "no justification of how the contributors combine"
        elif m.basis == "speculative" or not _empty(m.assumptions):
            reason = "speculative: " + (m.assumptions.strip() or "classified as speculative")
        if reason:
            out["rejected"].append(rec | {"reason": reason})
            continue

        # 2. The model's category: a state consequence is withheld only when that is unambiguous.
        status, pending_reason = "established", None
        if m.kind == "state_consequence":
            pending_reason = classify_state_consequence(m, grounded, by_id)
            if pending_reason is None:
                out["state_consequences"].append(rec | {"reason": "a factual state consequence, not a meaning"})
                continue
            status = "pending"

        # 3. Explicit only with verified words that state the meaning.
        basis, explicit_quote = m.basis, None
        if basis == "explicit":
            explicit_quote = verify_explicit_quote(store, book_id, m.stated_quote, m.statement, grounded, by_id, p)
            if explicit_quote is None:
                basis = "inferred"
                out["basis_downgraded"].append(rec | {"stated_quote": m.stated_quote})

        # 4. Redundancy: genuine duplicates are consolidated (declared, or found by the wording check).
        relation, related = m.relation_to_existing, m.related_to.strip() or None
        target, via = None, ""
        if relation == "reinforces" and related in shown_prior and related in existing:
            target, via = existing[related], "model"
        else:
            match = compare(m.statement, set(grounded), list(existing.values()) + stored_now)
            if match and match["kind"] == "duplicate":
                target = existing.get(match["of"]) or next(c for c in stored_now if c.id == match["of"])
                via = "similarity"
            elif match and relation not in ("extends",):
                relation, related = "overlaps", match["of"]
        if target is not None:
            added = _consolidate(store, book_id, target, p, roles, grounded, by_id, m.statement, via)
            if target.status == "pending" and status == "established":
                target.status, target.resolved_at = "established", p
                store.update_construction(book_id, target)
            out["consolidated" if added else "repeated"].append(
                rec | {"into": target.id, "added_units": added, "via": via, "status_after": target.status})
            continue

        if relation in ("extends", "reinforces") and related not in shown_prior:
            relation, related = "new", None
        elif relation == "reinforces":
            relation = "extends"  # declared a reinforcement of a meaning not available here
        if relation in ("supplements", "challenges") and related not in by_id:
            relation, related = "new", None
        readings = {uid: [x for x in [by_id[uid].reading, *by_id[uid].other_readings] if x] for uid in grounded}
        if (dup := restates_reading(m.statement, readings)):
            out["rejected"].append(rec | {"reason": "restates a stored reading", "duplicate": dup})
            continue
        if len(stored_now) >= MAX_ACCEPTED:
            out["rejected"].append(rec | {"reason": f"more than {MAX_ACCEPTED} new meanings at one passage"})
            continue

        k = 1
        while f"c{p:02d}_{k}" in taken:
            k += 1
        cid = f"c{p:02d}_{k}"
        taken.add(cid)
        c = Construction(
            id=cid, statement=m.statement.strip(), passage=p,
            contributors=[Contributor(unit_id=uid, role=roles[uid]) for uid in grounded],
            relationship=m.relationship.strip(), basis=basis, relation_to_existing=relation, related_to=related,
            justification=m.justification.strip(), limitations=m.limitations.strip(),
            model_confidence=min(1.0, max(0.0, m.confidence)),
            evidence=_evidence(by_id, grounded, p), triggers=sorted({t["rule"] for t in triggers}),
            status=status, pending_reason=pending_reason, explicit_quote=explicit_quote,
        )
        store.add_construction(book_id, c)
        stored_now.append(c)
        out["pending" if status == "pending" else "accepted"].append(cid)
    return out
