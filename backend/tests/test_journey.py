import re

import pytest

from motif import graph
from motif.journey import JourneyOut, representation_digest, synthesize, validate
from motif.llm import FixtureClient


@pytest.fixture()
def journey(settings, demo_store):
    return synthesize(FixtureClient(settings.demo_dir / "plato_cave.fixture.json"), demo_store, "plato_cave")


def test_demo_journey_is_valid_and_stored(journey, demo_store):
    assert journey["warnings"] == []
    assert 4 <= len(journey["stages"]) <= 6
    assert journey["provenance"] == "demo-fixture"
    assert demo_store.get_journey("plato_cave") == journey


def test_stages_cover_passages_in_order(journey, demo_store):
    n = len(demo_store.passages("plato_cave"))
    stages = journey["stages"]
    assert stages[0]["first_passage"] == 0 and stages[-1]["last_passage"] == n - 1
    for a, b in zip(stages, stages[1:]):
        assert b["first_passage"] == a["last_passage"] + 1


def test_every_stage_cites_grounded_units_inside_it(journey, demo_store):
    units = {u.id: u for u in demo_store.units("plato_cave")}
    for s in journey["stages"]:
        assert s["key_units"]
        for uid in s["key_units"]:
            assert s["first_passage"] <= units[uid].introduced_at <= s["last_passage"]
            assert units[uid].evidence  # every cited unit carries a verbatim quotation
    assert journey["stages"][-1]["leads_to_next"] == "" and journey["stages"][-1]["bridge_relations"] == []


def test_validation_repairs_ranges_and_drops_bad_citations(demo_store):
    raw = JourneyOut.model_validate({"overview": "o", "stages": [
        {"title": "A", "summary": "s", "first_passage": 2, "last_passage": 3, "key_units": ["u00_1", "u99_9"],
         "leads_to_next": "because u05_3 matters", "bridge_relations": ["r05_2", "r99_9"]},
        {"title": "B", "summary": "s", "first_passage": 4, "last_passage": 6, "key_units": ["u04_1"],
         "leads_to_next": "x", "bridge_relations": []},
        {"title": "C", "summary": "s", "first_passage": 7, "last_passage": 8, "key_units": [],
         "leads_to_next": "x", "bridge_relations": []},
        {"title": "D", "summary": "s", "first_passage": 9, "last_passage": 9, "key_units": ["u08_1"],
         "leads_to_next": "ignored for last", "bridge_relations": ["r08_1"]},
    ]})
    j = validate(raw, demo_store, "plato_cave")
    assert [(s["first_passage"], s["last_passage"]) for s in j["stages"]] == [(0, 2), (3, 5), (6, 7), (8, 8)]
    assert j["stages"][0]["key_units"] == ["u00_1"]
    assert j["stages"][0]["bridge_relations"] == ["r05_2"]
    assert "‘Learning as turning the soul’" in j["stages"][0]["leads_to_next"]
    assert j["stages"][2]["key_units"], "falls back to the most connected units"
    assert j["stages"][-1]["leads_to_next"] == "" and j["stages"][-1]["bridge_relations"] == []
    assert any("u99_9" in w for w in j["warnings"]) and any("r99_9" in w for w in j["warnings"])


def test_digest_contains_representation_not_source_text(demo_store):
    digest = representation_digest(demo_store, "plato_cave")
    assert "u05_3" in digest and "REFRAMES" in digest
    # The synthesis model gets the representation, never the passages themselves.
    for p in demo_store.passages("plato_cave"):
        assert p["text"][:120] not in digest


def test_snapshot_text_has_no_internal_ids(settings, cave):
    from motif.store import Store
    store = Store(settings.db_path)
    if not store.get_book("plato_cave"):
        pytest.skip("no live model run in data/motif.db")
    snap = graph.snapshot(store, "plato_cave")
    pattern = re.compile(r"\b(u\d{2}_\d+|n\d+|NEW|TARGET)\b")
    leftovers = [r["rationale"] for r in snap["relations"] if pattern.search(r["rationale"])]
    leftovers += [v["rationale"] + v["new_reading"] for v in snap["revisions"]
                  if pattern.search(v["rationale"] + v["new_reading"])]
    assert leftovers == []
