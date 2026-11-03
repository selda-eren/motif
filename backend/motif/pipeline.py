"""Incremental processing: perceive -> ground -> activate -> integrate, one passage at a time."""
from __future__ import annotations

from collections import Counter
from typing import Callable

from . import integrate
from .activation import activate_for_units
from .llm import StructuredClient
from .construct import construct as construct_meanings
from .perceive import ground, perceive
from .propagate import propagate as propagate_changes
from .schema import IntegrationResult
from .store import Store
from .text import Book, segment


def process_book(book: Book, client: StructuredClient, store: Store, *, limit: int | None = None,
                 reset: bool = False, propagate: bool = False, construct: bool = False,
                 log: Callable[[str], None] = print) -> list[dict]:
    if reset:
        store.reset_book(book.id)
    existing = store.get_book(book.id)
    if existing and existing["provenance"] != client.provenance:
        raise ValueError(
            f"{book.id!r} was processed with provenance {existing['provenance']!r}; "
            f"refusing to mix in {client.provenance!r} output. Use --reset.")
    store.upsert_book(book, client.provenance, client.model)
    passages = segment(book.text)
    store.ensure_passages(book.id, passages)
    stored = {p["idx"]: p for p in store.passages(book.id)}

    reports = []
    prev_gist = None
    for p in passages[: limit or len(passages)]:
        if stored[p.index]["processed"]:
            prev_gist = stored[p.index]["gist"]
            continue
        # A passage is atomic. Everything it adds (units, relations, revisions, constructions, the processed flag) is written
        # in ONE transaction that is committed only here, at the end. Model responses and usage rows are durable immediately
        # (they live in the store's separate calls database), so a failure at any stage loses no paid work: the transaction is
        # rolled back, and resuming reprocesses the passage with every completed call served from the cache.
        try:
            perception = perceive(client, book, p, len(passages), prev_gist)
            new_units, rejected = ground(perception.units, p)
            memory = {u.id: u for u in store.units(book.id)}
            activated = activate_for_units(
                [perception.gist] + [f"{u.label} {u.content} {u.evidence[0].quote}" for u in new_units],
                list(memory.values()), p.index,
                salience=Counter(a["unit_id"] for a in store.activations(book.id)))
            if new_units:
                result = integrate.propose(client, p.index, perception.gist, new_units, activated)
            else:
                result = IntegrationResult(decisions=[])
            notes = integrate.apply(store, book.id, p.index, new_units, result, memory,
                                    allowed={u.id for u in activated})
            notes["rejected"] = rejected
            notes["activated"] = [u.id for u in activated]
            if propagate:
                notes["propagation"] = propagate_changes(client, store, book.id, p.index, perception.gist)
            if construct:
                notes["construction"] = construct_meanings(client, store, book.id, p.index, perception.gist)
            store.mark_processed(book.id, p.index, perception.gist, notes)
            store.commit()
        except BaseException:
            store.rollback()
            raise
        prev_gist = perception.gist
        log(f"passage {p.index + 1}/{len(passages)}: +{len(notes['added'])} units, "
            f"{len(notes['merged'])} merged, {len(notes['relations'])} relations, "
            f"{len(notes['revisions'])} revisions, {len(rejected)} ungrounded rejected"
            + (f"; propagation: {len(notes['propagation']['candidates'])} reconsidered, "
               f"{len(notes['propagation']['revisions'])} revised" if propagate else "")
            + (f"; construction: {len(notes['construction']['triggers'])} triggers, "
               f"{len(notes['construction']['accepted'])} meanings, {len(notes['construction']['rejected'])} rejected"
               if construct else ""))
        reports.append(notes)
    return reports
