"""Export the finished Time Machine run to portable files and write MANIFEST.json (checksums of everything).
Read-only with respect to the run: it never calls the model API.

Outputs under docs/experiments/time_machine/exports/:
  representation.json           final units, evidence, relations, revisions, constructions, activations (raw tables)
  api_snapshot.json             exactly what GET /api/books/<id> returns (The Weave data)
  api_journey.json              exactly what GET /api/books/<id>/journey returns (Journey + transition explanations)
  api_connections.json          GET /api/books/<id>/connections?top=40
  api_relation_details.json     GET /api/books/<id>/relations/<id> for every relation
  constructed_meanings.json     every constructed meaning with contributor labels, roles and verbatim quotations
  revision_history.json         every revision with the unit label, the cause and chapter locations
  statistics.json               counts, per-passage and per-chapter figures, token / cost / time totals
  model_calls.jsonl.gz          every cached model request and response, with cache keys
  usage_log.csv                 every call attempt (ok, cache_hit, errors)
  motif.the_time_machine.db     self-contained SQLite (representation + journey + cache + usage) for the app
"""
import csv, gzip, hashlib, json, shutil, sqlite3, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from motif import construct, explain, graph, integrate, journey, perceive, propagate  # noqa: E402
from motif.experimental.long_run import Experiment, load_progress, read_json_gz  # noqa: E402
from motif.store import Store  # noqa: E402

BOOK = "the_time_machine"
OUT = ROOT / "exports"
OUT.mkdir(exist_ok=True)
exp = Experiment.create(BOOK, ROOT, 50.0)
state_db, side_db = exp.state_db, exp.side_db
sha = lambda b: hashlib.sha256(b).hexdigest()
chapters = json.loads((ROOT / "source" / "chapters.json").read_text())
passages_meta = json.loads((ROOT / "source" / "passages.json").read_text())

# --- consolidated, self-contained database (state + cache + usage) ---------------------------------------
dst = OUT / "motif.the_time_machine.db"
if dst.exists(): dst.unlink()
shutil.copy(state_db, dst)
db = sqlite3.connect(dst)
db.execute("DELETE FROM llm_cache"); db.execute("DELETE FROM usage_log")
db.execute("ATTACH DATABASE ? AS side", (str(side_db),))
db.execute("INSERT INTO llm_cache SELECT * FROM side.llm_cache"); db.execute("INSERT INTO usage_log SELECT * FROM side.usage_log")
db.commit(); db.execute("DETACH DATABASE side"); db.execute("VACUUM"); db.close()

store = Store(dst)
book = store.get_book(BOOK)
units = {u.id: u for u in store.units(BOOK)}

def chapter_of(pos: int) -> dict:
    for c in chapters:
        if c["start"] <= pos <= c["end"]:
            return {"number": c["number"], "numeral": c["numeral"], "title": c["title"]}
    return {"number": None, "numeral": None, "title": None}

def passage_chapter(idx: int) -> list[dict]:
    return [{k: c[k] for k in ("chapter", "numeral", "title")} for c in passages_meta[idx]["chapters"]]

def jdump(name: str, obj) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False))

# --- raw representation ----------------------------------------------------------------------------------
final_state = read_json_gz(ROOT / "checkpoints" / f"state_after_p{len(passages_meta):03d}.json.gz")
jdump("representation.json", final_state)
snap = graph.snapshot(store, BOOK)
jdump("api_snapshot.json", snap)
jr = store.get_journey(BOOK)
jdump("api_journey.json", jr if jr is not None else {"MISSING": "no journey stored"})
jdump("api_connections.json", graph.cross_passage_connections(store, BOOK, top=40))
jdump("api_relation_details.json", {r.id: graph.relation_detail(store, BOOK, r.id) for r in store.relations(BOOK)})

# --- constructed meanings with evidence ------------------------------------------------------------------
cm = []
for c in store.constructions(BOOK):
    d = c.model_dump()
    d["contributors_detail"] = [{"unit_id": x.unit_id, "label": units[x.unit_id].label, "role": x.role,
                                 "introduced_at_passage": units[x.unit_id].introduced_at + 1,
                                 "chapters": passage_chapter(units[x.unit_id].introduced_at),
                                 "quotations": [{"passage": e.passage + 1, "chapters": passage_chapter(e.passage), "quote": e.quote}
                                                for e in units[x.unit_id].evidence]} for x in c.contributors]
    d["formed_in_passage"] = c.passage + 1
    d["formed_in_chapters"] = passage_chapter(c.passage)
    cm.append(d)
jdump("constructed_meanings.json", cm)

rev = []
for v in store.revisions(BOOK):
    u = units[v.unit_id]
    rev.append({**v.model_dump(), "unit_label": u.label, "unit_introduced_passage": u.introduced_at + 1,
                "unit_chapters": passage_chapter(u.introduced_at), "revised_in_passage": v.passage + 1,
                "revised_in_chapters": passage_chapter(v.passage), "distance_passages": v.passage - u.introduced_at,
                "unit_quotations": [e.quote for e in u.evidence]})
jdump("revision_history.json", rev)

# --- statistics ------------------------------------------------------------------------------------------
rels = store.relations(BOOK)
dist = [abs(units[r.source].introduced_at - units[r.target].introduced_at) for r in rels]
usage = store.usage_rows()
ok = [u for u in usage if u["status"] == "ok"]
by_task = defaultdict(lambda: Counter())
for u in ok:
    t = by_task[u["task"]]; t["calls"] += 1; t["cost_usd"] += u["cost_usd"]; t["seconds"] += u["latency_s"]
    t["prompt_tokens"] += u["prompt_tokens"]; t["completion_tokens"] += u["completion_tokens"]; t["reasoning_tokens"] += u["reasoning_tokens"]
changes = {c["passage"]: c for c in graph.passage_changes(store, BOOK)}
per_chapter = []
for c in chapters:
    idxs = [p["index"] for p in passages_meta if any(x["chapter"] == c["number"] for x in p["chapters"])]
    per_chapter.append({"chapter": c["numeral"], "title": c["title"], "words": c["words"], "passages": [i + 1 for i in idxs],
                        "units_introduced": sum(u.introduced_at in idxs for u in units.values()),
                        "constructed_meanings_formed": sum(m.passage in idxs for m in store.constructions(BOOK))})
long_rels = [r for r, d in zip(rels, dist) if d >= 20]
stats = {"book": book["title"], "model": book["model"], "words": sum(len(p["text"].split()) for p in store.passages(BOOK)),
         "chapters": len(chapters), "passages": len(passages_meta), "units": len(units), "relations": len(rels),
         "revisions": len(rev), "revisions_interpretive": sum(r["kind"] == "interpretive" for r in rev),
         "revisions_state": sum(r["kind"] == "state" for r in rev), "constructed_meanings": len(cm),
         "constructed_established": sum(m["status"] == "established" for m in cm),
         "constructed_pending": sum(m["status"] != "established" for m in cm),
         "relation_types": dict(Counter(r.type for r in rels)),
         "relation_distance_passages": {"median": sorted(dist)[len(dist) // 2] if dist else 0, "max": max(dist, default=0),
                                        "share_ge_10": round(sum(d >= 10 for d in dist) / max(1, len(dist)), 3),
                                        "count_ge_20": len(long_rels)},
         "revisions_distance_ge_20": sum(r["distance_passages"] >= 20 for r in rev),
         "constructions_spanning_ge_20_passages": sum(
             (max(e["passage"] for e in m["evidence"]) - min(e["passage"] for e in m["evidence"])) >= 20 for m in cm if m["evidence"]),
         "constructions_spanning_ge_3_chapters": sum(len({x["chapter"] for e in m["evidence"] for x in passage_chapter(e["passage"])}) >= 3
                                                     for m in cm if m["evidence"]),
         "tasks": {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()} for k, v in by_task.items()},
         "totals": {"api_calls_ok": len(ok), "cache_hits": sum(u["status"] == "cache_hit" for u in usage),
                    "failed_or_uncertain_attempts": dict(Counter(u["status"] for u in usage if u["status"] not in ("ok", "cache_hit"))),
                    "cost_usd": round(sum(u["cost_usd"] for u in usage), 4),
                    "prompt_tokens": sum(u["prompt_tokens"] for u in ok), "completion_tokens": sum(u["completion_tokens"] for u in ok),
                    "reasoning_tokens": sum(u["reasoning_tokens"] for u in ok), "model_seconds": round(sum(u["latency_s"] for u in ok), 1)},
         "per_chapter": per_chapter,
         "per_passage": [{"passage": i + 1, "chapters": [x["numeral"] for x in p["chapters"]], "words": p["words"],
                          "change_score": changes[i]["change_score"] if i in changes else None} for i, p in enumerate(passages_meta)]}
prog = load_progress(exp)
if prog:
    stats["working_memory_and_growth"] = [{"passage": k, "units": v["units"], "relations": v["relations"], "constructions": v["constructions"],
                                           "prompt_tokens": v["prompt_tokens"], "cost_usd": v["cost_usd"], "wall_seconds": v.get("wall_seconds")}
                                          for k, v in sorted(prog.items())]
stats["activation"] = {"mean_recalled_units_per_passage": round(sum(len(p["notes"].get("activated", [])) for p in store.passages(BOOK)) / max(1, len(passages_meta)), 2),
                       "max_recalled_units": max((len(p["notes"].get("activated", [])) for p in store.passages(BOOK)), default=0)}
jdump("statistics.json", stats)

# --- model calls and usage -------------------------------------------------------------------------------
c2 = sqlite3.connect(dst); c2.row_factory = sqlite3.Row
with gzip.open(OUT / "model_calls.jsonl.gz", "wt", encoding="utf-8", compresslevel=9) as f:
    for r in c2.execute("SELECT * FROM llm_cache ORDER BY created_at"):
        f.write(json.dumps({"cache_key": r["key"], "task": r["task"], "model": r["model"], "created_at": r["created_at"],
                            "request": json.loads(r["request_json"]), "response": json.loads(r["response_json"])}, ensure_ascii=False) + "\n")
with (OUT / "usage_log.csv").open("w", newline="") as f:
    w = csv.writer(f); cols = ["ts", "run_id", "task", "key", "model", "reasoning_effort", "status", "prompt_tokens", "cached_tokens",
                               "completion_tokens", "reasoning_tokens", "cost_usd", "latency_s", "finish_reason", "detail"]
    w.writerow(cols)
    for r in c2.execute("SELECT * FROM usage_log ORDER BY ts"): w.writerow([r[c] for c in cols])
unc = ROOT / "logs" / "uncertain_calls.jsonl"
if unc.exists(): shutil.copy(unc, OUT / "uncertain_calls.jsonl")

# --- manifest --------------------------------------------------------------------------------------------
def prompt_hash(name, text): return {"name": name, "sha256": sha(text.encode()), "chars": len(text)}
prompts = [prompt_hash("perception", perceive.SYSTEM), prompt_hash("integration", integrate.SYSTEM), prompt_hash("propagation", propagate.SYSTEM),
           prompt_hash("construction", construct.SYSTEM), prompt_hash("journey", journey.SYSTEM), prompt_hash("explain", explain.SYSTEM)]
code_hash = sha("".join(sha(p.read_bytes()) for p in sorted((REPO / "backend" / "motif").glob("*.py"))).encode())
git = lambda *a: subprocess.run(["git", "-C", str(REPO), *a], capture_output=True, text=True).stdout.strip()
files = {}
for p in sorted(ROOT.rglob("*")):
    if p.is_file() and p.name not in ("MANIFEST.json",) and "__pycache__" not in p.parts and not p.name.endswith(".tmp"):
        rel = str(p.relative_to(ROOT))
        if rel.startswith(("captures/", "clips/")): continue  # listed by the capture manifest
        files[rel] = {"sha256": sha(p.read_bytes()), "bytes": p.stat().st_size}
src = json.loads((ROOT / "source" / "SOURCE.json").read_text())
manifest = {"experiment": "The Time Machine full-book MORe run", "created": __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime()),
            "source": src, "model": book["model"], "model_settings": {"reasoning_effort": exp.settings.reasoning_effort,
                                                                   "max_completion_tokens": exp.settings.max_completion_tokens,
                                                                   "max_attempts": exp.settings.max_attempts, "propagate": exp.settings.propagate,
                                                                   "construct": exp.settings.construct, "tier": "Muse Spark 1.3 Standard"},
            "prompts": prompts, "code": {"git_head": git("rev-parse", "HEAD"), "motif_package_sha256": code_hash,
                                         "note": "backend/motif/*.py except the new experimental/long_run.py are unmodified from the git HEAD"},
            "counts": {k: stats[k] for k in ("words", "chapters", "passages", "units", "relations", "revisions", "constructed_meanings")},
            "totals": stats["totals"], "artifact_locations": {"state_database": "data/motif.the_time_machine.db (gitignored; copy in exports/)",
            "call_cache_database": "data/motif.the_time_machine.calls.db (gitignored; merged into exports/motif.the_time_machine.db)",
            "portable_exports": "docs/experiments/time_machine/exports/", "per_passage_ledgers": "docs/experiments/time_machine/passages/",
            "per_passage_state_checkpoints": "docs/experiments/time_machine/checkpoints/"}, "files": files}
(ROOT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
print(json.dumps({k: stats[k] for k in ("words", "chapters", "passages", "units", "relations", "revisions", "constructed_meanings", "totals")}, indent=1))
print(len(files), "files in manifest")
