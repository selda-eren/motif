"""Run Experiment 4: revision-oriented (A) vs. constructive (B) objective on frozen candidate sets.

  MOTIF_DB=../data/motif.exp4.db uv run python -m motif.experimental.run_exp4 check OUT_DIR
  MOTIF_DB=../data/motif.exp4.db uv run python -m motif.experimental.run_exp4 run OUT_DIR

`check` prints what each frozen input contains (free). `run` calls the model and writes results.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from .. import propagate
from ..config import REPO_ROOT, load_settings
from ..llm import MetaModelClient
from ..schema import Evidence, Relation, Unit
from ..store import Store
from . import constructive as c

EXP3 = REPO_ROOT / "docs" / "experiments" / "exp3_propagation"
CONTROL_BOOK = "control_library"


def control_store() -> Store:
    """Negative control: a change whose linked units are merely associated with it."""
    store = Store(":memory:")

    def unit(uid, passage, label, quote):
        return Unit(id=uid, kind="situation", label=label, content=f"{quote}.", participants=[],
                    layer="observation", confidence=0.9, introduced_at=passage, last_active_at=passage,
                    evidence=[Evidence(passage=passage, quote=quote, start=0, end=len(quote))])

    for u in [unit("u00_1", 0, "Library opens at nine", "The library opens at nine every weekday"),
              unit("u00_2", 0, "Old map collection", "Its reading room holds the town's collection of old maps"),
              unit("u00_3", 0, "Fishing rods lent to children", "The library lends fishing rods to children in the holidays"),
              unit("u00_4", 0, "Trout below the weir", "Trout are still caught below the weir"),
              unit("u01_1", 1, "Library now opens at ten", "From May the library opens at ten instead of nine"),
              unit("u01_2", 1, "New reading-room carpet", "A new carpet was laid in the reading room")]:
        store.add_unit(CONTROL_BOOK, u)
    for r in [Relation(id="r00_1", source="u00_2", target="u00_1", type="RELATES_TO",
                       rationale="Both describe the library.", confidence=0.6, created_at=0),
              Relation(id="r00_2", source="u00_3", target="u00_1", type="RELATES_TO",
                       rationale="Both describe the library.", confidence=0.6, created_at=0),
              Relation(id="r00_3", source="u00_4", target="u00_3", type="RELATES_TO",
                       rationale="Both concern fishing.", confidence=0.5, created_at=0),
              Relation(id="r01_1", source="u01_1", target="u00_1", type="CHANGES_STATE",
                       rationale="The opening hour moves from nine to ten.", confidence=0.95, created_at=1)]:
        store.add_relation(CONTROL_BOOK, r)
    return store


def control_case(store: Store) -> c.FrozenCase:
    """Built with Experiment 3's own functions, so the input has exactly the same form."""
    changes = propagate.find_changes(store, CONTROL_BOOK, 1)
    cands = propagate.find_candidates(store, CONTROL_BOOK, 1, changes)
    units = {u.id: u for u in store.units(CONTROL_BOOK)}
    user = propagate.propagation_prompt(1, "The library changes its opening hour and lays a new carpet.",
                                        changes, cands, units, [u for u in units.values() if u.introduced_at == 1])
    return c.FrozenCase("control_library_p2", CONTROL_BOOK, 1, user)


def load_cases(main: Store, control: Store) -> list[tuple[c.FrozenCase, Store]]:
    magi = json.loads((EXP3 / "gift_of_the_magi.runC_prop.raw.json").read_text())
    bridge = json.loads((EXP3 / "synthetic_footbridge.runS_prop.raw.json").read_text())
    return ([(k, main) for k in c.cases_from_export(magi, "gift_of_the_magi", "magi")]
            + [(k, main) for k in c.cases_from_export(bridge, "synthetic_footbridge", "bridge")]
            + [(control_case(control), control)])


def cmd_check(cases) -> None:
    for case, store in cases:
        units = {u.id: u for u in store.units(case.book_id)}
        ids = sorted(c.listed_ids(case))
        print(f"\n{case.name} (passage {case.passage + 1}): {len(ids)} units shown")
        for uid in ids:
            print(f"  {uid} P{units[uid].introduced_at + 1} {units[uid].label}")


def cmd_run(cases, main: Store, settings, out: Path) -> None:
    client = MetaModelClient(settings, main, log=print)
    before = c.representation_fingerprint(main)
    results = []
    for case, store in cases:
        t0 = time.time()
        a = c.run_revision(client, case)
        t1 = time.time()
        b = c.run_constructive(client, case)
        t2 = time.time()
        results.append({"case": case.name, "book_id": case.book_id, "passage": case.passage + 1,
                        "shown_units": sorted(c.listed_ids(case)),
                        "A_revision": c.summarize_revision(a), "B_constructive": c.validate(b, case, store),
                        "B_raw": b, "wall_s": {"A": round(t1 - t0, 1), "B": round(t2 - t1, 1)}})
    after = c.representation_fingerprint(main)
    usage = main.usage_rows(client.run_id)
    (out / "results.json").write_text(json.dumps({
        "run_id": client.run_id, "model": settings.model, "reasoning_effort": settings.reasoning_effort,
        "max_completion_tokens": settings.max_completion_tokens,
        "representation_fingerprint": {"before": before, "after": after, "unchanged": before == after},
        "usage": usage, "cases": results}, indent=1, ensure_ascii=False))
    print(f"representation unchanged: {before == after}")
    print(f"cost this run: ${sum(r['cost_usd'] for r in usage):.4f}; total in db ${main.total_spend_usd():.4f}")


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    settings = load_settings()
    store = Store(settings.db_path)
    cases = load_cases(store, control_store())
    if argv[0] == "check":
        cmd_check(cases)
    else:
        cmd_run(cases, store, settings, Path(argv[1]))


if __name__ == "__main__":
    main()
