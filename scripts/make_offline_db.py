"""Build ONE read-only-use SQLite file holding The Time Machine, Plato and The Gift of the Magi, from COPIES of the saved databases, so a single offline app
instance can switch between books in its own book selector (as a reader would). Nothing is generated: every row is copied.
  The Time Machine <- docs/experiments/time_machine/exports/motif.the_time_machine.db
  Plato, Magi      <- data/motif.m51.db
usage: make_offline_db.py <out.db>"""
import shutil, sqlite3, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]); out.parent.mkdir(parents=True, exist_ok=True)
if out.exists(): out.unlink()
shutil.copy(REPO / "docs/experiments/time_machine/exports/motif.the_time_machine.db", out)
db = sqlite3.connect(out)
db.execute("ATTACH DATABASE ? AS src", (str(REPO / "data/motif.m51.db"),))
BOOK = {"books": "id", "passages": "book_id", "units": "book_id", "evidence": "book_id", "activations": "book_id", "relations": "book_id",
        "revisions": "book_id", "constructions": "book_id", "journeys": "book_id"}
for book in ("plato_cave", "gift_of_the_magi"):
    for t, col in BOOK.items():
        have = [r[1] for r in db.execute(f"PRAGMA main.table_info({t})")]
        cols = ",".join(have)
        db.execute(f"INSERT INTO main.{t} ({cols}) SELECT {cols} FROM src.{t} WHERE {col}=?", (book,))
db.commit(); db.execute("DETACH DATABASE src")
for b in db.execute("SELECT id, (SELECT COUNT(*) FROM units u WHERE u.book_id=b.id), (SELECT COUNT(*) FROM relations r WHERE r.book_id=b.id) FROM books b ORDER BY id"):
    print(b)
db.execute("DELETE FROM llm_cache"); db.execute("DELETE FROM usage_log"); db.commit(); db.execute("VACUUM"); db.close()
