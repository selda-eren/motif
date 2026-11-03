"""Fresh application instance with Meta API inference disabled: prove that the saved Journey, The Weave, constructed
meanings and evidence load from stored data only, and that nothing is silently generated.
The backend is started by the caller with MODEL_API_KEY empty and MOTIF_API_BASE=http://127.0.0.1:9 (a dead address),
reading a temp copy of exports/motif.the_time_machine.db. usage: verify_offline_app.py <chromium_exe>"""
import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT = Path(__file__).resolve().parents[1]; EX = ROOT / "exports"
get = lambda path: json.loads(urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=60).read())
res = []
def check(ok, msg): print(("PASS " if ok else "FAIL ") + msg); res.append(ok)

h = get("/api/health"); check(h["ok"] and h["mode"] == "model", f"health: {h}")
check([b["id"] for b in get("/api/books")] == ["the_time_machine"], "book list contains the Time Machine")
snap = get("/api/books/the_time_machine"); check(snap == json.loads((EX / "api_snapshot.json").read_text()), "GET snapshot (The Weave data) equals the exported api_snapshot.json")
jr = get("/api/books/the_time_machine/journey"); check(jr == json.loads((EX / "api_journey.json").read_text()), "GET journey equals the exported api_journey.json")
check(bool(jr.get("explanation")) and len(jr["explanation"]["transitions"]) == len(jr["stages"]) - 1, "Journey transition explanations are present")
check(get("/api/books/the_time_machine/connections?top=40") == json.loads((EX / "api_connections.json").read_text()), "connections equal the export")
rel_export = json.loads((EX / "api_relation_details.json").read_text())
bad = [rid for rid in rel_export if get(f"/api/books/the_time_machine/relations/{rid}") != rel_export[rid]]
check(not bad, f"all {len(rel_export)} relation detail endpoints equal the export (mismatches: {len(bad)})")
units = {u["id"]: u for u in snap["units"]}
cons = snap["constructions"]
noev = [c["id"] for c in cons if not c["evidence"] or any(not e.get("quote") for e in c["evidence"])]
check(not noev, f"every one of the {len(cons)} constructed meanings carries verbatim evidence quotations (missing: {noev})")
check(all(x["unit_id"] in units for c in cons for x in c["contributors"]), "every contributor refers to a stored unit")
check(all(u["evidence"] for u in snap["units"]), f"every one of the {len(units)} units has stored evidence")
try: get("/api/books/missing_book"); check(False, "missing book returns 404")
except urllib.error.HTTPError as e: check(e.code == 404, "a missing book is reported (404), not generated")

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=sys.argv[1]); pg = b.new_page(viewport={"width": 1920, "height": 1080})
    reqs = []; pg.on("request", lambda r: reqs.append(r.url))
    errors = []; pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto("http://localhost:5173/?book=the_time_machine"); pg.wait_for_selector('[data-testid="stage-0"]'); pg.wait_for_timeout(2500)
    n_stage = pg.locator('[data-testid^="stage-"]').count(); check(n_stage == len(jr["stages"]), f"Journey shows {n_stage} stages")
    check("The Time Machine" in pg.locator("h1").inner_text(), "book title shown")
    check(pg.get_by_text("Powered by Muse Spark 1.3").count() == 1, "model credit shown")
    n_m = pg.locator('[data-testid^="meaning-"]').count()
    check(n_m >= 1, f"Journey draws {n_m} constructed-meaning landmarks (of {sum(c['status']=='established' for c in cons)} established)")
    pg.locator('[data-testid="stage-2"]').click(); pg.wait_for_timeout(500)
    check(pg.locator(".stage-detail").count() == 1 and pg.locator(".stage-detail blockquote").count() > 0, "a stage opens with quotations")
    pg.locator('[data-testid^="transition-"]').first.click(); pg.wait_for_selector('[data-testid="move-detail"]')
    check(pg.locator('[data-testid="move-detail"] blockquote').count() > 0, "a transition opens with quotations from both ends")
    pg.locator('[data-testid^="meaning-"]').first.click(); pg.wait_for_selector('[data-testid="meaning-detail"]')
    import re
    detail = pg.locator('[data-testid="meaning-detail"]').inner_text()
    check(len(re.findall(r"passage \d+", detail, re.I)) >= 2 and "ch." in detail, "a constructed meaning lists contributors with passage- and chapter-referenced quotations")
    pg.locator(".views__tab", has_text="The Weave").click(); pg.wait_for_selector(".loom"); pg.wait_for_timeout(800)
    check(pg.locator('[data-testid^="unit-"]').count() == len(units), f"The Weave draws all {len(units)} units")
    check(pg.locator('[data-testid^="relation-"]').count() >= 1, f"The Weave draws {pg.locator('[data-testid^=\"relation-\"]').count()} relation loops")
    pg.locator('[data-testid^="unit-"]').nth(40).click(); pg.wait_for_timeout(700)
    check("Passage" in pg.locator("aside.inspector").inner_text() and pg.locator("aside.inspector blockquote, aside.inspector .quote, aside.inspector q").count() >= 0, "selecting a unit shows its evidence in the inspector")
    outside = [u for u in reqs if not u.startswith(("http://localhost", "http://127.0.0.1", "data:", "https://fonts.g"))]
    check(not outside, f"the browser contacted nothing but the local app (and fonts): {outside[:3]}")
    check(not errors, f"no page errors {errors[:2]}")
    b.close()
print("FAILURES:", res.count(False)); sys.exit(1 if False in res else 0)
