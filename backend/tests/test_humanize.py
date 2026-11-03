from motif.humanize import humanize, humanize_relation, temp_id_map
from motif.schema import Evidence, Relation, Unit


def _u(uid, label, p):
    return Unit(id=uid, kind="claim", label=label, content="c", participants=[], layer="observation",
                confidence=0.9, introduced_at=p, last_active_at=p,
                evidence=[Evidence(passage=p, quote="q", start=0, end=1)])


UNITS = {u.id: u for u in [_u("u00_1", "Chained prisoners", 0), _u("u03_2", "Cave as visible world", 3)]}


def test_ids_temp_ids_and_roles_become_labels():
    temp = {"n2": "u03_2"}
    text = "u00_1 says X; n2 says Y. NEW reframes TARGET's meaning."
    out = humanize(text, UNITS, temp, new_id="u03_2", target_id="u00_1")
    assert out == ("‘Chained prisoners’ says X; ‘Cave as visible world’ says Y. "
                   "‘Cave as visible world’ reframes ‘Chained prisoners’'s meaning.")


def test_relation_roles_follow_which_unit_is_new():
    r = Relation(id="r03_1", source="u00_1", target="u03_2", type="CAUSES", rationale="TARGET follows from NEW",
                 confidence=0.8, created_at=3)
    assert humanize_relation(r, UNITS, {}) == "‘Chained prisoners’ follows from ‘Cave as visible world’"


def test_temp_map_reconstruction_is_conservative():
    assert temp_id_map({"added": ["u03_1", "u03_2"]}) == {"n1": "u03_1", "n2": "u03_2"}
    assert temp_id_map({"added": ["u03_1"], "merged": [{"new": "x", "into": "u00_1"}]}) == {}
    assert temp_id_map({"temp_ids": {"n1": "u00_1"}}) == {"n1": "u00_1"}


def test_plain_words_are_untouched():
    assert humanize("NEWS and TARGETS in 2n1 form", UNITS, {}) == "NEWS and TARGETS in 2n1 form"
