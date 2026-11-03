from motif.activation import activate, activate_for_units, stem
from motif.schema import Evidence, Unit


def _unit(uid, text, passage=0):
    return Unit(id=uid, kind="claim", label=text[:20], content=text, participants=[], layer="observation",
                confidence=0.8, introduced_at=passage, last_active_at=passage,
                evidence=[Evidence(passage=passage, quote=text, start=0, end=len(text))])


def test_stem_merges_inflections():
    assert stem("turning") == stem("turned") == stem("turn")
    assert stem("shadows") == stem("shadow")


def test_activation_recalls_by_shared_terms():
    units = [_unit("a", "the prisoners cannot turn their heads"), _unit("b", "the sun gives the seasons")]
    hits = activate("the soul must be turned around", units, now=3)
    assert [u.id for _, u, _ in hits] == ["a"]
    assert "turn" in hits[0][2]


def test_salience_keeps_central_threads_in_memory():
    units = [_unit("a", "shadows on the wall"), _unit("b", "unrelated fire")]
    chosen = activate_for_units(["completely different words"], units, now=5, salience={"b": 4, "a": 1})
    assert [u.id for u in chosen] == ["b"]
