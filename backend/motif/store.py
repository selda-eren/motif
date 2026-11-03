"""SQLite persistence for books, passages, the MORe representation, and the LLM cache."""
from __future__ import annotations

import json
import re
import sqlite3
import time
from pathlib import Path

from .schema import Construction, Evidence, Relation, Revision, Unit

SCHEMA = """
CREATE TABLE IF NOT EXISTS books (
    id TEXT PRIMARY KEY, title TEXT, author TEXT, genre TEXT, meta_json TEXT,
    provenance TEXT, model TEXT, updated_at REAL
);
CREATE TABLE IF NOT EXISTS passages (
    book_id TEXT, idx INTEGER, text TEXT, start INTEGER, end_ INTEGER,
    gist TEXT, processed INTEGER DEFAULT 0, notes_json TEXT,
    PRIMARY KEY (book_id, idx)
);
CREATE TABLE IF NOT EXISTS units (
    id TEXT, book_id TEXT, kind TEXT, label TEXT, content TEXT, participants_json TEXT,
    layer TEXT, confidence REAL, status TEXT, reading TEXT,
    introduced_at INTEGER, last_active_at INTEGER,
    PRIMARY KEY (book_id, id)
);
CREATE TABLE IF NOT EXISTS evidence (
    book_id TEXT, unit_id TEXT, passage INTEGER, quote TEXT, start INTEGER, end_ INTEGER
);
CREATE TABLE IF NOT EXISTS activations (
    book_id TEXT, unit_id TEXT, passage INTEGER, kind TEXT
);
CREATE TABLE IF NOT EXISTS relations (
    id TEXT, book_id TEXT, source TEXT, target TEXT, type TEXT, rationale TEXT,
    confidence REAL, created_at INTEGER, layer TEXT,
    PRIMARY KEY (book_id, id)
);
CREATE TABLE IF NOT EXISTS revisions (
    book_id TEXT, unit_id TEXT, passage INTEGER, old_reading TEXT, new_reading TEXT,
    rationale TEXT, cause_unit TEXT
);
CREATE TABLE IF NOT EXISTS usage_log (
    ts REAL, run_id TEXT, task TEXT, key TEXT, model TEXT, reasoning_effort TEXT, status TEXT,
    prompt_tokens INTEGER, cached_tokens INTEGER, completion_tokens INTEGER, reasoning_tokens INTEGER,
    cost_usd REAL, latency_s REAL, finish_reason TEXT, detail TEXT
);
CREATE TABLE IF NOT EXISTS journeys (
    book_id TEXT PRIMARY KEY, journey_json TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS constructions (
    book_id TEXT, id TEXT, passage INTEGER, data_json TEXT,
    PRIMARY KEY (book_id, id)
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY, model TEXT, task TEXT, request_json TEXT, response_json TEXT,
    created_at REAL
);
"""

_BOOK_TABLES = ("passages", "units", "evidence", "activations", "relations", "revisions", "constructions")

# Columns added after the first live runs; added in place so older databases keep working.
_ADDED_COLUMNS = {
    "units": {"state": "TEXT", "other_readings_json": "TEXT DEFAULT '[]'"},
    "revisions": {"kind": "TEXT DEFAULT 'interpretive'", "mode": "TEXT DEFAULT 'replaces'",
                  "source": "TEXT DEFAULT 'integration'", "trigger_unit": "TEXT",
                  "evidence_units_json": "TEXT DEFAULT '[]'"},
}


# The response cache and the usage log live in a SEPARATE database file (`<name>.calls.db` next to the main one), opened
# on first use. Both are durable the moment a model call finishes, while the representation of the passage being processed
# stays in one open transaction until the whole passage is saved (see pipeline.process_book). In one file those two
# commits would be the same commit, and a failure after the first model call of a passage would persist a half-built passage.
CALLS_SCHEMA = """
CREATE TABLE IF NOT EXISTS llm_cache (
    key TEXT PRIMARY KEY, model TEXT, task TEXT, request_json TEXT, response_json TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS usage_log (
    ts REAL, run_id TEXT, task TEXT, key TEXT, model TEXT, reasoning_effort TEXT, status TEXT,
    prompt_tokens INTEGER, cached_tokens INTEGER, completion_tokens INTEGER, reasoning_tokens INTEGER,
    cost_usd REAL, latency_s REAL, finish_reason TEXT, detail TEXT
);
"""
_USAGE_COLS = ["ts", "run_id", "task", "key", "model", "reasoning_effort", "status", "prompt_tokens",
               "cached_tokens", "completion_tokens", "reasoning_tokens", "cost_usd", "latency_s",
               "finish_reason", "detail"]


class Store:
    def __init__(self, path: Path | str, calls_path: Path | str | None = None):
        """`calls_path`: where the response cache and usage log are kept (default: `<path>.calls.db`; `:memory:` for an
        in-memory store). Databases created before this split hold those tables in the main file; they stay readable
        (cached responses are found and their spend still counts), and new calls are recorded in the calls file."""
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._calls_path = str(calls_path) if calls_path is not None else (
            ":memory:" if str(path) == ":memory:" else str(Path(path).with_suffix(".calls.db")))
        self._calls: sqlite3.Connection | None = None
        for table, cols in _ADDED_COLUMNS.items():
            have = {r["name"] for r in self.db.execute(f"PRAGMA table_info({table})")}
            for col, decl in cols.items():
                if col not in have:
                    self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        self.db.commit()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        """Discard everything written to the representation since the last commit (an unfinished passage)."""
        self.db.rollback()

    # ----- the calls database (response cache + usage log), committed independently of the representation -----
    def _calls_db(self, create: bool = False) -> sqlite3.Connection | None:
        if self._calls is None:
            if self._calls_path != ":memory:" and not create and not Path(self._calls_path).exists():
                return None   # read-only users (the API) never create the file
            if self._calls_path != ":memory:":
                Path(self._calls_path).parent.mkdir(parents=True, exist_ok=True)
            self._calls = sqlite3.connect(self._calls_path, check_same_thread=False)
            self._calls.row_factory = sqlite3.Row
            self._calls.executescript(CALLS_SCHEMA)
            self._calls.commit()
        return self._calls

    @property
    def calls_db(self) -> sqlite3.Connection:
        return self._calls_db(create=True)  # type: ignore[return-value]

    # ----- books & passages -----
    def upsert_book(self, book, provenance: str, model: str | None) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO books VALUES (?,?,?,?,?,?,?,?)",
            (book.id, book.title, book.author, book.genre, json.dumps(book.meta), provenance, model, time.time()),
        )

    def reset_book(self, book_id: str) -> None:
        for table in _BOOK_TABLES:
            self.db.execute(f"DELETE FROM {table} WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM journeys WHERE book_id=?", (book_id,))
        self.db.execute("DELETE FROM books WHERE id=?", (book_id,))
        self.commit()

    def get_book(self, book_id: str) -> dict | None:
        row = self.db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["meta"] = json.loads(d.pop("meta_json"))
        return d

    def list_books(self) -> list[dict]:
        ids = [r["id"] for r in self.db.execute("SELECT id FROM books ORDER BY id")]
        return [self.get_book(i) for i in ids]

    def ensure_passages(self, book_id: str, passages) -> None:
        existing = {r["idx"]: r["text"] for r in self.db.execute(
            "SELECT idx, text FROM passages WHERE book_id=?", (book_id,))}
        if existing and existing != {p.index: p.text for p in passages}:
            raise ValueError(f"Stored passages for {book_id!r} differ from the current segmentation; use --reset.")
        for p in passages:
            self.db.execute(
                "INSERT OR IGNORE INTO passages (book_id, idx, text, start, end_) VALUES (?,?,?,?,?)",
                (book_id, p.index, p.text, p.start, p.end),
            )
        self.commit()

    def mark_processed(self, book_id: str, idx: int, gist: str, notes: dict) -> None:
        self.db.execute(
            "UPDATE passages SET processed=1, gist=?, notes_json=? WHERE book_id=? AND idx=?",
            (gist, json.dumps(notes), book_id, idx),
        )

    def passages(self, book_id: str) -> list[dict]:
        rows = self.db.execute("SELECT * FROM passages WHERE book_id=? ORDER BY idx", (book_id,))
        out = []
        for r in rows:
            d = dict(r)
            d["end"] = d.pop("end_")
            d["notes"] = json.loads(d.pop("notes_json") or "{}")
            out.append(d)
        return out

    # ----- units -----
    def add_unit(self, book_id: str, u: Unit) -> None:
        self.db.execute(
            "INSERT INTO units (id, book_id, kind, label, content, participants_json, layer, confidence, status, "
            "reading, introduced_at, last_active_at, state, other_readings_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (u.id, book_id, u.kind, u.label, u.content, json.dumps(u.participants), u.layer,
             u.confidence, u.status, u.reading, u.introduced_at, u.last_active_at, u.state,
             json.dumps(u.other_readings)),
        )
        for ev in u.evidence:
            self.add_evidence(book_id, u.id, ev)
        self.add_activation(book_id, u.id, u.introduced_at, "introduced")

    def update_unit(self, book_id: str, u: Unit) -> None:
        self.db.execute(
            "UPDATE units SET confidence=?, status=?, reading=?, last_active_at=?, state=?, other_readings_json=? "
            "WHERE book_id=? AND id=?",
            (u.confidence, u.status, u.reading, u.last_active_at, u.state, json.dumps(u.other_readings),
             book_id, u.id),
        )

    def add_evidence(self, book_id: str, unit_id: str, ev: Evidence) -> None:
        self.db.execute("INSERT INTO evidence VALUES (?,?,?,?,?,?)",
                        (book_id, unit_id, ev.passage, ev.quote, ev.start, ev.end))

    def add_activation(self, book_id: str, unit_id: str, passage: int, kind: str) -> None:
        self.db.execute("INSERT INTO activations VALUES (?,?,?,?)", (book_id, unit_id, passage, kind))

    def units(self, book_id: str) -> list[Unit]:
        ev: dict[str, list[Evidence]] = {}
        for r in self.db.execute("SELECT * FROM evidence WHERE book_id=? ORDER BY passage, start", (book_id,)):
            ev.setdefault(r["unit_id"], []).append(
                Evidence(passage=r["passage"], quote=r["quote"], start=r["start"], end=r["end_"]))
        out = []
        for r in self.db.execute("SELECT * FROM units WHERE book_id=? ORDER BY introduced_at, id", (book_id,)):
            d = dict(r)
            d.pop("book_id")
            d["participants"] = json.loads(d.pop("participants_json"))
            d["other_readings"] = json.loads(d.pop("other_readings_json") or "[]")
            d["evidence"] = ev.get(d["id"], [])
            out.append(Unit(**d))
        return out

    def activations(self, book_id: str) -> list[dict]:
        return [dict(r) for r in self.db.execute(
            "SELECT unit_id, passage, kind FROM activations WHERE book_id=? ORDER BY passage", (book_id,))]

    # ----- relations & revisions -----
    def add_relation(self, book_id: str, r: Relation) -> None:
        self.db.execute("INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?)",
                        (r.id, book_id, r.source, r.target, r.type, r.rationale, r.confidence, r.created_at, r.layer))

    def relations(self, book_id: str) -> list[Relation]:
        rows = self.db.execute("SELECT * FROM relations WHERE book_id=? ORDER BY created_at, id", (book_id,))
        return [Relation(**{k: r[k] for k in r.keys() if k != "book_id"}) for r in rows]

    def add_revision(self, book_id: str, rev: Revision) -> None:
        self.db.execute(
            "INSERT INTO revisions (book_id, unit_id, passage, old_reading, new_reading, rationale, cause_unit, "
            "kind, mode, source, trigger_unit, evidence_units_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (book_id, rev.unit_id, rev.passage, rev.old_reading, rev.new_reading, rev.rationale, rev.cause_unit,
             rev.kind, rev.mode, rev.source, rev.trigger_unit, json.dumps(rev.evidence_units)))

    def revisions(self, book_id: str) -> list[Revision]:
        rows = self.db.execute("SELECT * FROM revisions WHERE book_id=? ORDER BY passage, rowid", (book_id,))
        out = []
        for r in rows:
            d = {k: r[k] for k in r.keys() if k not in ("book_id", "evidence_units_json")}
            d["evidence_units"] = json.loads(r["evidence_units_json"] or "[]")
            out.append(Revision(**d))
        return out

    # ----- constructed meanings -----
    def add_construction(self, book_id: str, c: Construction) -> None:
        self.db.execute("INSERT INTO constructions VALUES (?,?,?,?)",
                        (book_id, c.id, c.passage, c.model_dump_json()))

    def update_construction(self, book_id: str, c: Construction) -> None:
        self.db.execute("UPDATE constructions SET data_json=? WHERE book_id=? AND id=?",
                        (c.model_dump_json(), book_id, c.id))

    def constructions(self, book_id: str) -> list[Construction]:
        rows = self.db.execute("SELECT data_json FROM constructions WHERE book_id=? ORDER BY passage, rowid",
                               (book_id,))
        return [Construction.model_validate_json(r["data_json"]) for r in rows]

    # ----- journey -----
    def save_journey(self, book_id: str, journey: dict) -> None:
        self.db.execute("INSERT OR REPLACE INTO journeys VALUES (?,?,?)",
                        (book_id, json.dumps(journey), time.time()))
        self.commit()

    def get_journey(self, book_id: str) -> dict | None:
        row = self.db.execute("SELECT journey_json FROM journeys WHERE book_id=?", (book_id,)).fetchone()
        return json.loads(row["journey_json"]) if row else None

    # ----- usage -----
    def log_usage(self, **row) -> None:
        c = self.calls_db
        c.execute(f"INSERT INTO usage_log ({','.join(_USAGE_COLS)}) VALUES ({','.join('?' * len(_USAGE_COLS))})",
                  [row.get(k) for k in _USAGE_COLS])
        c.commit()

    def usage_rows(self, run_id: str | None = None) -> list[dict]:
        """Every logged call attempt, oldest first (rows from before the calls file existed included)."""
        out: list[dict] = []
        for conn in (self.db, self._calls_db()):
            if conn is None:
                continue
            q, args = "SELECT * FROM usage_log", ()
            if run_id:
                q, args = q + " WHERE run_id=?", (run_id,)
            out += [dict(r) for r in conn.execute(q, args)]
        return sorted(out, key=lambda r: r["ts"] or 0)

    def total_spend_usd(self) -> float:
        total = float(self.db.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log").fetchone()[0])
        calls = self._calls_db()
        if calls is not None:
            total += float(calls.execute("SELECT COALESCE(SUM(cost_usd), 0) FROM usage_log").fetchone()[0])
        return total

    def uncertain_calls(self) -> list[dict]:
        """Calls that may have been billed although no response arrived (timeouts, network errors, 5xx). They are logged
        with cost 0 (nothing is known), and `uncertain_exposure_usd` is what they could have cost at most."""
        return [r for r in self.usage_rows() if r["status"] == "network_error" or str(r["status"]).startswith("http_5")]

    def uncertain_exposure_usd(self) -> float:
        total = 0.0
        for r in self.uncertain_calls():
            m = re.search(r"worst_case_usd=([0-9.]+)", r.get("detail") or "")
            total += float(m.group(1)) if m else 0.0
        return total

    # ----- LLM cache -----
    def cache_get(self, key: str) -> dict | None:
        row = self.cache_row(key)
        return json.loads(row["response_json"]) if row else None

    def cache_row(self, key: str) -> dict | None:
        for conn in (self._calls_db(), self.db):   # the calls file first, then caches from before the split
            if conn is None:
                continue
            row = conn.execute("SELECT * FROM llm_cache WHERE key=?", (key,)).fetchone()
            if row:
                return dict(row)
        return None

    def cache_put(self, key: str, model: str, task: str, request: dict, response: dict) -> None:
        c = self.calls_db
        c.execute("INSERT OR REPLACE INTO llm_cache VALUES (?,?,?,?,?,?)",
                  (key, model, task, json.dumps(request), json.dumps(response), time.time()))
        c.commit()
