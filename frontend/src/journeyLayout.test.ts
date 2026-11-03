import { describe, expect, it } from "vitest";
import journeyJson from "./__fixtures__/demo-journey.plato_cave.json";
import snapJson from "./__fixtures__/demo-snapshot.plato_cave.json";
import { LABEL_GAP, LABEL_MIN, LANDMARK_GAP, MAX_RETURNS, ROSETTE_GAP, VIEW, buildLayout, formatPassages, placeLabels, type PathStage } from "./journeyLayout";
import type { Journey, Snapshot } from "./types";

const snap = snapJson as unknown as Snapshot;
const journey = journeyJson as unknown as Journey;

describe("woven Journey layout", () => {
  it("places each stage where it falls in the book, in order, within the margins", () => {
    const { stages, passages } = buildLayout(snap, journey);
    const span = VIEW.w - 2 * VIEW.margin;
    stages.forEach((s, i) => {
      expect(s.x0).toBeCloseTo(VIEW.margin + (journey.stages[i].first_passage / passages) * span);
      expect(s.x1).toBeCloseTo(VIEW.margin + ((journey.stages[i].last_passage + 1) / passages) * span);
      if (i > 0) expect(s.cx).toBeGreaterThan(stages[i - 1].cx);
    });
    expect(Math.max(...stages.map((s) => s.weight))).toBe(1);
  });

  it("is deterministic", () => {
    expect(JSON.stringify(buildLayout(snap, journey))).toEqual(JSON.stringify(buildLayout(snap, journey)));
  });

  it("draws no returns and no landmarks when MORe recorded none", () => {
    const bare = { ...snap, revisions: [], relations: snap.relations.filter((r) => r.type !== "REFRAMES" && r.type !== "CONTRADICTS"), constructions: [] };
    const l = buildLayout(bare, journey);
    expect(l.returns).toEqual([]);
    expect(l.landmarks).toEqual([]);
    expect(l.moves).toHaveLength(journey.stages.length - 1);
  });

  it("ignores state updates and caps the number of returns", () => {
    const states = snap.revisions.map((v) => ({ ...v, kind: "state" as const }));
    const noReframes = snap.relations.filter((r) => r.type !== "REFRAMES" && r.type !== "CONTRADICTS");
    expect(buildLayout({ ...snap, revisions: states, relations: noReframes }, journey).returns).toEqual([]);
    expect(buildLayout(snap, journey).returns.length).toBeLessThanOrEqual(MAX_RETURNS);
  });

  it("shows only established, cited meanings, and marks threads added by later reinforcement", () => {
    const last = journey.stages.length - 1;
    const u0 = snap.units.find((u) => u.introduced_at === 0)!;
    const uLast = snap.units.find((u) => u.introduced_at >= journey.stages[last].first_passage)!;
    const base = { statement: "s", passage: journey.stages[last].first_passage, relationship: "r", basis: "inferred" as const,
      relation_to_existing: "new" as const, related_to: null, justification: "j", limitations: "l", model_confidence: 0.5, triggers: [],
      evidence: [{ unit_id: u0.id, passage: 0, quote: "q" }, { unit_id: uLast.id, passage: uLast.introduced_at, quote: "q" }] };
    const constructions = [
      { ...base, id: "ok", contributors: [{ unit_id: uLast.id, role: "a" }, { unit_id: u0.id, role: "b", added_at: 7 }] },
      { ...base, id: "pending", status: "pending" as const, contributors: [{ unit_id: uLast.id, role: "a" }, { unit_id: u0.id, role: "b" }] },
      { ...base, id: "uncited", contributors: [{ unit_id: uLast.id, role: "a" }, { unit_id: u0.id, role: "b" }] },
    ];
    const j = { ...journey, stages: journey.stages.map((s, i) => (i === last ? { ...s, key_meanings: ["ok", "pending", "missing"] } : s)) };
    const { landmarks } = buildLayout({ ...snap, constructions }, j);
    expect(landmarks.map((l) => l.construction.id)).toEqual(["ok"]);
    expect(landmarks[0].stage).toBe(last);
    expect(landmarks[0].sources).toEqual([{ stage: 0, reinforcement: true }, { stage: last, reinforcement: false }]);
    expect(landmarks[0].passages).toEqual([0, uLast.introduced_at]);
  });

  it("keeps landmarks apart and in order, within the margins", () => {
    const { landmarks } = layoutWithLandmarks(["a", "b", "c", "d"]);
    expectPacked(landmarks);
  });

  it("packs many landmarks (a long book) without any two captions colliding", () => {
    const ids = Array.from({ length: 12 }, (_, i) => `m${i}`);
    const { landmarks } = layoutWithLandmarks(ids);
    expect(landmarks).toHaveLength(12);
    expectPacked(landmarks);
    expect(new Set(landmarks.map((l) => l.captionRow))).toEqual(new Set([0, 1])); // the second row is used when needed
    // every landmark is still there and in the order the Journey cited them
    expect(landmarks.map((l) => l.construction.id)).toEqual(ids);
  });

  it("keeps every stage title readable and clear of its neighbours, even when a stage covers few passages", () => {
    // The Time Machine: five stages over 86 passages (9, 7, 20, 39 and 11 passages)
    const spans = [[0, 8], [9, 15], [16, 35], [36, 74], [75, 85]];
    const span = VIEW.w - 2 * VIEW.margin;
    const stages = spans.map(([a, b], i) => {
      const x0 = VIEW.margin + (a / 86) * span; const x1 = VIEW.margin + ((b + 1) / 86) * span;
      return { index: i, first: a, last: b, x0, x1, cx: (x0 + x1) / 2, labelLeft: 0, labelWidth: 0, weight: 1, r: 8 } as PathStage;
    });
    const knots = stages.map((s) => s.cx);
    placeLabels(stages);
    stages.forEach((s, i) => {
      expect(s.labelWidth).toBeGreaterThanOrEqual(LABEL_MIN);
      expect(s.labelLeft).toBeGreaterThanOrEqual(10 - 1e-9);
      expect(s.labelLeft + s.labelWidth).toBeLessThanOrEqual(VIEW.w - 10 + 1e-9);
      if (i) expect(s.labelLeft - (stages[i - 1].labelLeft + stages[i - 1].labelWidth)).toBeGreaterThanOrEqual(LABEL_GAP - 1e-9);
      expect(s.cx).toBe(knots[i]); // the knot never moves: only the title box does
    });
  });

  it("names passages exactly, in ordinary numbers, compressing only consecutive runs", () => {
    expect(formatPassages([0, 1, 2, 3])).toBe("passages 1–4");
    expect(formatPassages([2, 5])).toBe("passages 3, 6");
    expect(formatPassages([2, 3, 5])).toBe("passages 3–4, 6");
    expect(formatPassages([3])).toBe("passage 4");
  });

  it("names passages correctly beyond 50 (a long book), never in strings of Xs", () => {
    expect(formatPassages([85])).toBe("passage 86");
    expect(formatPassages([49, 50, 51])).toBe("passages 50–52");
    expect(formatPassages([14, 15, 76, 77, 85])).toBe("passages 15–16, 77–78, 86");
    for (let p = 0; p < 200; p++) expect(formatPassages([p])).toBe(`passage ${p + 1}`);
  });

  it("abbreviates a long list of runs for captions but not otherwise", () => {
    expect(formatPassages([4, 6, 8, 12], String, 2)).toBe("passages 5 … 13");
    expect(formatPassages([4, 6, 8, 12], String, 3)).toBe("passages 5, 7 … 13");
    expect(formatPassages([14, 15, 76, 77], String, 2)).toBe("passages 15–16, 77–78");
    expect(formatPassages([4, 6, 8, 12])).toBe("passages 5, 7, 9, 13");
  });
});

function layoutWithLandmarks(ids: string[]) {
  const last = journey.stages.length - 1;
  const u = snap.units.filter((x) => x.introduced_at >= journey.stages[last].first_passage).slice(0, 2);
  const mk = (id: string) => ({ id, statement: "s", passage: journey.stages[last].first_passage, relationship: "r",
    basis: "inferred" as const, relation_to_existing: "new" as const, related_to: null, justification: "j", limitations: "l",
    model_confidence: 0.5, triggers: [], evidence: [], contributors: u.map((x) => ({ unit_id: x.id, role: "r" })) });
  const j = { ...journey, stages: journey.stages.map((s, i) => (i === last ? { ...s, key_meanings: ids } : s)) };
  return buildLayout({ ...snap, constructions: ids.map(mk) }, j);
}

function expectPacked(landmarks: { x: number; captionRow: 0 | 1 }[]) {
  const xs = landmarks.map((l) => l.x);
  xs.slice(1).forEach((x, i) => expect(x - xs[i]).toBeGreaterThanOrEqual(ROSETTE_GAP - 1e-6));
  for (const row of [0, 1] as const) {
    const rx = landmarks.filter((l) => l.captionRow === row).map((l) => l.x);
    rx.slice(1).forEach((x, i) => expect(x - rx[i]).toBeGreaterThanOrEqual(LANDMARK_GAP - 1e-6));
  }
  expect(xs[xs.length - 1]).toBeLessThanOrEqual(VIEW.w - VIEW.margin + 1e-6);
  expect(xs[0]).toBeGreaterThanOrEqual(0);
}
