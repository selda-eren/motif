"""Milestone 5.1 regressions. The first test replays a saved model output (M5 replicate B, Magi passage 6);
the rest use small synthetic representations and a scripted model. No API calls."""
import json
from pathlib import Path

from motif import construct, explain, journey
from motif.experimental.constructive import representation_fingerprint
from motif.schema import Construction, ConstructionResult, Evidence, Relation, Unit
from motif.store import Store
from motif.text import Passage

M5 = Path(__file__).resolve().parents[2] / "docs" / "experiments" / "m5_refinement"
MAGI = "gift_of_the_magi"


def _replay_magi_p6():
    """Rebuild the store as it was before construction at Magi passage 6 in M5 replicate B, and the saved
    response, triggers, context and reactivated meanings of that call."""
    snap = json.loads((M5 / f"{MAGI}.m5B.json").read_text())
    raw = json.loads((M5 / f"{MAGI}.m5B.raw.json").read_text())
    store = Store(":memory:")
    for u in snap["units"]:
        store.add_unit(MAGI, Unit.model_validate(u))
    for r in snap["relations"]:
        store.add_relation(MAGI, Relation.model_validate({k: r[k] for k in Relation.model_fields}))
    store.ensure_passages(MAGI, [Passage(index=p["idx"], text=p["text"], start=0, end=len(p["text"]))
                                 for p in snap["passages"]])
    for c in snap["constructions"]:
        if c["passage"] < 5:
            store.add_construction(MAGI, Construction.model_validate(c))
    notes = next(p["notes"]["construction"] for p in raw["passage_notes"] if p["idx"] == 5)
    call = next(c for c in raw["llm_calls_since_start"] if c["task"] == "construction"
                and "Passage 6 just read" in c["request"]["messages"][1]["content"])
    units = {u.id: u for u in store.units(MAGI)}
    context = [units[i] for i in notes["context"]]
    prior = [c for c in store.constructions(MAGI) if c.id in notes["reactivated"]]
    return store, ConstructionResult.model_validate(call["response"]), notes["triggers"], context, prior


def test_saved_mutual_sacrifice_proposal_is_kept_as_pending_not_discarded():
    store, result, triggers, context, prior = _replay_magi_p6()
    assert result.meanings[0].kind == "state_consequence"  # the label that got it discarded in M5 replicate B
    before_units = representation_fingerprint(store)
    before = {c.id: c.model_dump() for c in store.constructions(MAGI)}

    out = construct.apply(store, MAGI, 5, result, triggers, context, prior)

    stored = {c.id: c for c in store.constructions(MAGI)}
    (pid,) = out["pending"]
    mutual = stored[pid]
    assert mutual.status == "pending" and "extends an existing interpretation" in mutual.pending_reason
    assert {x.unit_id for x in mutual.contributors} == {"u02_1", "u05_4", "u05_2", "u02_3"}  # both sales kept
    assert out["state_consequences"] == [] and out["rejected"] == []
    (aid,) = out["accepted"]  # the second proposal is established as before
    assert stored[aid].status == "established"
    # Observations and the earlier meanings are untouched.
    assert representation_fingerprint(store) == before_units
    assert all(stored[k].model_dump() == v for k, v in before.items())


def test_pending_meaning_is_never_presented_as_established():
    store, result, triggers, context, prior = _replay_magi_p6()
    construct.apply(store, MAGI, 5, result, triggers, context, prior)
    pending = [c for c in store.constructions(MAGI) if c.status == "pending"]
    assert pending
    store.upsert_book(type("Bk", (), {"id": MAGI, "title": "t", "author": "a", "genre": "g", "meta": {}})(), "model", "m")
    digest = journey.representation_digest(store, MAGI)
    assert all(c.statement not in digest for c in pending)
    assert all(c.id not in {x.id for x in construct.reactivate(store, MAGI, 6, store.units(MAGI))} for c in pending)
    j = {"stages": [{"first_passage": 0, "last_passage": 4}, {"first_passage": 5, "last_passage": 5}]}
    ids = {c.get("construction_id") for c in explain.gather_candidates(store, MAGI, j, 0)}
    assert not ids & {c.id for c in pending}


# ---------- small synthetic representation ----------

B = "b"
P0 = "Ana kept her violin for twenty years. She played it every evening."
P1 = "Ben kept a telescope. He watched the stars."
P2 = "Ana sold the violin to buy Ben a lens. Love is worth more than music, said the narrator."


def _unit(uid, passage, kind, quote, text):
    start = text.index(quote)
    return Unit(id=uid, kind=kind, label=quote[:30], content=quote, participants=[], layer="observation",
                confidence=0.9, introduced_at=passage, last_active_at=passage,
                evidence=[Evidence(passage=passage, quote=quote, start=start, end=start + len(quote))])


def _store():
    store = Store(":memory:")
    store.ensure_passages(B, [Passage(index=i, text=t, start=0, end=len(t)) for i, t in enumerate([P0, P1, P2])])
    for u in [_unit("u00_1", 0, "entity", "Ana kept her violin for twenty years", P0),
              _unit("u00_2", 0, "event", "She played it every evening", P0),
              _unit("u01_1", 1, "entity", "Ben kept a telescope", P1),
              _unit("u02_1", 2, "event", "Ana sold the violin to buy Ben a lens", P2),
              _unit("u02_2", 2, "claim", "Love is worth more than music, said the narrator", P2)]:
        store.add_unit(B, u)
    for rid, s, t, ty in [("r02_1", "u02_1", "u00_1", "CHANGES_STATE"), ("r02_2", "u02_1", "u00_2", "REFRAMES"),
                          ("r02_3", "u02_2", "u02_1", "SUPPORTS")]:
        store.add_relation(B, Relation(id=rid, source=s, target=t, type=ty, rationale="r", confidence=0.9, created_at=2))
    return store


def _m(statement, units, **kw):
    return {"statement": statement, "contributors": [{"unit": u, "role": f"role {u}"} for u in units],
            "relationship": "contrast", "basis": "inferred", "stated_quote": "", "kind": "emergent_meaning",
            "relation_to_existing": "new", "related_to": "", "justification": "together", "assumptions": "",
            "limitations": "l", "confidence": 0.7} | kw


def _apply(store, *meanings, p=2):
    triggers = construct.find_triggers(store, B, p)
    context, _ = construct.build_context(store, B, p, triggers)
    prior = construct.reactivate(store, B, p, context)
    return construct.apply(store, B, p, ConstructionResult.model_validate({"meanings": list(meanings),
                                                                           "no_new_meaning": ""}),
                           triggers, context, prior)


def test_explicit_requires_exact_words_that_state_the_meaning():
    store = _store()
    out = _apply(store,
                 _m("Love is worth more than Ana's music.", ["u02_1", "u02_2"], basis="explicit",
                    stated_quote="Love is worth more than music"),                         # verbatim, on topic
                 _m("Ana chooses Ben's stargazing over her evenings.", ["u02_1", "u00_2"], basis="explicit",
                    stated_quote="Love outweighs music entirely"))                         # not in the text
    c1, c2 = store.constructions(B)
    assert (c1.basis, c1.explicit_quote.quote, c1.explicit_quote.passage) == (
        "explicit", "Love is worth more than music", 2)
    assert (c2.basis, c2.explicit_quote) == ("inferred", None)
    assert out["basis_downgraded"][0]["stated_quote"] == "Love outweighs music entirely"


def test_a_quotation_that_only_supports_a_component_does_not_make_a_meaning_explicit():
    store = _store()
    _apply(store, _m("Ana gives up her nightly music so that Ben can see further.", ["u02_1", "u00_2"],
                     basis="explicit", stated_quote="Ana sold the violin to buy Ben a lens"))  # a fact, not the meaning
    (c,) = store.constructions(B)
    assert c.basis == "inferred"


def test_a_quotation_from_a_passage_not_yet_read_cannot_make_a_meaning_explicit():
    store = _store()
    units = {u.id: u for u in store.units(B)}
    quote = "Love is worth more than music"
    assert construct.verify_explicit_quote(store, B, quote, quote, ["u00_2", "u01_1"], units, 1) is None
    found = construct.verify_explicit_quote(store, B, quote, quote, ["u02_1", "u00_2"], units, 2)
    assert (found.passage, found.quote) == (2, quote)


def test_inferred_meaning_from_combined_evidence_is_established():
    store = _store()
    out = _apply(store, _m("Ana trades her own nightly joy for Ben's.", ["u02_1", "u00_2", "u01_1"]))
    (c,) = store.constructions(B)
    assert out["accepted"] == [c.id] and (c.basis, c.status) == ("inferred", "established")


def test_state_consequence_labels_are_resolved_or_kept_pending():
    store = _store()
    out = _apply(store,
                 _m("Ana no longer owns the violin.", ["u02_1", "u00_1"], kind="state_consequence"),   # pure fact
                 _m("Her sale enacts the narrator's claim.", ["u02_1", "u02_2"], kind="state_consequence"))  # a claim
    assert out["state_consequences"][0]["statement"] == "Ana no longer owns the violin."
    (c,) = store.constructions(B)
    assert c.status == "pending" and "claim" in c.pending_reason


def test_a_later_valid_duplicate_confirms_a_pending_meaning():
    store = _store()
    _apply(store, _m("Her sale enacts the narrator's claim about love and music.", ["u02_1", "u02_2"],
                     kind="state_consequence"))
    _apply(store, _m("Her sale enacts the narrator's claim about love and music, too.", ["u02_1", "u02_2", "u00_2"]))
    (c,) = store.constructions(B)
    assert (c.status, c.resolved_at, c.strength["distinct_units"]) == ("established", 2, 3)


def test_unsupported_proposals_are_still_rejected():
    store = _store()
    out = _apply(store,
                 _m("The violin haunts her.", ["u02_1", "u00_1"], basis="speculative"),
                 _m("Music symbolizes her youth.", ["u02_1", "u00_2"], assumptions="what music means to her"),
                 _m("Only one unit.", ["u02_1"]),
                 _m("Old facts only.", ["u00_1", "u01_1"]),
                 _m("A state consequence that is also speculative.", ["u02_1", "u02_2"], kind="state_consequence",
                    basis="speculative"))
    assert store.constructions(B) == [] and len(out["rejected"]) == 5


def _construction(relationship, statement="s", relation="new"):
    return Construction(id="c", statement=statement, passage=2, contributors=[], relationship=relationship,
                        basis="inferred", relation_to_existing=relation, related_to=None, justification="j",
                        limitations="l", model_confidence=0.5, evidence=[], triggers=[])


def test_a_constructed_meaning_supports_only_the_transitions_its_content_shows():
    assert explain.construction_supports(_construction("cause and consequence")) == {"consequence"}
    assert explain.construction_supports(_construction("parallel and reciprocal")) == {"analogy"}
    assert "reinterpretation" in explain.construction_supports(
        _construction("contrast", "useless gifts become the wisest love rather than waste"))
    assert explain.construction_supports(_construction("x", relation="extends")) == {"development"}
    assert explain.construction_supports(_construction("temporal sequence")) == set()


def test_transition_validation_uses_what_the_constructed_meaning_shows():
    journey_ = {"stages": [{"title": "a"}, {"title": "b"}]}
    cand = {"kind": "construction", "type": "CONSTRUCTED", "construction_id": "c",
            "earlier": {}, "later": {}, "adjacent": True}
    raw = explain.ExplainOut.model_validate({"stages": [], "transitions": [
        {"from_stage": 1, "kind": "consequence", "certainty": "supported", "what_changes": "w", "why": "y",
         "evidence": [{"ref": "E1", "how_it_supports": "h"}], "limitation": "", "beyond_evidence": ""}]})
    ok = explain.validate(raw, journey_, [[], []], [[cand | {"supports_kinds": ["consequence"]}]])
    assert ok["transitions"][0]["certainty"] == "supported" and ok["transitions"][0]["grounding_note"] == ""
    weak = explain.validate(raw, journey_, [[], []], [[cand | {"supports_kinds": ["analogy"]}]])
    assert weak["transitions"][0]["certainty"] == "tentative"
