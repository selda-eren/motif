"""Checkpointed, resumable runs of the unchanged MORe pipeline over a long text.

Nothing in the cognitive pipeline (perceive, activate, integrate, propagate, construct, journey, explain)
is changed. This module adds durability around it:

* The response cache and the usage log live in a SEPARATE SQLite file (`Store` does this itself since the Milestone 7
  fix; the experiment was run before it with an equivalent harness-only subclass, using the same file layout). Representation
  changes are committed only when a whole passage finishes, while every model response and usage row is durable on arrival.
* `RecordingClient` wraps the real client: it appends one line per call to an in-flight ledger before and
  after the call, and writes a separate record for calls whose billing is uncertain (timeouts, network
  errors, 5xx).
* After each passage the driver writes two immutable files: the passage ledger (exact text, every request
  and response, usage, notes) and the full representation state as it was after that passage.

  python -m motif.experimental.long_run preflight|run|journey|explain|audit  (see --help)
"""
from __future__ import annotations

import argparse
import dataclasses
import gzip
import hashlib
import json
import os
import statistics
import sys
import time
from pathlib import Path

from ..config import REPO_ROOT, Settings, load_settings
from ..llm import BudgetExceeded, LLMError, MetaModelClient
from ..pipeline import process_book
from ..store import Store
from ..text import load_book, segment
from ..usage import worst_case_usd

STATE_TABLES = ("books", "passages", "units", "evidence", "activations", "relations", "revisions", "constructions")
PASSAGE_TASKS = ("perception", "integration", "propagation", "construction")


class ResumableStore(Store):
    """The core Store with an explicit calls database. Since the pipeline fix, `Store` itself keeps the response cache and
    usage log in a separate file and commits a passage atomically, so this is only a named constructor kept for the
    experiment scripts (and `side` is the calls connection)."""

    def __init__(self, path: Path | str, side_path: Path | str):
        super().__init__(path, calls_path=side_path)
        self.calls_db  # open (and create) it now so it exists from the start

    @property
    def side(self):
        return self.calls_db


# ---------------------------------------------------------------------------------------------
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_immutable(path: Path, obj) -> str:
    """Write canonical gzip-JSON once. If the file exists it must be identical; it is made read-only."""
    data = gzip.compress(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(), mtime=0)
    if path.exists():
        if sha256_bytes(path.read_bytes()) != sha256_bytes(data):
            raise RuntimeError(f"{path} already exists with different content; checkpoints are immutable")
        return sha256_bytes(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    path.chmod(0o444)
    return sha256_bytes(data)


def read_json_gz(path: Path):
    return json.loads(gzip.decompress(path.read_bytes()))


def dump_state(store: Store, book_id: str) -> dict:
    """Every representation table for the book, exactly as stored right now (passage texts omitted:
    they are in the passage ledger)."""
    out = {}
    for t in STATE_TABLES:
        col = "id" if t == "books" else "book_id"
        rows = [dict(r) for r in store.db.execute(f"SELECT * FROM {t} WHERE {col}=?", (book_id,))]
        if t == "passages":
            for r in rows:
                r.pop("text", None)
        out[t] = rows
    return out


class RecordingClient:
    """Delegates to a real client and records every call durably (in-flight ledger + uncertain-call log)."""
    provenance = "model"

    def __init__(self, inner: MetaModelClient, store: ResumableStore, run_dir: Path, crash_after: str | None = None):
        self.inner, self.store, self.run_dir = inner, store, Path(run_dir)
        self.model = inner.model
        self.crash_after = crash_after or os.environ.get("MOTIF_TM_CRASH_AFTER")  # e.g. "integration:p3"
        (self.run_dir / "logs").mkdir(parents=True, exist_ok=True)
        self.inflight = self.run_dir / "logs" / "calls_inflight.jsonl"
        self.uncertain = self.run_dir / "logs" / "uncertain_calls.jsonl"

    def _append(self, path: Path, rec: dict) -> None:
        with path.open("a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    def complete(self, *, task: str, key: str, system: str, user: str, schema_name: str, schema: dict) -> dict:
        body = self.inner._body(system, user, schema_name, schema)
        ck = sha256_bytes(json.dumps(body, sort_keys=True).encode())
        hit = self.store.cache_get(ck) is not None
        t0 = time.time()
        self._append(self.inflight, {"event": "start", "task": task, "key": key, "cache_key": ck, "cache_hit": hit,
                                     "t": t0, "run_id": self.inner.run_id})
        try:
            out = self.inner.complete(task=task, key=key, system=system, user=user, schema_name=schema_name, schema=schema)
        except BudgetExceeded as exc:
            self._append(self.inflight, {"event": "budget_stop", "task": task, "key": key, "cache_key": ck, "t": time.time(), "error": str(exc)})
            raise
        except LLMError as exc:
            msg = str(exc)
            if msg.startswith("Network error"):
                kind = "timeout_or_network_billing_uncertain"
            elif msg.startswith("HTTP 5"):
                kind = "server_error_billing_uncertain"
            elif msg.startswith("HTTP"):
                kind = "rejected_expected_not_billed"
            elif msg.startswith("Unparseable"):
                kind = "invalid_output_billed_and_logged"
            else:
                kind = "other"
            est = worst_case_usd(self.model, len(json.dumps(body)), self.inner.settings.max_completion_tokens)
            rec = {"t": time.time(), "task": task, "key": key, "cache_key": ck, "kind": kind, "error": msg[:500],
                   "run_id": self.inner.run_id, "request_chars": len(json.dumps(body)),
                   "worst_case_cost_usd": round(est, 4) if kind.endswith("billing_uncertain") else 0.0}
            self._append(self.uncertain, rec)
            self._append(self.inflight, {"event": "error", **rec})
            raise
        self._append(self.inflight, {"event": "done", "task": task, "key": key, "cache_key": ck, "cache_hit": hit,
                                     "t": time.time(), "run_id": self.inner.run_id})
        if self.crash_after == f"{task}:{key}" and not hit:
            print(f"[fault injection] exiting right after {task}/{key} completed", flush=True)
            os._exit(137)  # simulate a kill: no cleanup, no commit
        return out


def uncertain_exposure_usd(run_dir: Path) -> float:
    p = Path(run_dir) / "logs" / "uncertain_calls.jsonl"
    if not p.exists():
        return 0.0
    return sum(json.loads(l).get("worst_case_cost_usd", 0.0) for l in p.read_text().splitlines() if l.strip())


# ---------------------------------------------------------------------------------------------
@dataclasses.dataclass
class Experiment:
    book_id: str
    run_dir: Path
    state_db: Path
    side_db: Path
    settings: Settings

    @classmethod
    def create(cls, book_id: str, run_dir: Path, budget_usd: float) -> "Experiment":
        base = load_settings()
        state_db = REPO_ROOT / "data" / f"motif.{book_id}.db"
        side_db = REPO_ROOT / "data" / f"motif.{book_id}.calls.db"
        st = dataclasses.replace(base, db_path=state_db, budget_usd=budget_usd)
        return cls(book_id, Path(run_dir), state_db, side_db, st)

    def store(self) -> ResumableStore:
        return ResumableStore(self.state_db, self.side_db)

    def client(self, store: ResumableStore, run_id: str | None = None) -> RecordingClient:
        inner = MetaModelClient(self.settings, store, run_id=run_id, log=lambda m: print(m, flush=True))
        return RecordingClient(inner, store, self.run_dir)


def passage_ledger(exp: Experiment, store: ResumableStore, p: int, passage, chapters: list[dict]) -> dict:
    """Everything that happened for passage p, across every attempt: exact text, each request and response,
    usage rows and the processing notes the pipeline stored."""
    key = f"p{p}"
    lines = [json.loads(l) for l in (exp.run_dir / "logs" / "calls_inflight.jsonl").read_text().splitlines() if l.strip()]
    lines = [l for l in lines if l.get("key") == key and l.get("task") in PASSAGE_TASKS]
    calls, seen = [], set()
    for l in lines:
        if l["event"] != "done" or (l["task"], l["cache_key"], l["t"]) in seen:
            continue
        seen.add((l["task"], l["cache_key"], l["t"]))
        row = store.cache_row(l["cache_key"])
        calls.append({"task": l["task"], "cache_key": l["cache_key"], "served_from_cache": l["cache_hit"], "t": l["t"],
                      "run_id": l["run_id"], "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"]),
                      "model": row["model"], "cached_at": row["created_at"]})
    usage = [dict(r) for r in store.side.execute(
        "SELECT * FROM usage_log WHERE key=? AND task IN (?,?,?,?) ORDER BY ts", (key, *PASSAGE_TASKS))]
    notes = next(r for r in store.passages(exp.book_id) if r["idx"] == p)
    return {"passage": p, "text": passage.text, "start": passage.start, "end": passage.end, "words": len(passage.text.split()),
            "chapters": chapters, "gist": notes["gist"], "notes": notes["notes"], "calls": calls, "usage": usage,
            "errors_and_retries": [l for l in lines if l["event"] == "error"],
            "settings": {"model": exp.settings.model, "reasoning_effort": exp.settings.reasoning_effort,
                         "max_completion_tokens": exp.settings.max_completion_tokens, "propagate": exp.settings.propagate,
                         "construct": exp.settings.construct}}


def write_checkpoint(exp: Experiment, store: ResumableStore, p: int, passage, chapters: list[dict]) -> dict:
    led = passage_ledger(exp, store, p, passage, chapters)
    led_sha = write_immutable(exp.run_dir / "passages" / f"p{p + 1:03d}.json.gz", led)
    state = dump_state(store, exp.book_id)
    state_sha = write_immutable(exp.run_dir / "checkpoints" / f"state_after_p{p + 1:03d}.json.gz", state)
    usage = led["usage"]
    api = [u for u in usage if u["status"] == "ok"]
    rec = {"passage": p + 1, "ledger_sha256": led_sha, "state_sha256": state_sha,
           "units": len(state["units"]), "relations": len(state["relations"]), "revisions": len(state["revisions"]),
           "constructions": len(state["constructions"]),
           "api_calls": len(api), "cache_hits": sum(u["status"] == "cache_hit" for u in usage),
           "cost_usd": round(sum(u["cost_usd"] or 0 for u in usage), 6),
           "model_seconds": round(sum(u["latency_s"] or 0 for u in api), 1),
           "prompt_tokens": sum(u["prompt_tokens"] or 0 for u in usage), "completion_tokens": sum(u["completion_tokens"] or 0 for u in usage),
           "reasoning_tokens": sum(u["reasoning_tokens"] or 0 for u in usage)}
    return rec


def load_progress(exp: Experiment) -> dict[int, dict]:
    p = exp.run_dir / "progress.json"
    return {r["passage"]: r for r in json.loads(p.read_text())} if p.exists() else {}


def save_progress(exp: Experiment, prog: dict[int, dict]) -> None:
    tmp = exp.run_dir / "progress.json.tmp"
    tmp.write_text(json.dumps([prog[k] for k in sorted(prog)], indent=1))
    os.replace(tmp, exp.run_dir / "progress.json")


def run_passages(exp: Experiment, upto: int | None, *, max_retries: int = 3, backoff_s: float = 30.0,
                 chapters_by_passage: dict[int, list[dict]] | None = None) -> None:
    book = load_book(exp.settings.texts_dir, exp.book_id)
    passages = segment(book.text)
    n = len(passages) if upto is None else min(upto, len(passages))
    store = exp.store()
    client = exp.client(store)
    chapters_by_passage = chapters_by_passage or {}
    prog = load_progress(exp)
    print(f"{exp.book_id}: {len(passages)} passages; target {n}; run {client.inner.run_id}; budget ${exp.settings.budget_usd:.2f}; "
          f"spent ${store.total_spend_usd():.4f}; uncertain exposure ${uncertain_exposure_usd(exp.run_dir):.4f}", flush=True)
    for p in range(n):
        done = {r["idx"]: r for r in store.passages(exp.book_id)} if store.get_book(exp.book_id) else {}
        if p in done and done[p]["processed"]:
            if (p + 1) not in prog:  # processed and committed, but the checkpoint was not written (killed in between)
                later = [i for i, r in done.items() if r["processed"] and i > p]
                if later:
                    raise RuntimeError(f"passage {p + 1} has no checkpoint but later passages are processed")
                prog[p + 1] = write_checkpoint(exp, store, p, passages[p], chapters_by_passage.get(p, []))
                save_progress(exp, prog)
                print(f"  recovered missing checkpoint for passage {p + 1}", flush=True)
            continue
        attempt = 0
        while True:
            exposure = uncertain_exposure_usd(exp.run_dir)
            if store.total_spend_usd() + exposure >= exp.settings.budget_usd:
                raise BudgetExceeded(f"local limit ${exp.settings.budget_usd:.2f} reached "
                                     f"(spent ${store.total_spend_usd():.2f} + uncertain exposure ${exposure:.2f})")
            attempt += 1
            t0 = time.time()
            try:
                process_book(book, client, store, limit=p + 1, propagate=exp.settings.propagate,
                             construct=exp.settings.construct, log=lambda m: print("  " + m, flush=True))
                break
            except BudgetExceeded:
                raise
            except LLMError as exc:
                store.db.rollback()  # nothing of the half-done passage was committed; make that explicit
                print(f"  passage {p + 1} attempt {attempt} failed: {str(exc)[:200]}", flush=True)
                if attempt > max_retries:
                    raise RuntimeError(f"passage {p + 1} failed {attempt} times; stopping. Completed calls are cached; "
                                       f"re-run the same command to resume.") from exc
                time.sleep(backoff_s * attempt)
        rec = write_checkpoint(exp, store, p, passages[p], chapters_by_passage.get(p, []))
        rec["wall_seconds"] = round(time.time() - t0, 1)
        rec["attempts"] = attempt
        prog[p + 1] = rec
        save_progress(exp, prog)
        print(f"passage {p + 1}/{len(passages)} checkpointed: {rec['units']} units, {rec['relations']} relations, "
              f"{rec['constructions']} constructed; passage cost ${rec['cost_usd']:.4f}; total ${store.total_spend_usd():.4f}", flush=True)


def audit(exp: Experiment) -> dict:
    """Resumability and duplicate-work audit."""
    store = exp.store()
    rows = store.usage_rows()
    ok = [r for r in rows if r["status"] == "ok"]
    from collections import Counter
    dup = {f"{t}/{k}": c for (t, k), c in Counter((r["task"], r["key"]) for r in ok).items() if c > 1}
    cache_keys = [json.loads(l) for l in (exp.run_dir / "logs" / "calls_inflight.jsonl").read_text().splitlines() if l.strip()] \
        if (exp.run_dir / "logs" / "calls_inflight.jsonl").exists() else []
    paid_by_key = Counter(l["cache_key"] for l in cache_keys if l["event"] == "done" and not l["cache_hit"])
    paid_twice = {k[:12]: c for k, c in paid_by_key.items() if c > 1}
    passages = store.passages(exp.book_id) if store.get_book(exp.book_id) else []
    prog = load_progress(exp)
    return {"ok_calls": len(ok), "duplicate_paid_task_keys": dup, "cache_keys_paid_more_than_once": paid_twice,
            "passages_processed": sum(p["processed"] for p in passages), "passages_checkpointed": len(prog),
            "checkpoint_missing_for_processed": [p["idx"] + 1 for p in passages if p["processed"] and (p["idx"] + 1) not in prog],
            "non_ok_calls": dict(Counter(r["status"] for r in rows if r["status"] not in ("ok", "cache_hit"))),
            "cache_hits": sum(r["status"] == "cache_hit" for r in rows), "spend_usd": round(store.total_spend_usd(), 4),
            "uncertain_exposure_usd": round(uncertain_exposure_usd(exp.run_dir), 4)}


def synthesize_stage(exp: Experiment, which: str) -> None:
    store = exp.store()
    client = exp.client(store)
    from .. import explain as explain_mod
    from .. import journey as journey_mod
    exposure = uncertain_exposure_usd(exp.run_dir)
    if store.total_spend_usd() + exposure >= exp.settings.budget_usd:
        raise BudgetExceeded("local limit reached")
    fn = journey_mod.synthesize if which == "journey" else explain_mod.explain
    result = fn(client, store, exp.book_id)
    lines = [json.loads(l) for l in (exp.run_dir / "logs" / "calls_inflight.jsonl").read_text().splitlines() if l.strip()]
    done = [l for l in lines if l["event"] == "done" and l["task"] == which and l["key"] == exp.book_id]
    calls = []
    for l in done:
        row = store.cache_row(l["cache_key"])
        calls.append({"task": which, "cache_key": l["cache_key"], "served_from_cache": l["cache_hit"], "t": l["t"],
                      "request": json.loads(row["request_json"]), "response": json.loads(row["response_json"])})
    usage = [dict(r) for r in store.side.execute("SELECT * FROM usage_log WHERE task=? AND key=? ORDER BY ts", (which, exp.book_id))]
    write_immutable(exp.run_dir / "passages" / f"{which}.json.gz", {"calls": calls, "usage": usage, "result": result})
    print(f"{which} saved ({len(calls)} call records)", flush=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="long_run")
    ap.add_argument("cmd", choices=["run", "journey", "explain", "audit"])
    ap.add_argument("--book", default="the_time_machine")
    ap.add_argument("--out", required=True, help="experiment directory (checkpoints, ledgers, logs)")
    ap.add_argument("--upto", type=int, help="process passages 1..N only")
    ap.add_argument("--budget", type=float, default=50.0)
    ap.add_argument("--retries", type=int, default=3)
    a = ap.parse_args(argv)
    exp = Experiment.create(a.book, Path(a.out), a.budget)
    if a.cmd == "run":
        chapters = {}
        pj = exp.run_dir / "source" / "passages.json"
        if pj.exists():
            chapters = {r["index"]: r["chapters"] for r in json.loads(pj.read_text())}
        run_passages(exp, a.upto, max_retries=a.retries, chapters_by_passage=chapters)
    elif a.cmd in ("journey", "explain"):
        synthesize_stage(exp, a.cmd)
    else:
        print(json.dumps(audit(exp), indent=1))


if __name__ == "__main__":
    main()
