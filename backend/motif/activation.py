"""Memory activation: which existing units does new material bring back to mind?

Deliberately simple and transparent: IDF-weighted lexical overlap with a crude stemmer,
plus a small recency bonus. No embeddings, so every activation can be explained by the
shared words. This is a provisional choice; embeddings could replace `score` later.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from .schema import Unit

STOPWORDS = set("""
a about above after again against all also am an and any are as at be because been before being
below between both but by can could did do does doing down during each even ever every few for from
further had has have having he her here hers him his how i if in into is it its itself just let like
made make many may me might more most much must my no nor not now of off on once only or other ought
our out over own same say said shall she should so some such than that the their them then there
these they this those through thus to too under until up upon very was we were what when where which
while who whom why will with would yes yet you your one ones thing things way being
""".split())


def stem(word: str) -> str:
    for suffix in ("ings", "ing", "edly", "ed", "ies", "es", "s", "ly"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            word = word[: -len(suffix)]
            break
    if len(word) > 3 and word[-1] == word[-2]:  # turnn -> turn, dragg -> drag
        word = word[:-1]
    return word


def tokens(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in STOPWORDS and len(w) > 2}


def unit_tokens(u: Unit) -> set[str]:
    parts = [u.label, u.content, " ".join(u.participants), u.reading or ""]
    parts += [e.quote for e in u.evidence]
    return tokens(" ".join(parts))


def activate(query: str, units: list[Unit], now: int, k: int = 8) -> list[tuple[float, Unit, list[str]]]:
    """Return up to k (score, unit, shared_terms) for units relevant to `query`, best first."""
    if not units:
        return []
    utoks = {u.id: unit_tokens(u) for u in units}
    df = Counter(t for toks in utoks.values() for t in toks)
    n = len(units)
    q = tokens(query)
    scored = []
    for u in units:
        shared = q & utoks[u.id]
        if not shared:
            continue
        lexical = sum(math.log(1 + n / df[t]) for t in shared) / math.sqrt(len(utoks[u.id]) + 1)
        recency = 0.15 / (1 + max(0, now - u.last_active_at))
        scored.append((lexical + recency, u, sorted(shared)))
    scored.sort(key=lambda x: -x[0])
    return scored[:k]


def activate_for_units(new_texts: list[str], units: list[Unit], now: int,
                       salience: dict[str, int] | None = None,
                       per_unit: int = 6, cap: int = 20, n_salient: int = 4) -> list[Unit]:
    """Working memory for integrating a passage.

    Two channels: (1) cue-driven recall, the union of the top lexical matches for each new
    unit; (2) salience, the few units most often reinforced, related or revised so far
    (the threads a reader keeps in mind). Capped, returned in reading order.
    """
    best: dict[str, tuple[float, Unit]] = {}
    for text in new_texts:
        for score, u, _ in activate(text, units, now, k=per_unit):
            if u.id not in best or best[u.id][0] < score:
                best[u.id] = (score, u)
    chosen = [u for _, u in sorted(best.values(), key=lambda x: -x[0])[:cap]]
    if salience:
        by_id = {u.id: u for u in units}
        ranked = sorted((uid for uid in salience if uid in by_id), key=lambda uid: -salience[uid])
        for uid in ranked[:n_salient]:
            if salience[uid] > 1 and by_id[uid] not in chosen:
                chosen.append(by_id[uid])
    return sorted(chosen, key=lambda u: (u.introduced_at, u.id))
