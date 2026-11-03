"""Atomic passages and safe resumption in the core pipeline (Milestone 7). Synthetic calls only: no model API is ever used.

The offline demo fixture supplies perception and integration; propagation and construction answer with empty (valid)
results, which still exercises every stage's call, commit and rollback path.
"""
import json
import sqlite3
from dataclasses import replace

import httpx
import pytest

from motif.llm import BudgetExceeded, FixtureClient, LLMError, MetaModelClient
from motif.pipeline import process_book
from motif.store import Store
from motif.text import load_book

TASKS = ("perception", "integration", "propagation", "construction")


class Killed(BaseException):
    """A process kill: not an Exception, so nothing in the pipeline can swallow it."""


class ScriptedClient:
    """Replays the demo fixture through the SAME cache/usage side effects as MetaModelClient, and can fail on demand.
    `faults` maps (task, nth_uncached_call_of_that_task) -> "timeout" | "die_after" (raise Killed after the call completed)."""
    provenance = "demo-fixture"
    model = None

    def __init__(self, settings, store, faults=None):
        self.fixture = FixtureClient(settings.demo_dir / "plato_cave.fixture.json")
        self.store, self.faults = store, dict(faults or {})
        self.count = {t: 0 for t in TASKS}
        self.paid, self.hits = [], []

    def complete(self, *, task, key, system, user, schema_name, schema):
        ck = f"{task}/{key}"
        if (hit := self.store.cache_get(ck)) is not None:
            self.hits.append(ck)
            self.store.log_usage(ts=1.0, run_id="t", task=task, key=key, model=None, reasoning_effort="x", status="cache_hit",
                                 prompt_tokens=0, cached_tokens=0, completion_tokens=0, reasoning_tokens=0, cost_usd=0.0,
                                 latency_s=0.0, finish_reason=None, detail=None)
            return hit
        self.count[task] += 1
        fault = self.faults.get((task, self.count[task]))
        if fault == "timeout":
            self.store.log_usage(ts=1.0, run_id="t", task=task, key=key, model=None, reasoning_effort="x", status="network_error",
                                 prompt_tokens=0, cached_tokens=0, completion_tokens=0, reasoning_tokens=0, cost_usd=0.0,
                                 latency_s=0.0, finish_reason=None, detail="read timed out | billing_uncertain worst_case_usd=0.0500")
            raise LLMError("Network error calling test: timed out")
        if task == "propagation":
            out = {"reconsiderations": []}
        elif task == "construction":
            out = {"meanings": [], "no_new_meaning": "synthetic: nothing to construct"}
        else:
            out = self.fixture.complete(task=task, key=key, system=system, user=user, schema_name=schema_name, schema=schema)
        self.paid.append(ck)
        self.store.log_usage(ts=1.0, run_id="t", task=task, key=key, model=None, reasoning_effort="x", status="ok",
                             prompt_tokens=1, cached_tokens=0, completion_tokens=1, reasoning_tokens=0, cost_usd=0.01,
                             latency_s=0.1, finish_reason="stop", detail=None)
        self.store.cache_put(ck, "m", task, {"k": ck}, out)
        if fault == "die_after":
            raise Killed()
        return out


@pytest.fixture()
def book(settings):
    return load_book(settings.texts_dir, "plato_cave")


def representation(store, book_id):
    out = {}
    for t, col in (("units", "book_id"), ("evidence", "book_id"), ("activations", "book_id"), ("relations", "book_id"),
                   ("revisions", "book_id"), ("constructions", "book_id")):
        out[t] = sorted(json.dumps(dict(r), sort_keys=True) for r in store.db.execute(f"SELECT * FROM {t} WHERE {col}=?", (book_id,)))
    out["passages"] = sorted(json.dumps({k: v for k, v in dict(r).items() if k != "text"}, sort_keys=True)
                             for r in store.db.execute("SELECT * FROM passages WHERE book_id=?", (book_id,)))
    return out


def run(settings, book, path, faults=None, hard_kill_on=None):
    """One 'process': open the store, process until done or interrupted. Returns (client, store, how_it_ended)."""
    store = Store(path)
    client = ScriptedClient(settings, store, faults)
    ended = "done"
    try:
        process_book(book, client, store, propagate=True, construct=True, log=lambda _: None)
    except LLMError:
        ended = "timeout"
    except Killed:
        ended = "killed"
        if hard_kill_on:           # a real kill: the pipeline's rollback must not be needed. Simulate by dropping the
            store.db.close()       # connection with the transaction still open (SQLite discards it).
    return client, store, ended


@pytest.fixture()
def reference(settings, book, tmp_path):
    client, store, ended = run(settings, book, tmp_path / "ref" / "m.db")
    assert ended == "done"
    assert all(client.count[t] > 0 for t in TASKS), f"the reference run must exercise every stage: {client.count}"
    return representation(store, book.id), client


def assert_clean(store, book):
    units = store.units(book.id)
    keys = [(u.introduced_at, u.label, u.evidence[0].quote if u.evidence else "") for u in units]
    assert len(keys) == len(set(keys)), "no unit was added twice"
    assert len({u.id for u in units}) == len(units)
    processed = [p["idx"] for p in store.passages(book.id) if p["processed"]]
    assert processed == sorted(set(processed))
    assert all(u.introduced_at in processed for u in units), "no units from a passage that was not completed"
    assert all(r.created_at in processed for r in store.relations(book.id))


@pytest.mark.parametrize("task", TASKS)
@pytest.mark.parametrize("mode", ["timeout", "die_after", "hard_kill"])
def test_interruption_at_each_stage_is_safe_and_resumable(settings, book, tmp_path, reference, task, mode):
    ref_state, ref_client = reference
    path = tmp_path / "run" / "m.db"
    fault = "die_after" if mode == "hard_kill" else mode
    client1, store1, ended = run(settings, book, path, {(task, 1): fault}, hard_kill_on=mode == "hard_kill")
    assert ended in ("timeout", "killed")
    if mode != "hard_kill":
        store1.db.close()
    # What the interruption left behind: only whole passages, and every completed call is already durable
    store = Store(path)
    assert_clean(store, book)
    done_before = [p["idx"] for p in store.passages(book.id) if p["processed"]]
    assert len(done_before) < len(store.passages(book.id))
    paid_before = list(client1.paid)
    assert all(store.cache_get(c) is not None for c in paid_before), "every paid call survived the interruption"
    store.db.close()
    # Resume (no more faults): finishes, identical to an uninterrupted run, paying only for what was never completed
    client2, store2, ended2 = run(settings, book, path)
    assert ended2 == "done"
    assert representation(store2, book.id) == ref_state
    assert_clean(store2, book)
    assert set(client2.paid).isdisjoint(paid_before), "no completed call was paid for again"
    assert len(paid_before) + len(client2.paid) == len(ref_client.paid), "every call was paid for exactly once overall"
    if paid_before:
        assert any(h in paid_before for h in client2.hits), "completed calls were served from the cache"


def test_repeated_interruptions_never_duplicate_anything(settings, book, tmp_path, reference):
    ref_state, ref_client = reference
    path = tmp_path / "run" / "m.db"
    all_paid, rounds = [], 0
    while True:
        rounds += 1
        assert rounds < 60, "must converge"
        # fail the very first uncached call of a rotating stage, every round
        task = TASKS[rounds % 4]
        client, store, ended = run(settings, book, path, {(task, 1): "die_after" if rounds % 2 else "timeout"}, hard_kill_on=rounds % 3 == 0)
        all_paid += client.paid
        if ended == "done":
            break
    assert rounds > 4, "the run really was interrupted several times"
    store = Store(path)
    assert_clean(store, book)
    assert representation(store, book.id) == ref_state
    assert len(all_paid) == len(set(all_paid)) == len(ref_client.paid), "no call was ever paid twice"


def test_resuming_a_finished_run_is_a_no_op(settings, book, tmp_path, reference):
    ref_state, _ = reference
    path = tmp_path / "run" / "m.db"
    run(settings, book, path)
    for _ in range(3):
        client, store, ended = run(settings, book, path)
        assert ended == "done" and client.paid == [] and client.hits == []
        assert representation(store, book.id) == ref_state


def test_timeouts_stay_on_record_after_the_passage_is_retried(settings, book, tmp_path):
    path = tmp_path / "run" / "m.db"
    _, store, ended = run(settings, book, path, {("integration", 1): "timeout"})
    assert ended == "timeout"
    store.db.close()
    _, store2, ended2 = run(settings, book, path)
    assert ended2 == "done"
    bad = store2.uncertain_calls()
    assert len(bad) == 1 and bad[0]["task"] == "integration"
    assert store2.uncertain_exposure_usd() == pytest.approx(0.05)
    assert store2.total_spend_usd() > 0


# ---------- the store itself ----------

def test_model_calls_are_durable_while_a_passage_is_not(tmp_path):
    path = tmp_path / "m.db"
    store = Store(path)
    store.db.execute("INSERT INTO books (id, title) VALUES ('b', 't')")     # an uncommitted change to the representation
    store.cache_put("k", "m", "perception", {"q": 1}, {"a": 2})
    store.log_usage(ts=1.0, run_id="r", task="perception", key="p0", model="m", status="ok", cost_usd=0.25)
    store.db.close()                                                         # killed with the representation uncommitted
    again = Store(path)
    assert again.get_book("b") is None
    assert again.cache_get("k") == {"a": 2}
    assert again.total_spend_usd() == pytest.approx(0.25)
    assert (tmp_path / "m.calls.db").exists()


def test_read_only_use_does_not_create_a_calls_file(tmp_path):
    path = tmp_path / "m.db"
    Store(path).commit()
    reader = Store(path)
    assert reader.get_book("x") is None and reader.cache_get("k") is None and reader.usage_rows() == [] and reader.total_spend_usd() == 0.0
    assert not (tmp_path / "m.calls.db").exists()


def test_databases_from_before_the_split_stay_readable_and_their_spend_still_counts(tmp_path):
    path = tmp_path / "old.db"
    legacy = Store(path)
    legacy.db.execute("INSERT INTO llm_cache VALUES ('k','m','t','{}','{\"a\": 1}', 1.0)")
    legacy.db.execute("INSERT INTO usage_log (ts, run_id, task, key, status, cost_usd) VALUES (1.0,'old','t','k','ok',1.5)")
    legacy.commit()
    legacy.db.close()
    store = Store(path)
    assert store.cache_get("k") == {"a": 1}
    assert store.total_spend_usd() == pytest.approx(1.5)
    store.log_usage(ts=2.0, run_id="new", task="t", key="k2", model="m", status="ok", cost_usd=0.5)
    assert store.total_spend_usd() == pytest.approx(2.0)
    assert [r["run_id"] for r in store.usage_rows()] == ["old", "new"]


# ---------- the real client's accounting of uncertain calls ----------

def _client(settings, handler, store, **over):
    opts = dict(api_key="k", api_base="https://example.test/v1", model="muse-spark-1.3", reasoning_effort="medium",
                max_completion_tokens=12000, max_attempts=1, budget_usd=2.0) | over
    s = replace(settings, **opts)
    return MetaModelClient(s, store, http=httpx.Client(transport=httpx.MockTransport(handler)), run_id="r")


KW = dict(task="perception", key="p0", system="sys", user="usr", schema_name="S", schema={"type": "object"})


def test_a_timed_out_call_is_recorded_with_its_possible_cost_and_counts_against_the_budget(settings):
    def handler(request):
        raise httpx.ReadTimeout("timed out")
    store = Store(":memory:")
    client = _client(settings, handler, store)
    with pytest.raises(LLMError):
        client.complete(**KW)
    [row] = store.usage_rows()
    assert row["status"] == "network_error" and row["cost_usd"] == 0
    assert "billing_uncertain" in row["detail"]
    exposure = store.uncertain_exposure_usd()
    assert 0.05 < exposure < 0.2
    # enough uncertain exposure makes the budget guard refuse the next call, although nothing was confirmed as spent
    tight = _client(settings, handler, store, budget_usd=exposure + 0.01)
    with pytest.raises(BudgetExceeded):
        tight.complete(**KW)
    assert store.usage_rows()[-1]["status"] == "blocked_budget"
