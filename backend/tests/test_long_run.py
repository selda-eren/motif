"""The experiment harness (motif.experimental.long_run) on top of the core store. The core guarantees are tested in
test_resume_atomic.py; these check the harness-level pieces (immutable checkpoints, the named constructor, offline replay)."""
import json
import sqlite3

import pytest

from motif.experimental.long_run import ResumableStore, dump_state, write_immutable
from motif.llm import FixtureClient, LLMError
from motif.pipeline import process_book
from motif.store import Store
from motif.text import load_book


class FlakyClient:
    """Replays the demo fixture through the same cache/usage side effects as the real client, and fails on
    the Nth *uncached* call (like a timeout)."""
    provenance = "demo-fixture"
    model = None

    def __init__(self, settings, store, fail_on_call=None, timeout_once_task=None):
        self.timeout_once_task = timeout_once_task
        self.inner = FixtureClient(settings.demo_dir / "plato_cave.fixture.json")
        self.store, self.fail_on_call = store, fail_on_call
        self.paid = []   # (task, key) of calls that were not served from cache
        self.hits = []

    def complete(self, *, task, key, system, user, schema_name, schema):
        ck = f"{task}/{key}"
        if (hit := self.store.cache_get(ck)) is not None:
            self.hits.append(ck)
            return hit
        if task == self.timeout_once_task:
            self.timeout_once_task = None
            # like MetaModelClient: the failure itself is logged (and logging commits on the stock Store)
            self.store.log_usage(ts=0.0, run_id="t", task=task, key=key, model=None, reasoning_effort="x",
                                 status="network_error", prompt_tokens=0, cached_tokens=0, completion_tokens=0,
                                 reasoning_tokens=0, cost_usd=0.0, latency_s=0.0, finish_reason=None, detail="timed out")
            raise LLMError("Network error calling test: timed out")
        if task == "propagation":      # the offline fixture has no propagation data: an empty reconsideration
            out = {"reconsiderations": []}
            self.paid.append(ck)
            self.store.cache_put(ck, "m", task, {"k": ck}, out)
            return out
        if self.fail_on_call is not None and len(self.paid) + 1 == self.fail_on_call:
            self.fail_on_call = None
            raise LLMError("Network error calling test: timed out")
        out = self.inner.complete(task=task, key=key, system=system, user=user, schema_name=schema_name, schema=schema)
        self.paid.append(ck)
        self.store.log_usage(ts=0.0, run_id="t", task=task, key=key, model=None, reasoning_effort="x", status="ok",
                             prompt_tokens=1, cached_tokens=0, completion_tokens=1, reasoning_tokens=0, cost_usd=0.001,
                             latency_s=0.0, finish_reason="stop", detail=None)
        self.store.cache_put(ck, "m", task, {"k": ck}, out)
        return out


def reopen(tmp_path):
    return ResumableStore(tmp_path / "state.db", tmp_path / "side.db")


def counts(store, book_id):
    return {t: len(rows) for t, rows in dump_state(store, book_id).items()}


def test_resumable_store_survives_a_propagation_timeout(settings, tmp_path):
    book = load_book(settings.texts_dir, "plato_cave")
    store = reopen(tmp_path)
    client = FlakyClient(settings, store, timeout_once_task="propagation")
    with pytest.raises(LLMError):
        process_book(book, client, store, propagate=True)
    store.db.close(); store.side.close()
    store = reopen(tmp_path)
    processed = {p["idx"] for p in store.passages(book.id) if p["processed"]}
    assert all(u.introduced_at in processed for u in store.units(book.id)), "nothing from the unfinished passage"
    client2 = FlakyClient(settings, store)
    process_book(book, client2, store, propagate=True)           # resume completes
    assert all(p["processed"] for p in store.passages(book.id))
    assert any(h.startswith("perception/") or h.startswith("integration/") for h in client2.hits), "completed calls reused"
    assert [r for r in store.usage_rows() if r["status"] == "network_error"], "the failed call stays on record"


def test_resumable_store_never_persists_a_partial_passage(settings, tmp_path):
    book = load_book(settings.texts_dir, "plato_cave")
    store = reopen(tmp_path)
    client = FlakyClient(settings, store)
    client.fail_on_call = 4          # integration of passage 2 fails after perception p1 (cached) and passage 1 integrated
    with pytest.raises(LLMError):
        process_book(book, client, store)
    # Simulate the process dying: drop the connection without committing anything further.
    store.db.close(); store.side.close()
    store = reopen(tmp_path)
    assert [p["idx"] for p in store.passages(book.id) if p["processed"]] == [0]
    state = dump_state(store, book.id)
    assert all(u["introduced_at"] == 0 for u in state["units"]), "no units from the unfinished passage"
    assert all(r["created_at"] == 0 for r in state["relations"])
    assert store.cache_get("perception/p1") is not None, "the completed perception call survived"
    assert store.total_spend_usd() == pytest.approx(0.003)   # three completed calls were logged immediately


def test_resume_matches_an_uninterrupted_run_and_repays_nothing(settings, tmp_path):
    book = load_book(settings.texts_dir, "plato_cave")
    # reference: one uninterrupted run
    ref_dir = tmp_path / "ref"; ref_dir.mkdir()
    ref = ResumableStore(ref_dir / "state.db", ref_dir / "side.db")
    ref_client = FlakyClient(settings, ref)
    process_book(book, ref_client, ref)
    reference = dump_state(ref, book.id)
    total_calls = len(ref_client.paid)

    # interrupted run, killed twice at different places, then resumed
    run_dir = tmp_path / "run"; run_dir.mkdir()
    paid_total, hits_total = [], []
    for fail_on in (4, 3, None):
        store = ResumableStore(run_dir / "state.db", run_dir / "side.db")
        client = FlakyClient(settings, store, fail_on_call=fail_on)
        try:
            process_book(book, client, store)
        except LLMError:
            pass
        paid_total += client.paid; hits_total += client.hits
        store.db.close(); store.side.close()
    final = ResumableStore(run_dir / "state.db", run_dir / "side.db")
    got = dump_state(final, book.id)

    def stable(state):   # ignore nothing: the whole representation must be identical
        return {t: sorted(json.dumps(r, sort_keys=True) for r in rows) for t, rows in state.items() if t != "books"}
    assert stable(got) == stable(reference)
    assert len(paid_total) == total_calls and len(set(paid_total)) == total_calls, "every call paid exactly once"
    assert all(p["processed"] for p in final.passages(book.id))
    assert any(h in paid_total for h in hits_total), "resumed runs reused completed calls from the cache"
    oks = [r for r in final.usage_rows() if r["status"] == "ok"]
    assert len(oks) == total_calls


def test_immutable_files_cannot_be_rewritten(tmp_path):
    p = tmp_path / "x.json.gz"
    sha = write_immutable(p, {"a": 1})
    assert write_immutable(p, {"a": 1}) == sha         # identical content is accepted
    with pytest.raises(RuntimeError):
        write_immutable(p, {"a": 2})
    assert not (p.stat().st_mode & 0o222)
