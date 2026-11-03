"""Read-only HTTP API over the stored representation.

Processing happens through the CLI, so browsing the UI can never spend API credits.
Set MOTIF_DEMO=1 to serve the offline demo database instead of model output; every
response carries the book's provenance so the UI can label it.
"""
from __future__ import annotations

import json
import os
from collections.abc import Iterator

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import graph
from .config import load_settings
from .store import Store

settings = load_settings()
DEMO = os.environ.get("MOTIF_DEMO") == "1"
DB_PATH = settings.demo_db_path if DEMO else settings.db_path


def get_store() -> Iterator[Store]:
    """One SQLite connection per request: FastAPI runs sync endpoints on a thread pool, and
    sqlite3 connections must not be shared across concurrent threads."""
    store = Store(DB_PATH)
    try:
        yield store
    finally:
        store.db.close()

app = FastAPI(title="MOTIF API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["GET", "POST"], allow_headers=["*"])


def _book_or_404(store: Store, book_id: str) -> dict:
    book = store.get_book(book_id)
    if not book:
        raise HTTPException(404, f"Book {book_id!r} has not been processed in this database")
    return book


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "mode": "demo" if DEMO else "model", "model": None if DEMO else settings.model}


@app.get("/api/books")
def books(store: Store = Depends(get_store)) -> list[dict]:
    return store.list_books()


@app.get("/api/books/{book_id}")
def book_snapshot(book_id: str, store: Store = Depends(get_store)) -> dict:
    _book_or_404(store, book_id)
    return graph.snapshot(store, book_id)


@app.get("/api/books/{book_id}/journey")
def journey(book_id: str, store: Store = Depends(get_store)) -> dict:
    _book_or_404(store, book_id)
    j = store.get_journey(book_id)
    if j is None:
        raise HTTPException(404, "No Journey synthesized yet; run: python -m motif.cli journey " + book_id)
    return j


@app.get("/api/books/{book_id}/connections")
def connections(book_id: str, top: int = 5, store: Store = Depends(get_store)) -> list[dict]:
    _book_or_404(store, book_id)
    return graph.cross_passage_connections(store, book_id, top=top)


@app.get("/api/books/{book_id}/relations/{rel_id}")
def relation(book_id: str, rel_id: str, store: Store = Depends(get_store)) -> dict:
    _book_or_404(store, book_id)
    detail = graph.relation_detail(store, book_id, rel_id)
    if detail is None:
        raise HTTPException(404, f"Relation {rel_id!r} not found")
    return detail


@app.get("/api/books/{book_id}/chapters")
def chapters(book_id: str, store: Store = Depends(get_store)) -> dict:
    """The book's own chapters, for books whose text file supplies a chapter map ("chapters": offsets into the
    processing text). Passage numbers are internal indices; this maps each passage to the chapter(s) it overlaps."""
    _book_or_404(store, book_id)
    meta_path = settings.texts_dir / f"{book_id}.json"
    chapter_list = json.loads(meta_path.read_text()).get("chapters") if meta_path.exists() else None
    if not chapter_list:
        raise HTTPException(404, f"No chapter map for {book_id!r}")
    ref = lambda c: {"number": c["number"], "numeral": c["numeral"], "title": c["title"], "start": c["start"], "end": c["end"]}
    passages = []
    for p in store.passages(book_id):
        overlapping = [ref(c) for c in chapter_list if min(p["end"], c["end"]) > max(p["start"], c["start"])]
        passages.append({"idx": p["idx"], "start": p["start"], "chapters": overlapping})
    return {"chapters": [ref(c) for c in chapter_list], "passages": passages}
