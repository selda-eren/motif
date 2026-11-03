"""Rebuild the representation from the cached model responses ONLY, with the API unreachable, and compare it to
the stored checkpoint after the same passage. Any call that is not in the cache would fail loudly (dead endpoint).
usage: offline_rebuild_check.py [N]   (default: every checkpointed passage). Uses temp copies; nothing is modified."""
import dataclasses, json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]; ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from motif.config import load_settings
from motif.experimental.long_run import ResumableStore, dump_state, read_json_gz, load_progress, Experiment
from motif.llm import MetaModelClient
from motif.pipeline import process_book
from motif.text import load_book

exp = Experiment.create("the_time_machine", ROOT, 50.0)
prog = load_progress(exp)
n = int(sys.argv[1]) if len(sys.argv) > 1 else max(prog)
tmp = Path(tempfile.mkdtemp())
# A fresh clone has no data/ calls file; the exported database holds the identical response cache (same 311 keys and responses).
shutil.copy(exp.side_db if exp.side_db.exists() else ROOT / "exports" / "motif.the_time_machine.db", tmp / "calls.db")
st = dataclasses.replace(exp.settings, api_key="offline-check-not-a-key", api_base="http://127.0.0.1:9", timeout_s=2.0)
store = ResumableStore(tmp / "state.db", tmp / "calls.db")
client = MetaModelClient(st, store, run_id="offline-rebuild", log=lambda m: print("UNEXPECTED API CALL:", m))
book = load_book(st.texts_dir, "the_time_machine")
bad = 0
for p in range(n):
    process_book(book, client, store, limit=p + 1, propagate=st.propagate, construct=st.construct, log=lambda m: None)
    got = dump_state(store, "the_time_machine")
    want = read_json_gz(ROOT / "checkpoints" / f"state_after_p{p + 1:03d}.json.gz")
    same = all(sorted(map(lambda r: json.dumps(r, sort_keys=True), got[t])) == sorted(map(lambda r: json.dumps(r, sort_keys=True), want[t]))
               for t in want if t != "books")
    bad += not same
    if not same: print(f"  MISMATCH after passage {p + 1}")
calls = store.usage_rows("offline-rebuild")
print(json.dumps({"passages_rebuilt": n, "identical_to_stored_checkpoints": n - bad, "mismatches": bad,
                  "api_requests_attempted": sum(r["status"] not in ("cache_hit",) for r in calls),
                  "cache_hits": sum(r["status"] == "cache_hit" for r in calls), "spend_usd": store.total_spend_usd()}, indent=1))
sys.exit(1 if bad or any(r["status"] != "cache_hit" for r in calls) else 0)
