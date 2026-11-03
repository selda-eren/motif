"""Experiment 4 harness: evidence integrity and non-mutation (scripted model, no API calls)."""
from motif import propagate
from motif.experimental import constructive as c
from motif.experimental.run_exp4 import CONTROL_BOOK, control_case, control_store
from motif.schema import Evidence


class ScriptedClient:
    provenance = "model"
    model = "scripted"

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def complete(self, *, task, key, system, user, schema_name, schema):
        self.calls.append({"task": task, "system": system, "user": user, "schema_name": schema_name})
        return self.responses[task]


def _interp(contributing, **kw):
    return {"statement": "s", "contributing": contributing,
            "support": [{"unit": u, "contributes": "x"} for u in contributing], "relationship": "parallel",
            "kind": "emergent_meaning", "relation_to_existing": "new", "existing_reading_of": "",
            "justification": "j", "limitations": "l", "confidence": 0.5} | kw


def test_both_objectives_receive_the_identical_frozen_input():
    store = control_store()
    case = control_case(store)
    client = ScriptedClient({"propagation": {"reconsiderations": []},
                             "constructive": {"interpretations": [], "no_new_meaning": "nothing"}})
    c.run_revision(client, case)
    c.run_constructive(client, case)
    a, b = client.calls
    assert a["user"] == b["user"] == case.user
    assert a["system"] == propagate.SYSTEM and b["system"] == c.SYSTEM


def test_contributors_must_come_from_the_frozen_set_and_quotes_from_read_passages():
    store = control_store()
    # u00_2 gains evidence from a later passage, which must not be attached at passage 2.
    store.add_evidence(CONTROL_BOOK, "u00_2", Evidence(passage=5, quote="later quote", start=0, end=5))
    case = control_case(store)
    assert c.listed_ids(case) == {"u00_1", "u00_2", "u00_3", "u01_1", "u01_2"}
    out = c.validate({"interpretations": [
        _interp(["u01_1", "u00_2"]),                 # valid
        _interp(["u01_1", "u00_4"]),                 # trout: in the store but not shown -> only one left
        _interp(["u01_1", "u99_9", "u00_3"]),        # unknown id dropped, two remain
        _interp(["u01_1"]),                          # a single unit is not joint support
    ], "no_new_meaning": ""}, case, store)
    assert [i["contributing_valid"] for i in out["accepted"]] == [["u01_1", "u00_2"], ["u01_1", "u00_3"]]
    assert out["accepted"][1]["contributing_unknown"] == ["u99_9"]
    assert len(out["rejected"]) == 2
    quotes = {e["unit"]: [q["quote"] for q in e["quotes"]] for e in out["accepted"][0]["evidence"]}
    assert quotes["u00_2"] == ["Its reading room holds the town's collection of old maps"]  # stored, verbatim


def test_harness_never_modifies_the_representation():
    store = control_store()
    before = c.representation_fingerprint(store)
    case = control_case(store)
    client = ScriptedClient({"propagation": {"reconsiderations": [
        {"candidate": "u00_2", "verdict": "reinterpretation", "new_reading": "x", "coexists": False,
         "evidence": ["u01_1"], "rationale": "r"}]},
        "constructive": {"interpretations": [_interp(["u01_1", "u00_2"])], "no_new_meaning": ""}})
    c.summarize_revision(c.run_revision(client, case))
    c.validate(c.run_constructive(client, case), case, store)
    assert c.representation_fingerprint(store) == before
    assert store.revisions(CONTROL_BOOK) == []


def test_empty_answer_records_no_new_meaning():
    store = control_store()
    out = c.validate({"interpretations": [], "no_new_meaning": "only associations"}, control_case(store), store)
    assert out == {"accepted": [], "rejected": [], "no_new_meaning": "only associations"}
