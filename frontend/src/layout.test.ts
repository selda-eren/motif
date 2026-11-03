import snapJson from "./__fixtures__/demo-snapshot.plato_cave.json";
import { layoutLoom, turningPoints } from "./layout";
import type { Snapshot } from "./types";

const snap = snapJson as unknown as Snapshot;

describe("layoutLoom", () => {
  const layout = layoutLoom(snap);

  it("lays out one thread per unit, in reading order", () => {
    expect(layout.threads.size).toBe(snap.units.length);
    const threads = [...layout.threads.values()];
    for (let i = 1; i < threads.length; i++) {
      expect(threads[i].y).toBeGreaterThan(threads[i - 1].y);
      expect(threads[i].unit.introduced_at).toBeGreaterThanOrEqual(threads[i - 1].unit.introduced_at);
    }
  });

  it("extends each thread to every passage where it is related or revised", () => {
    for (const r of snap.relations) {
      for (const id of [r.source, r.target]) expect(layout.threads.get(id)!.end).toBeGreaterThanOrEqual(r.created_at);
    }
    for (const rv of snap.revisions) expect(layout.threads.get(rv.unit_id)!.revisedAt).toContain(rv.passage);
  });

  it("ties every relation at the passage where it formed, with finite geometry", () => {
    expect(layout.knots).toHaveLength(snap.relations.length);
    for (const k of layout.knots) {
      expect(k.path).not.toMatch(/NaN|undefined/);
      expect(k.x).toBeGreaterThanOrEqual(layout.columnX(k.relation.created_at));
      expect(k.x).toBeLessThan(layout.columnX(k.relation.created_at + 1));
    }
  });

  it("measures how far back a cross-passage link reaches", () => {
    const k = layout.knots.find((x) => x.relation.id === "r05_2")!; // turning the soul -> chains (demo)
    expect(k.crossPassage).toBe(true);
    expect(k.span).toBe(5);
    expect(k.earlierId).toBe("u00_6");
  });
});

it("derives turning points from change scores only", () => {
  const top = [...snap.changes].sort((a, b) => b.change_score - a.change_score).slice(0, 3).map((c) => c.passage);
  expect([...turningPoints(snap)].sort()).toEqual(top.sort());
});
