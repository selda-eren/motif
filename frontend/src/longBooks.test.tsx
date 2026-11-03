import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { App } from "./App";
import { passageSpan } from "./components/Journey";
import { chapterLabeller } from "./passageRef";
import { RETURN_PREVIEW, ReturnDetail } from "./components/JourneyWoven";
import { bringIntoView } from "./components/Loom";
import journeyJson from "./__fixtures__/demo-journey.plato_cave.json";
import snapJson from "./__fixtures__/demo-snapshot.plato_cave.json";
import type { Return } from "./journeyLayout";
import type { Journey, Revision, Snapshot } from "./types";

/** A book with 86 passages (like The Time Machine): the fixture's nine plus 77 plain ones. */
function longSnapshot() {
  const extra = Array.from({ length: 77 }, (_, i) => ({ idx: 9 + i, text: `passage ${10 + i} text`, gist: null, processed: 1 }));
  return { ...snapJson, passages: [...snapJson.passages, ...extra], book: { ...snapJson.book, provenance: "model", model: "muse-spark-1.3" } };
}

function mock(routes: Record<string, unknown> = {}) {
  const snap = longSnapshot();
  const all: Record<string, unknown> = {
    "/api/books": [snap.book], "/api/books/plato_cave": snap, "/api/books/plato_cave/journey": journeyJson,
    "/api/books/plato_cave/connections?top=5": [], ...routes,
  };
  vi.stubGlobal("fetch", vi.fn(async (url: string) => (url in all ? new Response(JSON.stringify(all[url]), { status: 200 }) : new Response("nf", { status: 404 }))));
}

window.scrollTo = () => {};
afterEach(() => { cleanup(); vi.unstubAllGlobals(); window.history.replaceState(null, "", "/"); });

it("numbers passages with ordinary digits beyond 50, in the Weave and in the inspector", async () => {
  mock();
  window.history.replaceState(null, "", "/#p=86");
  render(<App />);
  const column = await screen.findByTestId("passage-85");
  expect(column.textContent).toContain("86");
  expect(column.textContent).not.toMatch(/X{3,}|LXXX/);
  const aside = document.querySelector("aside.inspector") as HTMLElement;
  expect(aside.textContent).toContain("Passage 86 of 86");
  expect(aside.textContent).not.toMatch(/\b[IVXL]{4,}\b/);
});

it("uses ordinary digits for passage numbers in a stage panel and keeps Roman numerals for the stages", async () => {
  mock();
  window.history.replaceState(null, "", "/#stage=1");
  render(<App />);
  const detail = await screen.findByTestId("stage-detail");
  expect(detail.textContent).toMatch(/Stage I\b/);          // stages keep their numerals
  expect(detail.textContent).toMatch(/[Pp]assages? \d+/);   // passages are numbers
  expect(detail.textContent).not.toMatch(/[Pp]assages? [IVX]+\b/);
});

it("shows the book's own chapter next to a passage when the book has a chapter map, and nothing otherwise", async () => {
  const chapters = { chapters: [{ number: 1, numeral: "I", title: "First" }, { number: 2, numeral: "II", title: "Second" }],
    passages: snapJson.passages.map((p) => ({ idx: p.idx, chapters: p.idx < 4 ? [{ number: 1, numeral: "I", title: "First" }] : [{ number: 1, numeral: "I", title: "First" }, { number: 2, numeral: "II", title: "Second" }] })) };
  mock({ "/api/books/plato_cave/chapters": chapters });
  window.history.replaceState(null, "", "/#p=6");
  render(<App />);
  const aside = await screen.findByText(/Passage 6 of 86/);
  await vi.waitFor(() => expect(document.querySelector("aside.inspector")!.textContent).toContain("ch. I–II"));
  expect(aside).toBeTruthy();
  cleanup();
  mock();   // no chapter map: no chapter text, and the page still works
  window.history.replaceState(null, "", "/#p=6");
  render(<App />);
  await screen.findByText(/Passage 6 of 86/);
  expect(document.querySelector("aside.inspector")!.textContent).not.toContain("ch.");
});

// ---------- progressive disclosure in the return panel ----------

function manyRevisions(n: number) {
  const snap = snapJson as unknown as Snapshot;
  const journey = journeyJson as unknown as Journey;
  const early = snap.units.filter((u) => u.introduced_at <= 1);
  const revisions = Array.from({ length: n }, (_, k): Revision => ({
    unit_id: early[k % early.length].id, passage: 2 + (k % 7), old_reading: "old", new_reading: `reading number ${k}`, rationale: "r",
    cause_unit: null, kind: "interpretive", source: "integration",
  }));
  const ret: Return = { from: 2, to: 0, revisions, relations: [], count: n };
  return { snap, journey, ret };
}

it("shows only the strongest few revised readings first and reveals all of them on request", () => {
  const { snap, journey, ret } = manyRevisions(10);
  render(<ReturnDetail snap={snap} journey={journey} ret={ret} openInWeave={() => {}} />);
  const list = screen.getByTestId("return-revisions");
  expect(within(list).getAllByRole("listitem")).toHaveLength(RETURN_PREVIEW);
  // longest reach first: the preview holds the readings made furthest from where the idea was first met
  const units = new Map(snap.units.map((u) => [u.id, u]));
  const reach = (v: Revision) => v.passage - units.get(v.unit_id)!.introduced_at;
  const best = [...ret.revisions].sort((a, b) => reach(b) - reach(a)).slice(0, RETURN_PREVIEW).map((v) => reach(v));
  const shownReach = within(list).getAllByRole("listitem").map((li) => reach(ret.revisions.find((v: Revision) => li.textContent!.includes(v.new_reading))!));
  expect(shownReach).toEqual(best);
  const button = screen.getByTestId("return-show-all");
  expect(button.textContent).toContain("Show all 10 revised readings");
  expect(button.getAttribute("aria-expanded")).toBe("false");
  fireEvent.click(button);
  expect(within(screen.getByTestId("return-revisions")).getAllByRole("listitem")).toHaveLength(10);   // nothing was dropped
  expect(screen.getByTestId("return-show-all").getAttribute("aria-expanded")).toBe("true");
  fireEvent.click(screen.getByTestId("return-show-all"));
  expect(within(screen.getByTestId("return-revisions")).getAllByRole("listitem")).toHaveLength(RETURN_PREVIEW);
});

it("needs no 'show all' control when a return has only a few items", () => {
  const { snap, journey, ret } = manyRevisions(2);
  render(<ReturnDetail snap={snap} journey={journey} ret={ret} openInWeave={() => {}} />);
  expect(within(screen.getByTestId("return-revisions")).getAllByRole("listitem")).toHaveLength(2);
  expect(screen.queryByTestId("return-show-all")).toBeNull();
});

// ---------- meanings the Journey does not draw ----------

function constructions(ids: string[]) {
  const [a, b] = snapJson.units.filter((u) => u.introduced_at <= 1 || u.introduced_at >= 6).slice(0, 2);
  return ids.map((id, k) => ({
    id, statement: `Meaning ${id} spanning ${k} passages.`, passage: 5, status: "established",
    contributors: [{ unit_id: a.id, role: "early" }, { unit_id: b.id, role: "late" }], relationship: "contrast", basis: "inferred",
    relation_to_existing: "new", related_to: null, justification: "They combine.", limitations: "l", model_confidence: 0.6, triggers: [],
    evidence: [{ unit_id: a.id, passage: 0, quote: a.evidence[0].quote }, { unit_id: b.id, passage: 1 + k, quote: b.evidence[0].quote }],
  }));
}

it("lists established meanings that are not drawn, widest reach first, and opens one with its evidence", async () => {
  const cs = constructions(["c1", "c2", "c3"]);
  const journey = { ...journeyJson, stages: journeyJson.stages.map((s, i) => (i === 0 ? { ...s, key_meanings: ["c1"] } : s)) };
  mock({ "/api/books/plato_cave": { ...longSnapshot(), constructions: cs }, "/api/books/plato_cave/journey": journey });
  render(<App />);
  await screen.findByTestId("journey-path");
  expect(screen.getByTestId("meaning-c1")).toBeTruthy();                       // the cited one is drawn
  expect(screen.queryByTestId("meaning-c2")).toBeNull();                       // the others are not
  const more = screen.getByTestId("more-meanings");
  expect(more.textContent).toContain("2 more woven meanings");
  const items = within(more).getAllByRole("button").map((b) => b.getAttribute("data-testid"));
  expect(items.slice(0, 2)).toEqual(["more-meaning-c3", "more-meaning-c2"]);   // c3 reaches furthest
  fireEvent.click(screen.getByTestId("more-meaning-c3"));
  const detail = screen.getByTestId("meaning-detail");
  expect(detail.textContent).toContain("Meaning c3 spanning 2 passages.");
  expect(detail.textContent).toContain(cs[2].evidence[0].quote);   // its original evidence, as for a drawn meaning
  expect(detail.textContent).toContain(cs[2].evidence[1].quote);
  expect(screen.getByTestId("more-meaning-c3").getAttribute("aria-pressed")).toBe("true");
});

it("shows no 'more meanings' list when the Journey already draws every established meaning", async () => {
  const cs = constructions(["c1"]);
  const journey = { ...journeyJson, stages: journeyJson.stages.map((s, i) => (i === 0 ? { ...s, key_meanings: ["c1"] } : s)) };
  mock({ "/api/books/plato_cave": { ...longSnapshot(), constructions: cs }, "/api/books/plato_cave/journey": journey });
  render(<App />);
  await screen.findByTestId("journey-path");
  expect(screen.queryByTestId("more-meanings")).toBeNull();
});

// ---------- finding a selected item in a very large Weave ----------

describe("bringIntoView", () => {
  const svgWith = (testid: string, rect: Partial<DOMRect>, wrap = { left: 0, right: 1000 }) => {
    const parent = document.createElement("div");
    parent.getBoundingClientRect = () => ({ left: wrap.left, right: wrap.right } as DOMRect);
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg") as unknown as SVGSVGElement;
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("data-testid", testid);
    g.getBoundingClientRect = () => ({ left: 0, right: 10, top: 0, bottom: 10, ...rect } as DOMRect);
    const spy = vi.fn();
    (g as unknown as { scrollIntoView: unknown }).scrollIntoView = spy;
    svg.appendChild(g); parent.appendChild(svg); document.body.appendChild(parent);
    return { svg, spy, parent };
  };

  it("centres a selected unit that is far off screen", () => {
    const { svg, spy, parent } = svgWith("unit-u1", { left: 6000, right: 6100, top: 4000, bottom: 4010 });
    expect(bringIntoView(svg, { kind: "unit", id: "u1" })).toBe(true);
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ block: "center", inline: "center" }));
    parent.remove();
  });

  it("does nothing when the selection is already in view", () => {
    const { svg, spy, parent } = svgWith("relation-r1", { left: 100, right: 300, top: 100, bottom: 200 });
    expect(bringIntoView(svg, { kind: "relation", id: "r1" })).toBe(false);
    expect(spy).not.toHaveBeenCalled();
    parent.remove();
  });

  it("only scrolls sideways for a passage column, which is as tall as the whole figure", () => {
    const { svg, spy, parent } = svgWith("passage-40", { left: 5000, right: 5110, top: -3000, bottom: 5000 });
    expect(bringIntoView(svg, { kind: "passage", idx: 40 })).toBe(true);
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ block: "nearest", inline: "center" }));
    parent.remove();
  });

  it("centres on a unit's own dot, not on a reinforcement marker further along its thread", () => {
    const { svg, spy, parent } = svgWith("unit-u9", { left: 100, right: 6000, top: 4000, bottom: 4010 });
    const g = svg.querySelector("g")!;
    const mk = (cls: string, left: number) => {
      const c = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      c.setAttribute("class", cls);
      const sp = vi.fn();
      (c as unknown as { scrollIntoView: unknown }).scrollIntoView = sp;
      c.getBoundingClientRect = () => ({ left, right: left + 6, top: 4000, bottom: 4006 } as DOMRect);
      return { c, sp };
    };
    const reinforced = mk("thread__reinforced", 5000);   // appears first in the DOM, as in the Loom
    const origin = mk("thread__origin thread__origin--observation", 120);
    g.appendChild(reinforced.c); g.appendChild(origin.c);
    expect(bringIntoView(svg, { kind: "unit", id: "u9" })).toBe(true);
    expect(origin.sp).toHaveBeenCalledWith(expect.objectContaining({ block: "center", inline: "center" }));
    expect(reinforced.sp).not.toHaveBeenCalled();
    expect(spy).not.toHaveBeenCalled();
    parent.remove();
  });

  it("is safe when the element is missing or nothing is selected", () => {
    const { svg, parent } = svgWith("unit-u1", {});
    expect(bringIntoView(svg, { kind: "unit", id: "nope" })).toBe(false);
    expect(bringIntoView(svg, null)).toBe(false);
    expect(bringIntoView(null, { kind: "unit", id: "u1" })).toBe(false);
    parent.remove();
  });
});

it("describes the passages a meaning draws on without writing a range for a single passage", () => {
  expect(passageSpan([83], 83)).toBe("passage 84");
  expect(passageSpan([16, 19, 73], 73)).toBe("passages 17–74");
  expect(passageSpan([], 4)).toBe("passage 5");
});

describe("chapter labels", () => {
  const I = { number: 1, numeral: "I", title: "One", start: 0, end: 1000 };
  const II = { number: 2, numeral: "II", title: "Two", start: 1000, end: 2000 };
  const map = { chapters: [I, II], passages: [{ idx: 0, start: 100, chapters: [I] }, { idx: 1, start: 900, chapters: [I, II] }, { idx: 2, start: 1100, chapters: [II] }] };
  const of = chapterLabeller(map);

  it("names a passage's chapter, or both chapters when it straddles a boundary", () => {
    expect(of(0)).toBe("I");
    expect(of(1)).toBe("I–II");
    expect(of(2)).toBe("II");
  });

  it("names the chapter of a quotation itself, not the passage's range", () => {
    expect(of(1, 50)).toBe("I");    // absolute offset 950: still chapter I
    expect(of(1, 150)).toBe("II");  // absolute offset 1050: chapter II
  });

  it("says nothing without a chapter map or for an unknown passage", () => {
    expect(chapterLabeller(null)(3)).toBe("");
    expect(of(99)).toBe("");
  });
});
