"""Command line: process a text into a MORe representation and inspect the result.

  python -m motif.cli segments plato_cave
  python -m motif.cli process plato_cave --offline        # hand-authored demo, no API calls
  python -m motif.cli process plato_cave --limit 2        # real model, first two passages
  python -m motif.cli show plato_cave [--offline]
  python -m motif.cli check                               # verify API key + model (free endpoint)
  python -m motif.cli usage [--run RUN_ID]                # token usage and cost
"""
from __future__ import annotations

import argparse
import sys
import textwrap

from . import graph
from .config import load_settings
import httpx

from .llm import BudgetExceeded, FixtureClient, LLMError, MetaModelClient
from .pipeline import process_book
from .store import Store
from .text import load_book, segment

DEMO_BANNER = ("[OFFLINE DEMO] Hand-authored sample data replayed through the real pipeline. "
               "This is NOT model output.")


def _wrap(s: str, indent: str = "    ") -> str:
    return textwrap.fill(s, width=96, initial_indent=indent, subsequent_indent=indent)


def cmd_segments(args, settings) -> None:
    book = load_book(settings.texts_dir, args.book)
    for p in segment(book.text):
        print(f"--- passage {p.index + 1} ({len(p.text.split())} words) ---")
        print(_wrap(p.text[:240] + " ..."))


def cmd_process(args, settings) -> None:
    book = load_book(settings.texts_dir, args.book)
    if args.offline:
        print(DEMO_BANNER)
        store = Store(settings.demo_db_path)
        client = FixtureClient(settings.demo_dir / f"{args.book}.fixture.json")
    else:
        store = Store(settings.db_path)
        client = MetaModelClient(settings, store, log=print)
        print(f"Meta Model API: model={settings.model} reasoning_effort={settings.reasoning_effort} "
              f"max_completion_tokens={settings.max_completion_tokens} attempts={settings.max_attempts} "
              f"propagate={settings.propagate} construct={settings.construct}")
        print(f"Budget: ${settings.budget_usd:.2f} total; already spent ${store.total_spend_usd():.4f} "
              f"(responses cached in {settings.db_path})")
    try:
        process_book(book, client, store, limit=args.limit, reset=args.reset,
                     propagate=settings.propagate and not args.offline,
                     construct=settings.construct and not args.offline)
    finally:
        if not args.offline:
            print()
            _print_usage(store.usage_rows(client.run_id), f"This run ({client.run_id})")
            print(f"Total spent in {settings.db_path.name}: ${store.total_spend_usd():.4f} "
                  f"of ${settings.budget_usd:.2f} budget")
    _show(store, args.book, top=3)


def _print_usage(rows: list[dict], title: str) -> None:
    print(f"{title}:")
    if not rows:
        print("  (no calls)")
        return
    print(f"  {'call':<16}{'status':<15}{'input':>8}{'cached':>8}{'output':>8}{'reasoning':>10}{'cost $':>10}{'secs':>7}")
    tot = dict(p=0, c=0, o=0, r=0, usd=0.0)
    for r in rows:
        print(f"  {r['task'][:5] + '/' + r['key']:<16}{r['status']:<15}{r['prompt_tokens']:>8}{r['cached_tokens']:>8}"
              f"{r['completion_tokens']:>8}{r['reasoning_tokens']:>10}{r['cost_usd']:>10.4f}{r['latency_s']:>7.1f}")
        tot["p"] += r["prompt_tokens"]; tot["c"] += r["cached_tokens"]; tot["o"] += r["completion_tokens"]
        tot["r"] += r["reasoning_tokens"]; tot["usd"] += r["cost_usd"]
    print(f"  {'TOTAL':<31}{tot['p']:>8}{tot['c']:>8}{tot['o']:>8}{tot['r']:>10}{tot['usd']:>10.4f}")


def cmd_usage(args, settings) -> None:
    store = Store(settings.db_path)
    rows = store.usage_rows(args.run)
    runs = sorted({r["run_id"] for r in rows})
    for run in runs:
        _print_usage([r for r in rows if r["run_id"] == run], f"Run {run}")
        print()
    print(f"Total spent: ${store.total_spend_usd():.4f} of ${settings.budget_usd:.2f} budget")


def cmd_check(args, settings) -> None:
    """Free configuration check: lists models (no tokens billed) and confirms the configured one."""
    print(f"API base:  {settings.api_base}")
    print(f"Model:     {settings.model}  reasoning_effort={settings.reasoning_effort}")
    print(f"API key:   {'set (' + str(len(settings.api_key)) + ' chars)' if settings.api_key else 'NOT SET'}")
    print(f"Budget:    ${settings.budget_usd:.2f}   max_completion_tokens={settings.max_completion_tokens}   "
          f"attempts={settings.max_attempts}")
    if not settings.api_key:
        sys.exit("error: MODEL_API_KEY is not set (copy .env.example to .env).")
    resp = httpx.get(f"{settings.api_base}/models", headers={"Authorization": f"Bearer {settings.api_key}"},
                     timeout=30)
    if resp.status_code != 200:
        sys.exit(f"error: GET /models returned HTTP {resp.status_code}: {resp.text[:300]}")
    ids = sorted(m.get("id", "?") for m in resp.json().get("data", []))
    print(f"Models visible to this key: {', '.join(ids)}")
    if settings.model not in ids:
        sys.exit(f"error: configured model {settings.model!r} is not in the list.")
    print("OK: key accepted and model available.")


def cmd_journey(args, settings) -> None:
    from .journey import synthesize
    if args.offline:
        print(DEMO_BANNER)
        store = Store(settings.demo_db_path)
        client = FixtureClient(settings.demo_dir / f"{args.book}.fixture.json")
    else:
        store = Store(settings.db_path)
        client = MetaModelClient(settings, store, log=print)
    if not store.get_book(args.book):
        sys.exit(f"{args.book!r} has not been processed in this database.")
    try:
        j = synthesize(client, store, args.book)
    finally:
        if not args.offline:
            _print_usage(store.usage_rows(client.run_id), f"This run ({client.run_id})")
    print(f"\n{j['overview']}\n")
    for s in j["stages"]:
        print(f"{s['index'] + 1}. {s['title']}  (passages {s['first_passage'] + 1}-{s['last_passage'] + 1})")
        print(_wrap(s["summary"]))
        if s["leads_to_next"]:
            print(_wrap("-> " + s["leads_to_next"], "       "))
    for w in j["warnings"]:
        print("warning:", w)


def cmd_explain(args, settings) -> None:
    from .explain import explain
    if args.offline:
        print(DEMO_BANNER)
        store = Store(settings.demo_db_path)
        client = FixtureClient(settings.demo_dir / f"{args.book}.fixture.json")
    else:
        store = Store(settings.db_path)
        client = MetaModelClient(settings, store, log=print)
    try:
        x = explain(client, store, args.book)
    finally:
        if not args.offline:
            _print_usage(store.usage_rows(client.run_id), f"This run ({client.run_id})")
    for t in x["transitions"]:
        print(f"\nStage {t['from_index'] + 1} -> {t['to_index'] + 1}: {t['kind'].upper()} ({t['certainty']})")
        print(_wrap(t["what_changes"]))
        print(_wrap("Why: " + t["why"]))
        for e in t["evidence"]:
            print(_wrap(f"[{e['type'].lower()}] \"{e['earlier']['quote'][:70]}\" / \"{e['later']['quote'][:70]}\"", "      "))
            print(_wrap(e["how_it_supports"], "        "))
        for line in (t["limitation"], t["grounding_note"]):
            if line:
                print(_wrap("Limit: " + line))
    for w in x["warnings"]:
        print("warning:", w)


def cmd_show(args, settings) -> None:
    store = Store(settings.demo_db_path if args.offline else settings.db_path)
    _show(store, args.book, top=args.top)


def _show(store: Store, book_id: str, top: int) -> None:
    book = store.get_book(book_id)
    if not book:
        sys.exit(f"{book_id!r} has not been processed in this database.")
    if book["provenance"] != "model":
        print(DEMO_BANNER)
    else:
        print(f"Provenance: model output ({book['model']})")
    units = store.units(book_id)
    print(f"\n{len(units)} units, {len(store.relations(book_id))} relations, "
          f"{len(store.revisions(book_id))} revisions, {len(store.constructions(book_id))} constructed meanings\n")
    print("Change per passage (what the representation did):")
    for c in graph.passage_changes(store, book_id):
        if not c["processed"]:
            continue
        bar = "~" * int(round(c["change_score"]))
        print(f"  {c['passage'] + 1:>2} {c['change_score']:>5}  {bar}")
        print(_wrap(c["gist"] or "", "          "))
    by_id = {u.id: u for u in units}
    for c in store.constructions(book_id):
        status = "" if c.status == "established" else f", PENDING: {c.pending_reason}"
        print(f"Constructed meaning {c.id} (passage {c.passage + 1}, {c.basis}{status}): {c.statement}")
        print(_wrap("built from: " + "; ".join(f"{by_id[x.unit_id].label} ({x.role})" for x in c.contributors)))
    print(f"\nStrongest cross-passage connections (formed by integration):")
    for i, d in enumerate(graph.cross_passage_connections(store, book_id, top=top), 1):
        r, s, t = d["relation"], d["source"], d["target"]
        print(f"\n {i}. [{s['label']}] (passage {s['introduced_at'] + 1}) "
              f"--{r['type']}--> [{t['label']}] (passage {t['introduced_at'] + 1})  conf={r['confidence']:.2f}")
        print(_wrap("Why: " + r["rationale"]))
        for u in sorted((s, t), key=lambda u: u["introduced_at"]):
            for ev in u["evidence"]:
                print(_wrap(f"Evidence [{u['label']}], passage {ev['passage'] + 1}: \"{ev['quote']}\""))
        earlier = s if d["earlier"] == s["id"] else t
        if earlier.get("reading"):
            print(_wrap(f"Current reading of the earlier unit: {earlier['reading']}"))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="motif")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("segments"); p.add_argument("book")
    p = sub.add_parser("process"); p.add_argument("book")
    p.add_argument("--offline", action="store_true", help="replay the hand-authored demo fixture (no API calls)")
    p.add_argument("--limit", type=int, help="process only the first N passages")
    p.add_argument("--reset", action="store_true", help="discard the stored representation first")
    p = sub.add_parser("show"); p.add_argument("book"); p.add_argument("--offline", action="store_true")
    p.add_argument("--top", type=int, default=5)
    sub.add_parser("check")
    p = sub.add_parser("explain"); p.add_argument("book"); p.add_argument("--offline", action="store_true")
    p = sub.add_parser("journey"); p.add_argument("book"); p.add_argument("--offline", action="store_true")
    p = sub.add_parser("usage"); p.add_argument("--run")
    args = parser.parse_args(argv)
    settings = load_settings()
    try:
        commands = {"segments": cmd_segments, "process": cmd_process, "show": cmd_show,
                    "check": cmd_check, "usage": cmd_usage, "journey": cmd_journey, "explain": cmd_explain}
        commands[args.cmd](args, settings)
    except (LLMError, BudgetExceeded, ValueError) as exc:
        sys.exit(f"error: {exc}")


if __name__ == "__main__":
    main()
