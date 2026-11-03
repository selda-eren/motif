import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { App } from "./App";
import relationJson from "./__fixtures__/demo-relation.r05_2.json";
import journeyJson from "./__fixtures__/demo-journey.plato_cave.json";
import snapJson from "./__fixtures__/demo-snapshot.plato_cave.json";

function mockApi(provenance = "demo-fixture", withJourney: boolean | object = true, extraSnap: object = {}, otherBooks: object[] = []) {
  const snap = { ...snapJson, ...extraSnap, book: { ...snapJson.book, provenance, model: provenance === "model" ? "muse-spark-1.3" : snapJson.book.model } };
  const routes: Record<string, unknown> = {
    "/api/books": [snap.book, ...otherBooks],
    "/api/books/plato_cave": snap,
    "/api/books/plato_cave/connections?top=5": [{ ...relationJson, score: 1 }],
    "/api/books/plato_cave/relations/r05_2": relationJson,
  };
  if (withJourney) routes["/api/books/plato_cave/journey"] = withJourney === true ? journeyJson : withJourney;
  vi.stubGlobal("fetch", vi.fn(async (url: string) => {
    if (!(url in routes)) return new Response("not found", { status: 404 });
    return new Response(JSON.stringify(routes[url]), { status: 200 });
  }));
}

window.scrollTo = () => {};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

it("labels offline data as demonstration data", async () => {
  mockApi();
  render(<App />);
  expect(await screen.findByText("Demonstration data.")).toBeTruthy();
  expect(screen.getByText(/not model output and do not show/)).toBeTruthy();
  expect(screen.getByText(/hand-authored demonstration, not model output/)).toBeTruthy(); // Journey key line
  fireEvent.click(screen.getByText(/^The Weave/));
  expect(screen.getByText("demonstration data · not model output")).toBeTruthy(); // Weave inspector stamp
});

it("labels model output differently", async () => {
  mockApi("model");
  render(<App />);
  expect(await screen.findByText(/Powered by Muse Spark 1\.3/)).toBeTruthy();
  expect(screen.queryByText("Demonstration data.")).toBeNull();
  expect(screen.queryByText("Model output")).toBeNull(); // the long banner is gone
  // the Journey still separates quotations from interpretation
  expect(await screen.findByText(/is MOTIF's interpretation/)).toBeTruthy();
});

it("keeps the demonstration banner and no model credit for hand-authored data", async () => {
  mockApi("demo-fixture");
  render(<App />);
  expect(await screen.findByText("Demonstration data.")).toBeTruthy();
  expect(screen.queryByText(/Powered by/)).toBeNull();
});

it("the information button opens the disclosure and Escape closes it without clearing the view", async () => {
  mockApi("model");
  render(<App />);
  const info = await screen.findByRole("button", { name: "About these interpretations" });
  const pop = () => document.querySelector(".modelnote__pop") as HTMLElement;
  expect(info.getAttribute("aria-expanded")).toBe("false");
  expect(pop().hidden).toBe(true);
  fireEvent.click(info);
  expect(info.getAttribute("aria-expanded")).toBe("true");
  expect(pop().hidden).toBe(false);
  expect(info.getAttribute("aria-controls")).toBe(pop().id);
  expect(pop().textContent).toContain("MOTIF uses Meta's Muse Spark 1.3 to construct evidence-linked interpretations.");
  expect(pop().textContent).toContain("Quotations are verified against the source text; AI-generated interpretations have not been independently validated.");
  fireEvent.keyDown(window, { key: "Escape" });
  await waitFor(() => expect(info.getAttribute("aria-expanded")).toBe("false"));
  expect(pop().hidden).toBe(true);
});

it("arranges the header as brand and book, title block, then view tabs", async () => {
  mockApi("model", true, {}, [{ ...snapJson.book, id: "other", title: "Another Book", provenance: "model" }]);
  render(<App />);
  await screen.findByText(/Powered by Muse Spark 1\.3/);
  const header = document.querySelector("header.masthead") as HTMLElement;
  const kids = [...header.children].map((c) => c.className);
  expect(kids).toEqual(["masthead__top", "masthead__book", "views"]);
  const top = header.querySelector(".masthead__top") as HTMLElement;
  expect(top.textContent).toContain("MOTIF");
  expect(top.querySelector("select")?.getAttribute("aria-label")).toBe("Book");
  expect(header.querySelector(".masthead__book h1")).toBeTruthy();
  const tabs = [...header.querySelectorAll(".views__tab")].map((t) => t.textContent);
  expect(tabs[0]).toContain("Journey");
  expect(tabs[1]).toContain("The Weave");
});

it("clicking a relation shows both original quotations and the revised reading", async () => {
  mockApi();
  window.history.replaceState(null, "", "/#weave");
  render(<App />);
  const knot = await screen.findByTestId("relation-r05_2");
  fireEvent.click(knot);
  await waitFor(() => expect(screen.getByText("Why the system linked them")).toBeTruthy());
  expect(screen.getByText("being prevented by the chains from turning round their heads")).toBeTruthy();
  expect(screen.getByText(/the instrument of knowledge can only by the movement of the whole soul/)).toBeTruthy();
  expect(screen.getByText(/How its reading changed/)).toBeTruthy();
  expect(window.location.hash).toBe("#rel=r05_2");
});

it("clicking a passage shows its text with evidence highlighted", async () => {
  mockApi();
  window.history.replaceState(null, "", "/#weave");
  render(<App />);
  fireEvent.click(await screen.findByTestId("passage-0"));
  const marks = document.querySelectorAll(".passage-text mark");
  expect(marks.length).toBeGreaterThan(3);
});

it("opens on the Journey: overview, stages and transitions, marked as interpretation", async () => {
  mockApi();
  render(<App />);
  expect(await screen.findByText(journeyJson.overview)).toBeTruthy();
  for (const st of journeyJson.stages) expect(screen.getByText(st.title)).toBeTruthy();
  expect(screen.getAllByTestId(/^transition-/)).toHaveLength(journeyJson.stages.length - 1);
  expect(screen.getByText(journeyJson.stages[0].title).className).toContain("gen");
  expect(document.querySelector(".loom")).toBeNull(); // The Weave is not rendered on the Journey
});

it("a stage reveals its quotations and opens connections in The Weave", async () => {
  mockApi();
  render(<App />);
  fireEvent.click(await screen.findByTestId("stage-0"));
  const detail = screen.getByTestId("stage-detail");
  const firstKey = snapJson.units.find((u) => u.id === journeyJson.stages[0].key_units[0])!;
  expect(detail.textContent).toContain(firstKey.evidence[0].quote);
  expect(window.location.hash).toBe("#stage=1");

  fireEvent.click(screen.getAllByText("open in The Weave")[0]);
  expect(window.location.hash).toMatch(/^#rel=r\d{2}_\d+$/);
  expect(document.querySelector(".loom")).not.toBeNull();
});

it("explains how to create a Journey when none exists", async () => {
  mockApi("demo-fixture", false);
  render(<App />);
  expect(await screen.findByText(/No Journey has been synthesized/)).toBeTruthy();
});

it("shows no internal ids in the Journey text", async () => {
  mockApi();
  render(<App />);
  await screen.findByText(journeyJson.overview);
  fireEvent.click(screen.getByTestId("stage-2"));
  const text = document.querySelector(".journey")!.textContent!;
  expect(text).not.toMatch(/\b(u\d{2}_\d+|r\d{2}_\d+|n\d+|NEW|TARGET)\b/);
});

it("labels each transition with the kind of intellectual move", async () => {
  mockApi();
  render(<App />);
  await screen.findByText(journeyJson.overview);
  const kinds = journeyJson.explanation!.transitions.map((t) => t.kind);
  const badges = screen.getAllByTestId("kind-badge").map((b) => b.textContent);
  expect(badges).toEqual(kinds.map((k) => ({ development: "Develops", reinterpretation: "Reinterprets", contradiction: "Challenges",
    consequence: "Draws a consequence", analogy: "Draws a parallel", succession: "Comes next", unclassified: "Unclassified" } as Record<string, string>)[k]));
  // In the woven path the move's explanation opens on selection...
  fireEvent.click(screen.getByTestId("transition-2"));
  expect(screen.getByTestId("move-detail").textContent).toContain(journeyJson.explanation!.transitions[2].what_changes);
  // ...and the card fallback still prints it under each transition.
  fireEvent.click(screen.getByText("Cards"));
  expect(screen.getByTestId("transition-2").textContent).toContain(journeyJson.explanation!.transitions[2].what_changes);
});

it("discloses understanding first, then evidence, then the research detail", async () => {
  mockApi();
  render(<App />);
  fireEvent.click(await screen.findByTestId("stage-3"));
  const x = journeyJson.explanation!;
  const detail = screen.getByTestId("stage-detail");
  expect(detail.textContent).toContain(x.stages[3].what_changes);
  expect(detail.textContent).toContain(x.stages[3].why_it_matters);
  expect(screen.getByTestId("incoming-transition").textContent).toContain(x.transitions[2].why);
  const evidence = screen.getByTestId("level-evidence") as HTMLDetailsElement;
  const research = screen.getByTestId("level-detail") as HTMLDetailsElement;
  expect(evidence.open).toBe(false);
  expect(research.open).toBe(false);
  // Level 2: each quotation is the text's own words, with a generated note on how it supports the reading.
  for (const q of x.stages[3].quotes) {
    expect(evidence.textContent).toContain(`“${q.quote}”`);
    expect(evidence.textContent).toContain(q.how_it_supports);
  }
  for (const e of x.transitions[2].evidence) expect(evidence.textContent).toContain(e.earlier.quote);
});

it("never presents an unsupported transition as definitive", async () => {
  const j = structuredClone(journeyJson);
  j.explanation!.transitions[0] = { ...j.explanation!.transitions[0], kind: "unclassified", certainty: "tentative", evidence: [],
    grounding_note: "Proposed as consequence, but no recorded link between these stages was cited, so MOTIF does not present it as an established connection.",
    limitation: "" };
  mockApi("demo-fixture", j);
  render(<App />);
  await screen.findByText(j.overview);
  const badge = screen.getAllByTestId("kind-badge")[0];
  expect(badge.textContent).toBe("Unclassified · tentative");
  fireEvent.click(screen.getByTestId("stage-1"));
  expect(screen.getByTestId("caveat").textContent).toContain("does not present it as an established connection");
});

it("falls back gracefully when no explanation layer exists", async () => {
  const j = structuredClone(journeyJson);
  delete (j as { explanation?: unknown }).explanation;
  mockApi("demo-fixture", j);
  render(<App />);
  await screen.findByText(j.overview);
  expect(screen.queryAllByTestId("kind-badge")).toHaveLength(0);
  expect(screen.getAllByText("Leads on")).toHaveLength(j.stages.length - 1); // unclassified, not invented kinds
  fireEvent.click(screen.getByText("Cards"));
  expect(screen.getAllByText("why this leads on")).toHaveLength(j.stages.length - 1);
  fireEvent.click(screen.getByTestId("stage-0"));
  expect(screen.getByTestId("level-evidence").textContent).toContain("“");
});

it("shows a constructed meaning with the units and quotations it was built from", async () => {
  const [a, b] = snapJson.units;
  const meaning = {
    id: "c00_1", statement: "Both images together suggest a shared captivity.", passage: 0,
    contributors: [{ unit_id: a.id, role: "first image" }, { unit_id: b.id, role: "second image" }],
    relationship: "parallel", basis: "inferred", relation_to_existing: "new", related_to: null,
    justification: "j", limitations: "The units do not show the cause.", model_confidence: 0.7,
    evidence: [{ unit_id: a.id, passage: 0, quote: a.evidence[0].quote }, { unit_id: b.id, passage: 0, quote: b.evidence[0].quote }],
    triggers: ["R1 reinterpretation"],
    reinforcements: [{ passage: 2, new_units: [b.id], statement: "s", via: "model" }],
    strength: { distinct_units: 2, distinct_passages: 1, reinforcements: 1 },
  };
  const journey = { ...journeyJson, stages: journeyJson.stages.map((s, i) => (i === 0 ? { ...s, key_meanings: ["c00_1"] } : s)) };
  mockApi("model", journey, { constructions: [meaning] });
  window.history.replaceState(null, "", "/#stage=1");
  render(<App />);
  const card = await screen.findByTestId("constructed-meaning");
  expect(card.textContent).toContain("Both images together suggest a shared captivity.");
  expect(card.textContent).toContain(a.label);
  expect(card.textContent).toContain(b.evidence[0].quote);
  expect(card.textContent).toContain("MOTIF's inference");
  expect(screen.getByTestId("meaning-support").textContent).toContain("reinforced by new evidence in passage 3");
});

// ---------- the woven Journey path ----------

function withMeanings() {
  const units = snapJson.units;
  const byStage = (i: number) => units.filter((u) => u.introduced_at >= journeyJson.stages[i].first_passage
    && u.introduced_at <= journeyJson.stages[i].last_passage);
  const last = journeyJson.stages.length - 1;
  const [a] = byStage(0);
  const [b] = byStage(last);
  const mk = (id: string, status: string, statement: string) => ({
    id, statement, passage: journeyJson.stages[last].first_passage, status,
    contributors: [{ unit_id: a.id, role: "early image" }, { unit_id: b.id, role: "late claim" }],
    relationship: "contrast", basis: "inferred", relation_to_existing: "new", related_to: null, justification: "They combine.",
    limitations: "Not shown: the cause.", model_confidence: 0.6, triggers: ["R1 reinterpretation"],
    evidence: [{ unit_id: a.id, passage: a.introduced_at, quote: a.evidence[0].quote }, { unit_id: b.id, passage: b.introduced_at, quote: b.evidence[0].quote }],
  });
  const constructions = [mk("c09_1", "established", "An established meaning across the book."),
                         mk("c09_2", "pending", "A pending meaning that must not appear.")];
  const journey = { ...journeyJson, stages: journeyJson.stages.map((s, i) => (i === last ? { ...s, key_meanings: ["c09_1", "c09_2"] } : s)) };
  return { constructions, journey, a, b };
}

it("draws the journey as a woven path: one titled knot per stage, a labelled move between each pair", async () => {
  mockApi("model");
  render(<App />);
  const path = await screen.findByTestId("journey-path");
  journeyJson.stages.forEach((st, i) => expect(screen.getByTestId(`stage-${i}`).textContent).toContain(st.title));
  expect(path.querySelectorAll(".jp__knot")).toHaveLength(journeyJson.stages.length);
  expect(screen.getAllByTestId("kind-badge")).toHaveLength(journeyJson.stages.length - 1);
  // The legend names only the kinds of move that occur.
  const legend = screen.getByLabelText("How to read the journey").textContent!;
  for (const t of journeyJson.explanation!.transitions) expect(legend.toLowerCase()).toContain(
    ({ development: "develops", reinterpretation: "reinterprets", contradiction: "challenges", consequence: "draws a consequence",
       analogy: "draws a parallel", succession: "comes next", unclassified: "unclassified" } as Record<string, string>)[t.kind]);
});

it("shows established constructed meanings as landmarks and never pending ones", async () => {
  const { constructions, journey, a, b } = withMeanings();
  mockApi("model", journey, { constructions });
  render(<App />);
  await screen.findByTestId("journey-path");
  expect(screen.queryByTestId("meaning-c09_2")).toBeNull();
  fireEvent.click(screen.getByTestId("meaning-c09_1"));
  const detail = screen.getByTestId("meaning-detail");
  expect(detail.textContent).toContain("An established meaning across the book.");
  expect(detail.textContent).toContain(a.evidence[0].quote);
  expect(detail.textContent).toContain(b.evidence[0].quote);
  expect(detail.textContent).not.toContain("A pending meaning");
  fireEvent.click(screen.getAllByText("open in The Weave")[0]);
  expect(window.location.hash).toBe(`#unit=${a.id}`);
});

it("draws a return only where a later stage rereads or reframes an earlier one, with the recorded readings", async () => {
  mockApi("model");
  render(<App />);
  await screen.findByTestId("journey-path");
  const handles = screen.queryAllByTestId(/^return-/);
  const stageOf = (p: number) => journeyJson.stages.findIndex((s) => s.first_passage <= p && p <= s.last_passage);
  const units = new Map(snapJson.units.map((u) => [u.id, u]));
  const expected = new Set<string>();
  for (const v of snapJson.revisions) {
    const a = stageOf(units.get(v.unit_id)!.introduced_at), b = stageOf(v.passage);
    if (a < b) expected.add(`return-${b}-${a}`);
  }
  for (const r of snapJson.relations) {
    if (r.type !== "REFRAMES" && r.type !== "CONTRADICTS") continue;
    const [a, b] = [stageOf(units.get(r.source)!.introduced_at), stageOf(units.get(r.target)!.introduced_at)].sort((x, y) => x - y);
    if (a < b) expected.add(`return-${b}-${a}`);
  }
  const shown = handles.map((h) => h.getAttribute("data-testid")!);
  expect(shown.length).toBeGreaterThan(0);
  for (const id of shown) expect(expected.has(id)).toBe(true); // nothing drawn without a recorded rereading
  if (expected.size <= 6) expect(new Set(shown)).toEqual(expected); // and nothing recorded left out (up to the cap)
  fireEvent.click(handles[0]);
  const detail = screen.getByTestId("return-detail");
  expect(detail.textContent).toMatch(/revised reading|reframes|contradicts/);
  expect(detail.querySelector("blockquote, .gen")).toBeTruthy();
});

it("opens a move with its kind, explanation, limits and evidence, and links into The Weave", async () => {
  mockApi("model");
  render(<App />);
  await screen.findByTestId("journey-path");
  const x = journeyJson.explanation!;
  const i = x.transitions.findIndex((t) => t.evidence.some((e) => e.relation_id));
  fireEvent.click(screen.getByTestId(`transition-${i}`));
  const detail = screen.getByTestId("move-detail");
  expect(detail.textContent).toContain(x.transitions[i].why);
  expect(detail.textContent).toContain(x.transitions[i].evidence[0].earlier.quote);
  const rel = x.transitions[i].evidence.find((e) => e.relation_id)!;
  fireEvent.click(screen.getAllByText("open in The Weave")[x.transitions[i].evidence.indexOf(rel)]);
  expect(window.location.hash).toBe(`#rel=${rel.relation_id}`);
});

it("marks a tentative move in the drawing, not only in words", async () => {
  mockApi("model");
  render(<App />);
  const path = await screen.findByTestId("journey-path");
  const tentative = journeyJson.explanation!.transitions.filter((t) => t.certainty === "tentative").length;
  expect(path.querySelectorAll(".jp__thread.is-tentative")).toHaveLength(tentative);
});
