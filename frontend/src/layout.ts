import type { Relation, Snapshot, Unit } from "./types";

// Pure layout of the "loom": passages are columns read left to right; each unit is a thread
// that starts where the unit is first perceived and runs to the last passage that touches it.
// A relation is a knot tied at the passage where integration formed it, joining the two threads.

export interface LayoutOptions {
  colWidth: number;
  rowHeight: number;
  groupGap: number;
  left: number;
  top: number;
}

// Labels sit to the LEFT of each thread's origin; knots bulge to the RIGHT of their column.
// Knots at passage p only span rows of units introduced at or before p, and labels at those rows
// lie left of their own origin, so loops and labels never collide. `left` leaves room for column I labels.
export const DEFAULT_LAYOUT: LayoutOptions = { colWidth: 110, rowHeight: 16, groupGap: 10, left: 178, top: 18 };

export interface ThreadLayout {
  unit: Unit;
  y: number;
  x0: number; // origin node
  x1: number; // thread end
  end: number; // passage index where the thread ends
  reinforcedAt: number[]; // passages that added evidence (merges)
  revisedAt: number[];
}

export interface KnotLayout {
  relation: Relation;
  path: string;
  x: number;
  ySource: number;
  yTarget: number;
  crossPassage: boolean;
  span: number; // passages between the earlier unit's origin and the knot
  earlierId: string;
}

export interface LoomLayout {
  width: number;
  height: number;
  columnX: (i: number) => number;
  threads: Map<string, ThreadLayout>;
  knots: KnotLayout[];
}

export function layoutLoom(snap: Snapshot, opt: LayoutOptions = DEFAULT_LAYOUT): LoomLayout {
  const nPassages = snap.passages.length;
  const columnX = (i: number) => opt.left + i * opt.colWidth;
  const units = [...snap.units].sort((a, b) => a.introduced_at - b.introduced_at || idOrder(a.id, b.id));

  // How far each thread runs: the last passage where the unit is reinforced, related or revised.
  const end = new Map<string, number>(units.map((u) => [u.id, u.last_active_at]));
  for (const r of snap.relations) {
    for (const id of [r.source, r.target]) end.set(id, Math.max(end.get(id) ?? 0, r.created_at));
  }
  for (const rv of snap.revisions) end.set(rv.unit_id, Math.max(end.get(rv.unit_id) ?? 0, rv.passage));

  const threads = new Map<string, ThreadLayout>();
  let y = opt.top;
  let group = units[0]?.introduced_at ?? 0;
  for (const u of units) {
    if (u.introduced_at !== group) {
      y += opt.groupGap;
      group = u.introduced_at;
    }
    const e = end.get(u.id) ?? u.introduced_at;
    threads.set(u.id, {
      unit: u,
      y,
      x0: columnX(u.introduced_at),
      x1: columnX(e),
      end: e,
      reinforcedAt: [...new Set(u.evidence.map((ev) => ev.passage).filter((p) => p > u.introduced_at))],
      revisedAt: snap.revisions.filter((r) => r.unit_id === u.id).map((r) => r.passage),
    });
    y += opt.rowHeight;
  }

  const knots: KnotLayout[] = [];
  const perColumn = new Map<number, number>();
  for (const r of snap.relations) {
    const s = threads.get(r.source);
    const t = threads.get(r.target);
    if (!s || !t) continue;
    const earlier = s.unit.introduced_at <= t.unit.introduced_at ? s : t;
    const k = perColumn.get(r.created_at) ?? 0;
    perColumn.set(r.created_at, k + 1);
    // Knots in the same column fan out slightly so they don't sit on top of each other.
    const x = columnX(r.created_at) + 4 + (k % 4) * 3;
    const dy = Math.abs(s.y - t.y);
    const bulge = Math.min(opt.colWidth * 0.55, 10 + dy * 0.18);
    knots.push({
      relation: r,
      path: `M ${x} ${s.y} C ${x + bulge} ${s.y}, ${x + bulge} ${t.y}, ${x} ${t.y}`,
      x,
      ySource: s.y,
      yTarget: t.y,
      crossPassage: earlier.unit.introduced_at < r.created_at,
      span: r.created_at - earlier.unit.introduced_at,
      earlierId: earlier.unit.id,
    });
  }

  return {
    width: opt.left + (nPassages - 1) * opt.colWidth + opt.colWidth * 0.75,
    height: y + opt.top,
    columnX,
    threads,
    knots,
  };
}

function idOrder(a: string, b: string): number {
  // Unit ids look like u05_3: passage 5, third unit added in that passage.
  return Number(a.split("_")[1] ?? 0) - Number(b.split("_")[1] ?? 0);
}

/** Top-k passages by change score: candidate turning points, derived only from the data. */
export function turningPoints(snap: Snapshot, k = 3): Set<number> {
  const ranked = snap.changes.filter((c) => c.processed).sort((a, b) => b.change_score - a.change_score);
  return new Set(ranked.slice(0, k).map((c) => c.passage));
}
