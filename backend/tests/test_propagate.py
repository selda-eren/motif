"""Propagation on a small synthetic representation (a lighthouse, unrelated to any test text).

    P0  lamp (u00_1)  <-SUPPORTS-  ships rely on lamp (u00_2)
        lamp          <-RELATES_TO- lamp painted red (u00_3)
    P1  lamp on the town crest (u01_1) -REFINES-> lamp
        harbour fees (u01_2) -CAUSES-> ships rely on lamp      (two hops from the lamp)
    P2  storm breaks the lamp (u02_1) -CHANGES_STATE-> lamp    (the change being propagated)
    P3  keeper retires (u03_1) -RELATES_TO-> lamp              (not yet read when P2 is processed)
"""
import json

from motif import integrate, propagate
from motif.schema import Evidence, Relation, Unit
from motif.store import Store

B = "lighthouse"


def _unit(uid, passage, label):
    return Unit(id=uid, kind="situation", label=label, content=f"{label}.", participants=[],
                layer="observation", confidence=0.9, introduced_at=passage, last_active_at=passage,
                evidence=[Evidence(passage=passage, quote=f"the {label}", start=0, end=5)])


def _rel(rid, source, target, type_, passage, conf=0.8):
    return Relation(id=rid, source=source, target=target, type=type_, rationale=f"{source} {type_} {target}",
                    confidence=conf, created_at=passage)


def _store():
    store = Store(":memory:")
    for u in [_unit("u00_1", 0, "lamp"), _unit("u00_2", 0, "ships rely on lamp"),
              _unit("u00_3", 0, "lamp painted red"), _unit("u01_1", 1, "lamp on the town crest"),
              _unit("u01_2", 1, "harbour fees"), _unit("u02_1", 2, "storm breaks the lamp"),
              _unit("u03_1", 3, "keeper retires")]:
        store.add_unit(B, u)
    for r in [_rel("r00_1", "u00_2", "u00_1", "SUPPORTS", 0, 0.9),
              _rel("r00_2", "u00_3", "u00_1", "RELATES_TO", 0, 0.5),
              _rel("r01_1", "u01_1", "u00_1", "REFINES", 1, 0.7),
              _rel("r01_2", "u01_2", "u00_2", "CAUSES", 1, 0.9),
              _rel("r02_1", "u02_1", "u00_1", "CHANGES_STATE", 2, 0.95),
              _rel("r03_1", "u03_1", "u00_1", "RELATES_TO", 3, 0.9)]:
        store.add_relation(B, r)
    return store


class ScriptedClient:
    provenance = "model"
    model = "scripted"

    def __init__(self, response):
        self.response = response
        self.calls = []

    def complete(self, *, task, key, system, user, schema_name, schema):
        self.calls.append({"task": task, "key": key, "user": user, "schema": schema})
        return self.response


def _rc(candidate, verdict, new_reading="", coexists=False, evidence=()):
    return {"candidate": candidate, "verdict": verdict, "new_reading": new_reading, "coexists": coexists,
            "evidence": list(evidence), "rationale": "because"}


def test_candidates_are_direct_neighbours_from_passages_already_read():
    store = _store()
    changes = propagate.find_changes(store, B, 2)
    assert [(c.unit_id, c.cause_unit, c.how) for c in changes] == [("u00_1", "u02_1", "CHANGES_STATE")]
    cands = propagate.find_candidates(store, B, 2, changes)
    # Strongest link first; harbour fees is two hops away; the keeper (P3) has not been read yet.
    assert list(cands) == ["u00_2", "u01_1", "u00_3"]


def test_judgements_are_applied_selectively_and_with_evidence():
    store = _store()
    client = ScriptedClient({"reconsiderations": [
        _rc("u00_2", "reinterpretation", "Ships can no longer rely on the lamp.", evidence=["u02_1", "u00_2"]),
        _rc("u01_1", "reinterpretation", "The crest now also commemorates the lost lamp.", coexists=True,
            evidence=["u00_1"]),
        _rc("u00_3", "unchanged"),
        _rc("u01_2", "reinterpretation", "Fees fall.", evidence=["u02_1"]),        # not a candidate
        _rc("u00_2", "state_update", "Judged twice.", evidence=["u02_1"]),         # duplicate
    ]})
    store.update_unit(B, store.units(B)[3].model_copy(update={"reading": "The lamp stands for the town."}))
    notes = propagate.propagate(client, store, B, 2, "A storm breaks the lamp.")

    assert len(client.calls) == 1 and client.calls[0]["task"] == "propagation"
    assert "keeper" not in client.calls[0]["user"]  # nothing from a later passage reaches the model
    units = {u.id: u for u in store.units(B)}
    assert units["u00_2"].reading == "Ships can no longer rely on the lamp."
    assert units["u00_2"].content == "ships rely on lamp."  # the observation itself never changes
    assert units["u01_1"].reading == "The lamp stands for the town."  # symbolic reading kept...
    assert units["u01_1"].other_readings == ["The crest now also commemorates the lost lamp."]  # ...beside the new one
    assert units["u00_3"].reading is None and units["u01_2"].reading is None
    revs = {v.unit_id: v for v in store.revisions(B)}
    assert set(revs) == {"u00_2", "u01_1"}
    v = revs["u00_2"]
    assert (v.source, v.kind, v.mode, v.trigger_unit, v.cause_unit) == ("propagation", "interpretive", "replaces",
                                                                         "u00_1", "u02_1")
    assert v.evidence_units == ["u02_1", "u00_2"]
    assert revs["u01_1"].mode == "coexists"
    assert [d["verdict"] for d in notes["decisions"]] == ["reinterpretation", "reinterpretation", "unchanged"]
    assert len(notes["rejected"]) == 2


def test_revision_without_evidence_from_the_change_is_rejected():
    store = _store()
    client = ScriptedClient({"reconsiderations": [
        _rc("u00_2", "reinterpretation", "Ships rely on luck.", evidence=["u00_2"]),       # only itself
        _rc("u00_3", "state_update", "Paint peeling.", evidence=["u03_1"]),               # future unit
    ]})
    notes = propagate.propagate(client, store, B, 2, "A storm breaks the lamp.")
    assert store.revisions(B) == [] and len(notes["rejected"]) == 2


def test_state_update_leaves_the_reading_alone():
    store = _store()
    store.update_unit(B, store.units(B)[1].model_copy(update={"reading": "Trade depends on the light."}))
    client = ScriptedClient({"reconsiderations": [
        _rc("u00_2", "state_update", "Ships now sail without the light.", evidence=["u02_1"])]})
    propagate.propagate(client, store, B, 2, "A storm breaks the lamp.")
    u = {u.id: u for u in store.units(B)}["u00_2"]
    assert (u.reading, u.state) == ("Trade depends on the light.", "Ships now sail without the light.")
    assert store.revisions(B)[0].kind == "state"


def test_propagation_is_one_level_and_bounded():
    store = _store()
    for i in range(10):  # many neighbours of the lamp
        store.add_unit(B, _unit(f"u01_{i + 3}", 1, f"neighbour {i}"))
        store.add_relation(B, _rel(f"r01_{i + 3}", f"u01_{i + 3}", "u00_1", "SUPPORTS", 1, 0.6))
    store.add_relation(B, _rel("r02_2", "u02_1", "u00_2", "CONTRADICTS", 2, 0.9))  # a second change
    changes = propagate.find_changes(store, B, 2)
    cands = propagate.find_candidates(store, B, 2, changes)
    assert len(cands) <= propagate.MAX_CANDIDATES
    assert "u01_2" in cands  # harbour fees: a neighbour of the second changed unit gets a slot
    client = ScriptedClient({"reconsiderations": [
        _rc(c, "reinterpretation", f"new {c}", evidence=["u02_1"]) for c in cands]})
    propagate.propagate(client, store, B, 2, "A storm breaks the lamp.")
    # Propagation's own revisions do not count as changes, so nothing is propagated further.
    assert [c.unit_id for c in propagate.find_changes(store, B, 2)] == [c.unit_id for c in changes]
    assert len(client.calls) == 1


def test_no_change_means_no_call():
    store = _store()
    client = ScriptedClient({"reconsiderations": []})
    notes = propagate.propagate(client, store, B, 1, "Nothing changes.")
    assert client.calls == [] and notes["changes"] == []


def test_schema_sent_to_the_model_requires_every_field():
    store = _store()
    client = ScriptedClient({"reconsiderations": []})
    propagate.propagate(client, store, B, 2, "A storm breaks the lamp.")
    schema = client.calls[0]["schema"]
    rc = schema["$defs"]["Reconsideration"]
    assert set(rc["required"]) == set(rc["properties"])
    json.dumps(schema)
