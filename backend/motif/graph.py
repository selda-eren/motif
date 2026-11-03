"""Read-side views over the stored representation (NetworkX for relational queries)."""
from __future__ import annotations

import networkx as nx

from .humanize import humanize_relation, humanize_revision
from .store import Store

# How much each kind of change alters the representation; used to find turning points.
CHANGE_WEIGHTS = {"REFRAMES": 3.0, "CONTRADICTS": 3.0, "REFINES": 2.0, "CHANGES_STATE": 1.5, "CAUSES": 1.5,
                  "SUPPORTS": 1.0, "RELATES_TO": 0.5}
REVISION_WEIGHTS = {"interpretive": 3.0, "state": 1.5}


def build_graph(store: Store, book_id: str) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    for u in store.units(book_id):
        g.add_node(u.id, unit=u)
    for r in store.relations(book_id):
        g.add_edge(r.source, r.target, key=r.id, relation=r)
    return g


def _notes(store: Store, book_id: str) -> dict[int, dict]:
    return {p["idx"]: p["notes"] for p in store.passages(book_id)}


def readable_relations(store: Store, book_id: str) -> list[dict]:
    """Relations for display: rationale with internal ids replaced by unit labels."""
    units = {u.id: u for u in store.units(book_id)}
    notes = _notes(store, book_id)
    return [r.model_dump() | {"rationale": humanize_relation(r, units, notes), "rationale_raw": r.rationale}
            for r in store.relations(book_id)]


def readable_revisions(store: Store, book_id: str) -> list[dict]:
    units = {u.id: u for u in store.units(book_id)}
    notes = _notes(store, book_id)
    out = []
    for v in store.revisions(book_id):
        reading, why = humanize_revision(v, units, notes)
        out.append(v.model_dump() | {"new_reading": reading, "rationale": why})
    return out


def _passage_text(store: Store, book_id: str) -> dict[int, str]:
    return {p["idx"]: p["text"] for p in store.passages(book_id)}


def evidence_with_context(store: Store, book_id: str, unit_id: str, window: int = 220) -> list[dict]:
    texts = _passage_text(store, book_id)
    unit = next(u for u in store.units(book_id) if u.id == unit_id)
    out = []
    for ev in unit.evidence:
        t = texts[ev.passage]
        out.append({"passage": ev.passage, "quote": ev.quote,
                    "before": t[max(0, ev.start - window):ev.start], "after": t[ev.end:ev.end + window]})
    return out


def relation_detail(store: Store, book_id: str, rel_id: str) -> dict | None:
    rel = next((r for r in store.relations(book_id) if r.id == rel_id), None)
    if rel is None:
        return None
    units = {u.id: u for u in store.units(book_id)}
    earlier, later = sorted((units[rel.source], units[rel.target]), key=lambda u: u.introduced_at)
    notes = _notes(store, book_id)
    return {
        "earlier": earlier.id, "later": later.id,
        "relation": rel.model_dump() | {"rationale": humanize_relation(rel, units, notes), "rationale_raw": rel.rationale},
        "source": units[rel.source].model_dump(),
        "target": units[rel.target].model_dump(),
        "source_evidence": evidence_with_context(store, book_id, rel.source),
        "target_evidence": evidence_with_context(store, book_id, rel.target),
    }


def cross_passage_connections(store: Store, book_id: str, top: int = 5) -> list[dict]:
    """Relations linking units first perceived in different passages: links that exist only
    because integration brought an earlier unit back into play. Ranked by type weight,
    confidence and distance."""
    units = {u.id: u for u in store.units(book_id)}
    scored = []
    for r in store.relations(book_id):
        s, t = units[r.source], units[r.target]
        gap = abs(s.introduced_at - t.introduced_at)
        if gap == 0:
            continue
        score = CHANGE_WEIGHTS[r.type] * r.confidence * (1 + 0.25 * gap)
        scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [relation_detail(store, book_id, r.id) | {"score": round(sc, 3)} for sc, r in scored[:top]]


def passage_changes(store: Store, book_id: str) -> list[dict]:
    """What changed in the representation at each passage, and how much."""
    units = {u.id: u for u in store.units(book_id)}
    rels = store.relations(book_id)
    revs = store.revisions(book_id)
    acts = store.activations(book_id)
    out = []
    for p in store.passages(book_id):
        i = p["idx"]
        p_rels = [r for r in rels if r.created_at == i]
        cross = [r for r in p_rels if min(units[r.source].introduced_at, units[r.target].introduced_at) < i]
        p_revs = [r for r in revs if r.passage == i]
        introduced = [a["unit_id"] for a in acts if a["passage"] == i and a["kind"] == "introduced"]
        reinforced = [a["unit_id"] for a in acts if a["passage"] == i and a["kind"] == "reinforced"]
        score = (sum(CHANGE_WEIGHTS[r.type] for r in cross)
                 + 0.5 * sum(CHANGE_WEIGHTS[r.type] for r in p_rels if r not in cross)
                 + sum(REVISION_WEIGHTS[v.kind] for v in p_revs) + 0.5 * len(introduced) + 0.5 * len(reinforced))
        out.append({
            "passage": i, "gist": p["gist"], "processed": bool(p["processed"]),
            "introduced": introduced, "reinforced": reinforced,
            "relations": [r.id for r in p_rels], "cross_passage_relations": [r.id for r in cross],
            "revisions": [r.model_dump() for r in p_revs], "change_score": round(score, 2),
        })
    return out


def snapshot(store: Store, book_id: str) -> dict:
    book = store.get_book(book_id)
    return {
        "book": book,
        "passages": [{k: p[k] for k in ("idx", "text", "gist", "processed")} for p in store.passages(book_id)],
        "units": [u.model_dump() for u in store.units(book_id)],
        "relations": readable_relations(store, book_id),
        "revisions": readable_revisions(store, book_id),
        "changes": passage_changes(store, book_id),
        "constructions": [c.model_dump() for c in store.constructions(book_id)],
    }
