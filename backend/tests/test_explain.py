import pytest

from motif.explain import ExplainOut, build_prompt, explain, gather_candidates, validate
from motif.journey import synthesize
from motif.llm import FixtureClient


@pytest.fixture()
def explained(settings, demo_store):
    client = FixtureClient(settings.demo_dir / "plato_cave.fixture.json")
    synthesize(client, demo_store, "plato_cave")
    return explain(client, demo_store, "plato_cave"), demo_store


def _units(store):
    return {u.id: u for u in store.units("plato_cave")}


def test_demo_explanation_is_valid(explained):
    x, store = explained
    assert x["warnings"] == []
    assert len(x["stages"]) == 5 and len(x["transitions"]) == 4
    assert store.get_journey("plato_cave")["explanation"] == x
    assert {t["kind"] for t in x["transitions"]} <= {"development", "reinterpretation", "contradiction",
                                                     "consequence", "analogy", "succession", "unclassified"}


def test_every_quotation_is_verbatim_from_its_passage(explained):
    x, store = explained
    texts = {p["idx"]: p["text"] for p in store.passages("plato_cave")}
    quotes = [q for s in x["stages"] for q in s["quotes"]]
    quotes += [side for t in x["transitions"] for e in t["evidence"] for side in (e["earlier"], e["later"])]
    assert quotes
    for q in quotes:
        assert texts[q["passage"]][q["start"]:q["end"]] == q["quote"]


def test_stage_quotations_come_from_the_stage(explained):
    x, store = explained
    journey = store.get_journey("plato_cave")
    for s, st in zip(x["stages"], journey["stages"]):
        for q in s["quotes"]:
            assert q["unit_id"] in st["key_units"]
            assert st["first_passage"] <= q["passage"] <= st["last_passage"]


def test_candidates_link_the_later_stage_back_to_earlier_ones(explained):
    _, store = explained
    journey = store.get_journey("plato_cave")
    units = _units(store)
    for i in range(len(journey["stages"]) - 1):
        nxt = journey["stages"][i + 1]
        for c in gather_candidates(store, "plato_cave", journey, i):
            assert nxt["first_passage"] <= c["later"]["passage"] <= nxt["last_passage"] or c["kind"] == "revision"
            assert c["earlier"]["passage"] < nxt["first_passage"]
            if c["kind"] == "relation":
                assert {c["earlier"]["unit_id"], c["later"]["unit_id"]} <= set(units)


def _raw(transitions, n_stages=5):
    return ExplainOut.model_validate({
        "stages": [{"stage": i + 1, "what_changes": "w", "why_it_matters": "m", "quotes": [{"ref": "Q1", "how_it_supports": "h"}]}
                   for i in range(n_stages)],
        "transitions": transitions,
    })


def _t(frm, kind, certainty="supported", evidence=(), limitation=""):
    return {"from_stage": frm, "kind": kind, "certainty": certainty, "what_changes": "c", "why": "y",
            "evidence": [{"ref": r, "how_it_supports": "s"} for r in evidence], "limitation": limitation}


@pytest.fixture()
def parts(explained):
    _, store = explained
    journey = store.get_journey("plato_cave")
    _, quotes, cands = build_prompt(store, "plato_cave", journey)
    return journey, quotes, cands


def test_claim_without_cited_evidence_is_not_presented_as_established(parts):
    journey, quotes, cands = parts
    x = validate(_raw([_t(1, "consequence"), _t(2, "succession"), _t(3, "reinterpretation", evidence=["E99"]),
                       _t(4, "unclassified")]), journey, quotes, cands)
    t1, t2, t3, t4 = x["transitions"]
    assert (t1["kind"], t1["certainty"]) == ("unclassified", "tentative") and "no recorded link" in t1["grounding_note"]
    assert t2["kind"] == "succession" and t2["limitation"]  # succession needs no link but must state its limit
    assert (t3["kind"], t3["certainty"]) == ("unclassified", "tentative") and t3["evidence"] == []
    assert any("E99" in w for w in x["warnings"])
    assert (t4["kind"], t4["certainty"]) == ("unclassified", "tentative")


def test_kind_must_match_the_type_of_cited_evidence(parts):
    journey, quotes, cands = parts
    # Transition 3->4 in the demo: E1 is a CONTRADICTS link, E2 a REFRAMES link.
    assert cands[2][0]["type"] == "CONTRADICTS" and cands[2][1]["type"] == "REFRAMES"
    x = validate(_raw([_t(1, "development", evidence=["E1"]), _t(2, "reinterpretation", evidence=["E1"]),
                       _t(3, "reinterpretation", evidence=["E1"]), _t(4, "contradiction", evidence=["E1"])]),
                 journey, quotes, cands)
    t3 = x["transitions"][2]
    assert t3["certainty"] == "tentative" and "contradicts" in t3["grounding_note"]
    assert x["transitions"][3]["certainty"] == "supported"  # CONTRADICTS supports a contradiction


def test_invalid_quotation_refs_fall_back_to_stage_quotations(parts):
    journey, quotes, cands = parts
    raw = _raw([_t(i, "succession") for i in range(1, 5)])
    raw.stages[0].quotes[0].ref = "Q42"
    x = validate(raw, journey, quotes, cands)
    assert x["stages"][0]["quotes"] and x["stages"][0]["quotes"][0]["how_it_supports"] == ""
    assert any("Q42" in w for w in x["warnings"])
