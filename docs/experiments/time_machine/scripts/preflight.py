"""Preflight for the full-book run: size, expected model calls, runtime and cost, calibrated on the real
usage logs of the Plato and Gift of the Magi runs (data/motif.m51.db). Free: no API calls."""
import json, sqlite3, statistics, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from motif.text import load_book, segment
from motif.usage import PRICES_PER_M

book = load_book(REPO / "data" / "texts", "the_time_machine")
passages = segment(book.text)
n, words = len(passages), len(book.text.split())
db = sqlite3.connect(REPO / "data" / "motif.m51.db")
rows = db.execute("select task, count(*), avg(cost_usd), avg(latency_s), avg(prompt_tokens), avg(completion_tokens), max(cost_usd) "
                  "from usage_log where status='ok' group by task").fetchall()
st = {r[0]: dict(n=r[1], cost=r[2], secs=r[3], tin=r[4], tout=r[5], maxcost=r[6]) for r in rows}
# how often each optional stage fired per passage in the two finished books (propagation/construction were run in M5.1)
fired = {}
for book_id, npass in (("plato_cave", 9), ("gift_of_the_magi", 6)):
    for task in ("propagation", "construction"):
        c = db.execute("select count(*) from usage_log where task=? and status in ('ok','cache_hit') and run_id=(select run_id from usage_log where task='journey' order by ts desc limit 1)", (task,)).fetchone()[0]
rate = {"propagation": 0.70, "construction": 0.80}   # observed share of passages (Plato 6/9 and 7/9, Magi 4/6 and 4/6 after P2)
calls = {"perception": n, "integration": n, "propagation": round(n * rate["propagation"]), "construction": round(n * rate["construction"])}
per = {t: st[t]["cost"] for t in calls}
base = sum(calls[t] * per[t] for t in calls)
secs = sum(calls[t] * st[t]["secs"] for t in calls)
# integration/construction inputs grow with the memory, capped by the working-memory limits; allow +60% on those two inputs' share
growth = 1.6
journey_in_tok = 3_000 + n * 40 + 5.2 * n * 70 + 8.2 * n * 85 + 1.7 * n * 70 + 1.0 * n * 110   # gists, units, relations, revisions, meanings
journey_cost = journey_in_tok * PRICES_PER_M["muse-spark-1.3"]["input"] / 1e6 + 5000 * PRICES_PER_M["muse-spark-1.3"]["output"] / 1e6
explain_cost = (20_000 * PRICES_PER_M["muse-spark-1.3"]["input"] + 8000 * PRICES_PER_M["muse-spark-1.3"]["output"]) / 1e6
est = base * growth + journey_cost + explain_cost
worst = (n * (4) * 0.0575 + journey_cost * 2 + explain_cost * 2)   # every call at the 12,000-token output cap, input as observed
report = {"book": "The Time Machine (H. G. Wells), Project Gutenberg #35", "words": words, "chapters": 17, "passages": n,
          "passage_words": {"min": min(len(p.text.split()) for p in passages), "median": statistics.median(len(p.text.split()) for p in passages),
                            "max": max(len(p.text.split()) for p in passages)},
          "expected_calls": {**calls, "journey": 1, "explain": 1, "total": sum(calls.values()) + 2},
          "calibration": {t: {"mean_cost_usd": round(st[t]["cost"], 4), "mean_seconds": round(st[t]["secs"], 1),
                              "mean_input_tokens": round(st[t]["tin"]), "mean_output_tokens": round(st[t]["tout"])} for t in st},
          "cost_usd": {"central_with_growth_allowance": round(est, 2), "journey": round(journey_cost, 3), "explain": round(explain_cost, 3),
                       "ceiling_every_call_at_output_cap": round(worst, 2), "local_limit": 50.0},
          "runtime_minutes": {"expected": round(secs * 1.25 / 60), "range": [round(secs / 60), round(secs * 1.6 / 60 + 10)]},
          "assumptions": ["per-call cost and latency = means of the 'ok' calls in the Plato and Gift of the Magi runs",
                          f"propagation fires on {rate['propagation']:.0%} and construction on {rate['construction']:.0%} of passages (observed)",
                          "x1.6 allowance on per-passage cost for larger working memory", "Journey input estimated from the digest format"]}
(ROOT / "PREFLIGHT.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report, indent=1))
