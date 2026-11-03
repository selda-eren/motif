"""Rebuild Plato and The Gift of the Magi from the cached model responses stored in data/motif.m51.db, with the API unreachable and
the CURRENT code, and compare every representation table with what that database holds. Works on temp copies; nothing is modified."""
import dataclasses, json, shutil, sys, tempfile
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "backend"))
from motif.config import load_settings
from motif.llm import MetaModelClient
from motif.pipeline import process_book
from motif.store import Store
from motif.text import load_book

settings = load_settings()
src = REPO / "data" / "motif.m51.db"
ok_all = True
for book_id in ("plato_cave", "gift_of_the_magi"):
    tmp = Path(tempfile.mkdtemp()); shutil.copy(src, tmp / "m.db")
    store = Store(tmp / "m.db")                      # legacy layout: the cache is inside the main file
    ref = {t: sorted(json.dumps(dict(r), sort_keys=True) for r in store.db.execute(f"SELECT * FROM {t} WHERE book_id=?", (book_id,)))
           for t in ("units", "evidence", "activations", "relations", "revisions", "constructions")}
    ref_p = sorted(json.dumps({k: v for k, v in dict(r).items() if k != "text"}, sort_keys=True) for r in store.db.execute("SELECT * FROM passages WHERE book_id=?", (book_id,)))
    st = dataclasses.replace(settings, api_key="not-a-key", api_base="http://127.0.0.1:9", timeout_s=2.0, db_path=tmp / "m.db")
    client = MetaModelClient(st, store, run_id="rebuild-check", log=lambda m: print("UNEXPECTED API CALL:", m))
    book = load_book(st.texts_dir, book_id)
    process_book(book, client, store, reset=True, propagate=True, construct=True, log=lambda m: None)
    got = {t: sorted(json.dumps(dict(r), sort_keys=True) for r in store.db.execute(f"SELECT * FROM {t} WHERE book_id=?", (book_id,))) for t in ref}
    got_p = sorted(json.dumps({k: v for k, v in dict(r).items() if k != "text"}, sort_keys=True) for r in store.db.execute("SELECT * FROM passages WHERE book_id=?", (book_id,)))
    same = got == ref and got_p == ref_p
    rows = [r for r in store.usage_rows("rebuild-check")]
    print(json.dumps({"book": book_id, "identical_representation": same, "units": len(store.units(book_id)), "relations": len(store.relations(book_id)),
                      "revisions": len(store.revisions(book_id)), "constructions": len(store.constructions(book_id)),
                      "api_requests_attempted": sum(r["status"] != "cache_hit" for r in rows), "cache_hits": len(rows)}))
    ok_all &= same and all(r["status"] == "cache_hit" for r in rows)
print("ALL IDENTICAL, ZERO API REQUESTS" if ok_all else "MISMATCH")
sys.exit(0 if ok_all else 1)
