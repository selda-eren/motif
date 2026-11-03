"""Constructed meanings on a small synthetic representation (scripted model, no API calls).

    P0  violin (u00_1), Ana plays every evening (u00_2)        u00_2 SUPPORTS u00_1
    P1  telescope (u01_1), Ben watches the stars (u01_2)       u01_2 SUPPORTS u01_1
    P2  Ana sells the violin to buy Ben a lens (u02_1)         u02_1 CHANGES_STATE u00_1, u02_1 SUPPORTS u01_1,
                                                               u02_1 REFRAMES u00_2 (triggers R1)
    P3  Ben sells the telescope (u03_1)                        not yet read when P2 is processed
"""
from motif import construct
from motif.experimental.constructive import representation_fingerprint
from motif.schema import ConstructionResult, Evidence, Relation, Unit
from motif.store import Store

B = "b"


def _unit(uid, passage, label, quote=None):
    q = quote or f"the {label}"
    return Unit(id=uid, kind="event", label=label, content=f"{label}.", participants=[], layer="observation",
                confidence=0.9, introduced_at=passage, last_active_at=passage,
                evidence=[Evidence(passage=passage, quote=q, start=0, end=len(q))])


def _store():
    store = Store(":memory:")
    for u in [_unit("u00_1", 0, "Ana's violin"), _unit("u00_2", 0, "Ana plays every evening"),
              _unit("u01_1", 1, "Ben's telescope"), _unit("u01_2", 1, "Ben watches the stars"),
              _unit("u02_1", 2, "Ana sells the violin for a lens"), _unit("u03_1", 3, "Ben sells the telescope")]:
        store.add_unit(B, u)
    for r in [("r00_1", "u00_2", "u00_1", "SUPPORTS", 0), ("r01_1", "u01_2", "u01_1", "SUPPORTS", 1),
              ("r01_2", "u01_1", "u00_1", "RELATES_TO", 1),
              ("r02_1", "u02_1", "u00_1", "CHANGES_STATE", 2), ("r02_2", "u02_1", "u01_1", "SUPPORTS", 2),
              ("r02_3", "u02_1", "u00_2", "REFRAMES", 2),
              ("r03_1", "u03_1", "u01_1", "CHANGES_STATE", 3)]:
        store.add_relation(B, Relation(id=r[0], source=r[1], target=r[2], type=r[3], rationale="r",
                                       confidence=0.9, created_at=r[4]))
    return store


class ScriptedClient:
    provenance = "model"
    model = "scripted"

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, task, key, system, user, schema_name, schema):
        self.calls.append({"task": task, "key": key, "user": user, "schema": schema})
        return self.responses.pop(0)


def _m(statement, units, **kw):
    return {"statement": statement, "contributors": [{"unit": u, "role": f"role of {u}"} for u in units],
            "relationship": "parallel", "basis": "inferred", "stated_quote": "", "kind": "emergent_meaning",
            "relation_to_existing": "new", "related_to": "", "justification": "together they show it",
            "assumptions": "", "limitations": "l", "confidence": 0.7} | kw


def _resp(*meanings, why=""):
    return {"meanings": list(meanings), "no_new_meaning": why}


def test_meaning_is_stored_with_contributors_and_evidence_and_units_are_untouched():
    store = _store()
    before = representation_fingerprint(store)  # units, evidence, relations, revisions, ...; not constructions
    client = ScriptedClient(_resp(_m("Ana gives up her own pleasure to serve Ben's.", ["u02_1", "u00_2", "u01_2"])))
    notes = construct.construct(client, store, B, 2, "Ana sells her violin.")

    assert notes["accepted"] == ["c02_1"] and len(client.calls) == 1
    (c,) = store.constructions(B)
    assert [x.unit_id for x in c.contributors] == ["u02_1", "u00_2", "u01_2"]
    assert {e.quote for e in c.evidence} == {"the Ana sells the violin for a lens", "the Ana plays every evening",
                                             "the Ben watches the stars"}
    assert c.passage == 2 and c.triggers == ["R1 reinterpretation"]
    # Units, relations and revisions are exactly as before (constructions live in their own table).
    assert representation_fingerprint(store) == before
    assert all(u.reading is None and not u.other_readings for u in store.units(B))


def test_snapshot_exposes_constructions_for_journey_and_api():
    from motif import graph
    store = _store()
    store.upsert_book(type("Bk", (), {"id": B, "title": "t", "author": "a", "genre": "g", "meta": {}})(), "model", "m")
    construct.construct(ScriptedClient(_resp(_m("Two gifts mirror each other.", ["u02_1", "u01_2"]))),
                        store, B, 2, "g")
    assert graph.snapshot(store, B)["constructions"][0]["id"] == "c02_1"


def test_invalid_contributors_are_rejected():
    store = _store()
    client = ScriptedClient(_resp(
        _m("Only one unit.", ["u02_1"]),
        _m("Ghost unit.", ["u02_1", "u99_9"]),
        _m("Cites a constructed meaning as a contributor.", ["u02_1", "c01_1"]),
        _m("No anchor in this passage.", ["u00_1", "u01_2"]),
        _m("Missing role.", ["u02_1", "u00_2"]) | {"contributors": [
            {"unit": "u02_1", "role": "x"}, {"unit": "u00_2", "role": " "}]},
    ))
    notes = construct.construct(client, store, B, 2, "g")
    assert store.constructions(B) == [] and len(notes["rejected"]) == 5


def test_no_unit_or_quotation_from_a_later_passage_is_used():
    store = _store()
    store.add_evidence(B, "u01_2", Evidence(passage=3, quote="a later quotation", start=0, end=5))
    client = ScriptedClient(_resp(
        _m("Both sell what they love.", ["u02_1", "u03_1"]),          # u03_1 is from passage 4
        _m("Ana's sale answers Ben's stargazing.", ["u02_1", "u01_2"])))
    notes = construct.construct(client, store, B, 2, "g")
    prompt = client.calls[0]["user"]
    assert "u03_1" not in prompt and "sells the telescope" not in prompt and "later quotation" not in prompt
    assert "u03_1" not in notes["context"]
    (c,) = store.constructions(B)
    assert all(e.passage <= 2 for e in c.evidence)
    assert notes["rejected"][0]["contributors"] == ["u02_1", "u03_1"]


def test_extension_of_an_earlier_meaning_keeps_the_link():
    store = _store()
    construct.construct(ScriptedClient(_resp(_m("Ana sacrifices her violin for Ben.", ["u02_1", "u00_1"]))),
                        store, B, 2, "g")
    # Reprocessing passage 2 with a later meaning that extends the first (same passage is allowed here).
    prior = construct.reactivate(store, B, 3, store.units(B))
    assert [c.id for c in prior] == ["c02_1"]
    result = ConstructionResult.model_validate(_resp(_m(
        "Ana's sacrifice is answered by Ben's matching sale.", ["u03_1", "u02_1"],
        relation_to_existing="extends", related_to="c02_1")))
    triggers = [{"rule": "R3 consequential state change", "units": ["u01_1", "u03_1"], "detail": ""}]
    out = construct.apply(store, B, 3, result, triggers, store.units(B), prior)
    (c,) = [c for c in store.constructions(B) if c.id in out["accepted"]]
    assert (c.relation_to_existing, c.related_to) == ("extends", "c02_1")


def test_plain_state_consequences_and_speculative_meanings_are_not_stored():
    store = _store()
    notes = construct.construct(ScriptedClient(_resp(
        _m("Ana can no longer play.", ["u02_1", "u00_2"], kind="state_consequence"),
        _m("The violin now symbolizes loss for the town.", ["u02_1", "u00_1"],
           assumptions="how the town feels about the violin"))), store, B, 2, "g")
    assert store.constructions(B) == []
    assert notes["state_consequences"][0]["statement"] == "Ana can no longer play."
    assert notes["rejected"][0]["reason"].startswith("speculative")


def test_no_new_meaning_is_a_valid_outcome():
    store = _store()
    notes = construct.construct(ScriptedClient(_resp(why="only associations")), store, B, 2, "g")
    assert store.constructions(B) == [] and notes["no_new_meaning"] == "only associations"


def test_runs_only_when_triggered_once_per_passage_and_never_on_its_own_output():
    store = _store()
    client = ScriptedClient()
    assert construct.construct(client, store, B, 0, "g")["triggers"] == [] and client.calls == []
    before = construct.find_triggers(store, B, 2)
    client = ScriptedClient(_resp(_m("Two gifts mirror each other.", ["u02_1", "u01_2"])))
    construct.construct(client, store, B, 2, "g")
    assert len(client.calls) == 1
    assert construct.find_triggers(store, B, 2) == before  # its own meanings are not triggers
    rc = client.calls[0]["schema"]["$defs"]["ProposedMeaning"]
    assert set(rc["required"]) == set(rc["properties"])


# ---------- Milestone 5: triggers ----------

def _rules(store, p):
    return sorted({t["rule"] for t in construct.find_triggers(store, B, p)})


def _bare(*rels):
    store = Store(":memory:")
    for uid, p in [("u00_1", 0), ("u01_1", 1), ("u01_2", 1), ("u02_1", 2)]:
        store.add_unit(B, _unit(uid, p, uid))
    for i, (s, t, ty, p) in enumerate(rels):
        store.add_relation(B, Relation(id=f"r{i}", source=s, target=t, type=ty, rationale="r", confidence=0.9,
                                       created_at=p))
    return store


def test_a_long_range_link_alone_no_longer_triggers():
    store = _bare(("u02_1", "u00_1", "SUPPORTS", 2))  # two passages back, but nothing else
    assert _rules(store, 2) == []


def test_bridging_requires_previously_separate_units():
    links = [("u02_1", "u00_1", "SUPPORTS", 2), ("u02_1", "u01_1", "CAUSES", 2)]
    assert _rules(_bare(*links), 2) == ["R2 bridging"]
    # A common neighbour (path of length two) means they were already connected.
    assert _rules(_bare(*links, ("u01_2", "u00_1", "REFINES", 1), ("u01_2", "u01_1", "REFINES", 1)), 2) == []


def test_state_change_triggers_only_for_established_units():
    change = ("u02_1", "u00_1", "CHANGES_STATE", 2)
    assert _rules(_bare(change, ("u01_1", "u00_1", "SUPPORTS", 1)), 2) == []
    assert _rules(_bare(change, ("u01_1", "u00_1", "SUPPORTS", 1), ("u01_2", "u00_1", "CAUSES", 1)), 2) \
        == ["R3 consequential state change"]


def test_touching_two_contributors_of_a_meaning_offers_an_extension():
    store = _bare(("u02_1", "u00_1", "SUPPORTS", 2), ("u02_1", "u01_1", "SUPPORTS", 2), ("u01_1", "u00_1", "SUPPORTS", 1))
    assert _rules(store, 2) == []
    result = ConstructionResult.model_validate(_resp(_m("A pair.", ["u01_1", "u00_1"])))
    construct.apply(store, B, 1, result, [{"rule": "x", "units": ["u01_1"]}], store.units(B), [])
    assert _rules(store, 2) == ["R4 extension"]


# ---------- Milestone 5: consolidation, overlap, coexistence ----------

def _seeded():
    """c02_1 'Ana sacrifices her violin for Ben' built at passage 2; then passage 3 is processed."""
    store = _store()
    construct.construct(ScriptedClient(_resp(_m("Ana sacrifices her violin for Ben.", ["u02_1", "u00_1"]))),
                        store, B, 2, "g")
    prior = store.constructions(B)
    triggers = [{"rule": "R3 consequential state change", "units": ["u01_1", "u03_1"]}]
    return store, prior, triggers


def _apply3(store, prior, triggers, *meanings):
    return construct.apply(store, B, 3, ConstructionResult.model_validate(_resp(*meanings)), triggers,
                           store.units(B), prior)


def test_reinforcement_adds_distinct_evidence_and_keeps_the_original_meaning():
    store, prior, triggers = _seeded()
    out = _apply3(store, prior, triggers, _m("Both give up a treasure for the other.", ["u03_1", "u02_1", "u00_1"],
                                             relation_to_existing="reinforces", related_to="c02_1"))
    (c,) = store.constructions(B)
    assert out["consolidated"][0]["added_units"] == ["u03_1"] and out["accepted"] == []
    assert c.statement == "Ana sacrifices her violin for Ben."  # original wording kept
    assert [(x.unit_id, x.added_at) for x in c.contributors] == [("u02_1", None), ("u00_1", None), ("u03_1", 3)]
    assert c.reinforcements[0].statement == "Both give up a treasure for the other."  # its perspective kept
    assert c.strength == {"distinct_units": 3, "distinct_passages": 3, "reinforcements": 1}


def test_repeating_a_meaning_without_new_evidence_adds_no_strength():
    store, prior, _ = _seeded()
    before = store.constructions(B)[0].strength
    out = _apply3(store, prior, [{"rule": "R1 reinterpretation", "units": ["u00_1"]}],
                  _m("Ana sacrifices her violin for Ben.", ["u02_1", "u00_1"], relation_to_existing="reinforces",
                     related_to="c02_1", confidence=0.99))
    (c,) = store.constructions(B)
    assert out["repeated"][0]["into"] == "c02_1" and c.repeated_at == [3]
    assert c.strength == before  # neither repetition nor higher confidence adds strength


def test_near_identical_wording_is_consolidated_even_if_declared_new():
    store, prior, triggers = _seeded()
    out = _apply3(store, prior, triggers, _m("Ana sacrifices her violin for Ben, too.", ["u03_1", "u00_1"]))
    assert out["consolidated"][0]["via"] == "similarity" and len(store.constructions(B)) == 1


def test_overlapping_and_independent_meanings_are_preserved_separately():
    store, prior, triggers = _seeded()
    out = _apply3(store, prior, triggers,
                  _m("Ana's violin sacrifice now answers Ben's own loss.", ["u03_1", "u02_1", "u00_1"]),  # overlap
                  _m("Music and astronomy stand for two private worlds.", ["u03_1", "u00_2"]))            # independent
    c1, c2, c3 = store.constructions(B)
    assert out["accepted"] == ["c03_1", "c03_2"]
    assert (c2.relation_to_existing, c2.related_to) == ("overlaps", "c02_1")
    assert (c3.relation_to_existing, c3.related_to) == ("new", None)
    assert c1.contributors and len(c1.contributors) == 2  # the earlier meaning is not flattened or changed


def test_restating_a_stored_reading_is_rejected():
    store, prior, triggers = _seeded()
    u = store.units(B)[1]
    store.update_unit(B, u.model_copy(update={"reading": "Ana's evening playing is her deepest joy."}))
    out = _apply3(store, prior, triggers, _m("Ana's evening playing is truly her deepest joy.", ["u03_1", "u00_2"]))
    assert out["rejected"][0]["reason"] == "restates a stored reading"


# ---------- Milestone 5: explicit / inferred / speculative ----------

# ---------- Milestone 5: Journey transitions ----------

def test_a_meaning_reinforced_in_a_later_stage_explains_the_transition_into_it():
    from motif import explain
    store, prior, triggers = _seeded()  # c02_1 formed at passage 2 (index), from passages 0 and 2
    journey = {"stages": [{"first_passage": 0, "last_passage": 2}, {"first_passage": 3, "last_passage": 3}]}
    assert [c for c in explain.gather_candidates(store, B, journey, 0) if c["kind"] == "construction"] == []
    _apply3(store, prior, triggers, _m("Both give up a treasure for the other.", ["u03_1", "u02_1", "u00_1"],
                                       relation_to_existing="reinforces", related_to="c02_1"))
    (cand,) = [c for c in explain.gather_candidates(store, B, journey, 0) if c["kind"] == "construction"]
    assert (cand["construction_id"], cand["reinforced_at"]) == ("c02_1", [3])
    assert cand["earlier"]["passage"] == 0 and cand["later"]["passage"] == 3
