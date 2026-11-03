from motif import integrate
from motif.schema import Evidence, IntegrationResult, Unit
from motif.store import Store


def _unit(uid, passage):
    return Unit(id=uid, kind="concept", label=uid, content=f"content {uid}", participants=[],
                layer="observation", confidence=0.6, introduced_at=passage, last_active_at=passage,
                evidence=[Evidence(passage=passage, quote=f"quote {uid}", start=0, end=5)])


def _setup():
    store = Store(":memory:")
    old = _unit("u00_1", 0)
    hidden = _unit("u00_2", 0)
    store.add_unit("b", old)
    store.add_unit("b", hidden)
    return store, {old.id: old, hidden.id: hidden}


def test_apply_adds_merges_relates_and_revises():
    store, memory = _setup()
    new = [_unit("n1", 2), _unit("n2", 2)]
    result = IntegrationResult.model_validate({"decisions": [
        {"new_unit": "n1", "action": "add", "merge_into": "", "relations": [
            {"target": "u00_1", "type": "REFRAMES", "direction": "new_to_target", "rationale": "r", "confidence": 1.7},
            {"target": "n2", "type": "CAUSES", "direction": "target_to_new", "rationale": "r", "confidence": 0.5},
            {"target": "n1", "type": "SUPPORTS", "direction": "new_to_target", "rationale": "self", "confidence": 0.5},
            {"target": "u00_2", "type": "SUPPORTS", "direction": "new_to_target", "rationale": "hidden", "confidence": 0.5},
            {"target": "u99_9", "type": "SUPPORTS", "direction": "new_to_target", "rationale": "ghost", "confidence": 0.5},
        ], "revisions": [{"target": "u00_1", "new_reading": "now a figure", "rationale": "because"}]},
        {"new_unit": "n2", "action": "merge", "merge_into": "u00_1", "relations": [], "revisions": []},
    ]})
    notes = integrate.apply(store, "b", 2, new, result, memory, allowed={"u00_1"})

    assert notes["added"] == ["u02_1"]
    assert notes["merged"] == [{"new": "n2", "into": "u00_1"}]
    rels = {(r.source, r.type, r.target): r for r in store.relations("b")}
    assert set(rels) == {("u02_1", "REFRAMES", "u00_1"), ("u00_1", "CAUSES", "u02_1")}
    assert rels[("u02_1", "REFRAMES", "u00_1")].confidence == 1.0  # clamped
    assert len(notes["warnings"]) == 2  # hidden (not activated) and unknown targets rejected

    units = {u.id: u for u in store.units("b")}
    assert units["u00_1"].reading == "now a figure"
    assert len(units["u00_1"].evidence) == 2  # merged evidence from passage 2
    assert units["u00_1"].confidence > 0.6
    rev = store.revisions("b")[0]
    assert (rev.unit_id, rev.passage, rev.old_reading, rev.cause_unit) == ("u00_1", 2, None, "u02_1")


def test_revision_of_same_passage_unit_is_rejected():
    store, memory = _setup()
    new = [_unit("n1", 0)]
    result = IntegrationResult.model_validate({"decisions": [
        {"new_unit": "n1", "action": "add", "merge_into": "", "relations": [],
         "revisions": [{"target": "u00_1", "new_reading": "x", "rationale": "y"}]}]})
    notes = integrate.apply(store, "b", 0, new, result, memory)
    assert store.revisions("b") == [] and notes["warnings"]


def test_change_over_time_is_not_a_contradiction():
    store, memory = _setup()
    new = [_unit("n1", 2), _unit("n2", 2)]
    result = IntegrationResult.model_validate({"decisions": [
        {"new_unit": "n1", "action": "add", "merge_into": "", "relations": [
            {"target": "u00_1", "type": "CHANGES_STATE", "direction": "new_to_target", "rationale": "r", "confidence": 0.9}],
         "revisions": [{"target": "u00_1", "kind": "state", "new_reading": "now gone", "coexists": False,
                        "rationale": "sold"}]},
        {"new_unit": "n2", "action": "add", "merge_into": "", "relations": [
            {"target": "u00_2", "type": "CONTRADICTS", "direction": "new_to_target", "rationale": "r", "confidence": 0.9}],
         "revisions": []},
    ]})
    integrate.apply(store, "b", 2, new, result, memory)
    units = {u.id: u for u in store.units("b")}
    assert (units["u00_1"].status, units["u00_1"].state, units["u00_1"].reading) == ("active", "now gone", None)
    assert units["u00_2"].status == "contested"
    assert store.revisions("b")[0].kind == "state"


def test_coexisting_reading_keeps_the_current_one():
    store, memory = _setup()
    memory["u00_1"].reading = "a family heirloom"
    store.update_unit("b", memory["u00_1"])
    result = IntegrationResult.model_validate({"decisions": [
        {"new_unit": "n1", "action": "add", "merge_into": "", "relations": [],
         "revisions": [{"target": "u00_1", "kind": "interpretive", "new_reading": "a sacrifice",
                        "coexists": True, "rationale": "r"}]}]})
    integrate.apply(store, "b", 2, [_unit("n1", 2)], result, memory)
    u = {u.id: u for u in store.units("b")}["u00_1"]
    assert (u.reading, u.other_readings) == ("a family heirloom", ["a sacrifice"])
    rev = store.revisions("b")[0]
    assert (rev.mode, rev.old_reading, rev.evidence_units) == ("coexists", "a family heirloom", ["u02_1", "u00_1"])


def test_older_database_gains_the_new_columns(tmp_path):
    import sqlite3
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE units (id TEXT, book_id TEXT, kind TEXT, label TEXT, content TEXT, participants_json TEXT,
            layer TEXT, confidence REAL, status TEXT, reading TEXT, introduced_at INTEGER, last_active_at INTEGER,
            PRIMARY KEY (book_id, id));
        CREATE TABLE revisions (book_id TEXT, unit_id TEXT, passage INTEGER, old_reading TEXT, new_reading TEXT,
            rationale TEXT, cause_unit TEXT);
        INSERT INTO units VALUES ('u00_1','b','concept','x','c','[]','observation',0.5,'active','r',0,0);
        INSERT INTO revisions VALUES ('b','u00_1',1,NULL,'r','why','u01_1');
    """)
    db.commit()
    db.close()
    store = Store(path)
    assert store.units("b")[0].other_readings == [] and store.units("b")[0].state is None
    rev = store.revisions("b")[0]
    assert (rev.kind, rev.mode, rev.source, rev.evidence_units) == ("interpretive", "replaces", "integration", [])
