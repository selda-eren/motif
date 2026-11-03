import pytest

from motif import graph
from motif.llm import FixtureClient
from motif.pipeline import process_book
from motif.schema import IntegrationResult, PerceptionResult


def test_demo_fixture_is_fully_grounded_and_consistent(demo_store):
    for notes in demo_store.reports:
        assert notes["rejected"] == [], "every demo quote must occur verbatim in its passage"
        assert notes["warnings"] == [], "demo links must only target units in working memory"


def test_every_unit_is_anchored_to_its_passage(demo_store):
    passages = {p["idx"]: p["text"] for p in demo_store.passages("plato_cave")}
    for u in demo_store.units("plato_cave"):
        assert u.evidence
        for ev in u.evidence:
            assert passages[ev.passage][ev.start:ev.end] == ev.quote


def test_emergent_connection_across_passages(demo_store):
    """Milestone 1 target: the passage-6 claim about turning the soul reframes the passage-1 chains."""
    units = {u.id: u for u in demo_store.units("plato_cave")}
    link = next(r for r in demo_store.relations("plato_cave")
                if r.type == "REFRAMES" and units[r.target].label == "Unable to turn round")
    assert units[link.source].introduced_at == 5 and units[link.target].introduced_at == 0
    assert units[link.target].reading, "the earlier unit's reading was revised"
    detail = graph.relation_detail(demo_store, "plato_cave", link.id)
    assert "turning round their heads" in detail["target_evidence"][0]["quote"]
    assert detail["source_evidence"][0]["before"]  # passage context returned with the quote


def test_reading_of_a_unit_evolves_over_several_passages(demo_store):
    shadows = next(u for u in demo_store.units("plato_cave") if u.label == "Shadows on the wall")
    history = [r for r in demo_store.revisions("plato_cave") if r.unit_id == shadows.id]
    assert [r.passage for r in history] == [1, 4, 7]
    assert history[1].old_reading == history[0].new_reading


def test_processing_is_resumable(settings, cave, demo_store):
    before = len(demo_store.units("plato_cave"))
    client = FixtureClient(settings.demo_dir / "plato_cave.fixture.json")
    assert process_book(cave, client, demo_store, log=lambda _: None) == []
    assert len(demo_store.units("plato_cave")) == before


def test_refuses_to_mix_demo_and_model_output(cave, demo_store):
    class FakeModel:
        provenance, model = "model", "x"
    with pytest.raises(ValueError, match="refusing to mix"):
        process_book(cave, FakeModel(), demo_store, log=lambda _: None)


def test_changes_and_connections(demo_store):
    changes = graph.passage_changes(demo_store, "plato_cave")
    assert len(changes) == 9 and all(c["processed"] for c in changes)
    top = graph.cross_passage_connections(demo_store, "plato_cave", top=3)
    assert len(top) == 3 and all(d["relation"]["type"] == "REFRAMES" for d in top)


def _depth(node, d=0):
    if isinstance(node, dict):
        return max([_depth(v, d + 1) for v in node.values()] or [d])
    if isinstance(node, list):
        return max([_depth(v, d + 1) for v in node] or [d])
    return d


@pytest.mark.parametrize("model", [PerceptionResult, IntegrationResult])
def test_llm_schemas_fit_documented_limits(model):
    schema = model.model_json_schema()
    assert _depth(schema) <= 10  # documented structured-output nesting limit is 10 levels
