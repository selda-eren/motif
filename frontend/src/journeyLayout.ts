// Deterministic layout for the woven Journey view. Pure functions of the stored Journey and MORe snapshot:
// nothing here invents a stage, a move, a return or a convergence. See docs/design/journey-visual.md.
import type { Construction, Journey, Relation, Revision, Snapshot, TransitionExplanation, TransitionKind, Unit } from "./types";

export const VIEW = { w: 1000, h: 356, margin: 46, threadY: 150, meaningY: 264, titleBottom: 64 };
export const MAX_RETURNS = 6;
export const LANDMARK_GAP = 112; // minimum distance between two captions in the same row, so they never collide
export const ROSETTE_GAP = 36; // minimum distance between any two rosettes
export const LABEL_MIN = 150; // stage titles get at least this much width (a stage of seven passages is narrow)
export const LABEL_MAX = 230;
export const LABEL_GAP = 10;

export interface PathStage {
  index: number;
  first: number;
  last: number;
  x0: number; // where the stage begins in the book
  x1: number; // where it ends
  cx: number; // its knot
  labelLeft: number; // the stage title's box: wide enough to read, kept clear of its neighbours
  labelWidth: number;
  weight: number; // 0..1: the stage's share of change, relative to the stage with the most
  r: number;
}

export interface PathMove {
  from: number;
  to: number;
  x1: number;
  x2: number;
  kind: TransitionKind | null; // null: the Journey has no explanation layer
  tentative: boolean;
  transition?: TransitionExplanation;
}

/** A later stage rereading or reframing ideas first met in an earlier stage. */
export interface Return {
  from: number; // the later stage
  to: number; // the earlier stage
  revisions: Revision[]; // interpretive revisions made in `from` of units first met in `to`
  relations: Relation[]; // REFRAMES / CONTRADICTS links formed in `from` that reach back to `to`
  count: number;
}

/** An established constructed meaning cited by a stage, with the stages its contributors come from. */
export interface Landmark {
  construction: Construction;
  stage: number;
  x: number;
  captionRow: 0 | 1; // captions alternate between two rows when meanings are closer than a caption is wide
  sources: { stage: number; reinforcement: boolean }[];
  passages: number[]; // the distinct passages its evidence comes from, in order
}

export interface JourneyLayout {
  passages: number;
  stages: PathStage[];
  moves: PathMove[];
  returns: Return[];
  landmarks: Landmark[];
}

export const isEstablished = (c: Construction) => (c.status ?? "established") === "established";

export function stageOf(journey: Journey, passage: number): number {
  const i = journey.stages.findIndex((s) => s.first_passage <= passage && passage <= s.last_passage);
  return i < 0 ? (passage < journey.stages[0].first_passage ? 0 : journey.stages.length - 1) : i;
}

export function buildLayout(snap: Snapshot, journey: Journey): JourneyLayout {
  const n = Math.max(1, snap.passages.length);
  const span = VIEW.w - 2 * VIEW.margin;
  const xAt = (p: number) => VIEW.margin + (p / n) * span;
  const units = new Map<string, Unit>(snap.units.map((u) => [u.id, u]));
  const score = new Map<number, number>(snap.changes.map((c) => [c.passage, c.change_score]));

  const raw = journey.stages.map((s) => {
    let total = 0;
    for (let p = s.first_passage; p <= s.last_passage; p++) total += score.get(p) ?? 0;
    return total;
  });
  const top = Math.max(1e-9, ...raw);
  const stages: PathStage[] = journey.stages.map((s, i) => {
    const x0 = xAt(s.first_passage);
    const x1 = xAt(s.last_passage + 1);
    const weight = raw[i] / top;
    return { index: i, first: s.first_passage, last: s.last_passage, x0, x1, cx: (x0 + x1) / 2, labelLeft: 0, labelWidth: 0, weight, r: 6 + 6 * weight };
  });
  placeLabels(stages);

  const moves: PathMove[] = stages.slice(0, -1).map((s, i) => {
    const t = journey.explanation?.transitions.find((x) => x.from_index === i);
    return { from: i, to: i + 1, x1: s.cx, x2: stages[i + 1].cx, kind: t?.kind ?? null,
             tentative: t?.certainty === "tentative", transition: t };
  });

  // Returns: grouped by (later stage, earlier stage); only what MORe recorded.
  const groups = new Map<string, Return>();
  const group = (from: number, to: number) => {
    const key = `${from}-${to}`;
    if (!groups.has(key)) groups.set(key, { from, to, revisions: [], relations: [], count: 0 });
    return groups.get(key)!;
  };
  for (const v of snap.revisions) {
    const u = units.get(v.unit_id);
    if (!u || (v.kind ?? "interpretive") !== "interpretive") continue;
    const a = stageOf(journey, u.introduced_at);
    const b = stageOf(journey, v.passage);
    if (a < b) group(b, a).revisions.push(v);
  }
  for (const r of snap.relations) {
    if (r.type !== "REFRAMES" && r.type !== "CONTRADICTS") continue;
    const s = units.get(r.source);
    const t = units.get(r.target);
    if (!s || !t) continue;
    const [a, b] = [stageOf(journey, s.introduced_at), stageOf(journey, t.introduced_at)].sort((x, y) => x - y);
    if (a < b) group(b, a).relations.push(r);
  }
  const returns = [...groups.values()]
    .map((g) => ({ ...g, count: g.revisions.length + g.relations.length }))
    .sort((x, y) => y.count - x.count || x.from - y.from || x.to - y.to)
    .slice(0, MAX_RETURNS);

  // Landmarks: established constructed meanings that the Journey cites for a stage.
  const byId = new Map((snap.constructions ?? []).map((c) => [c.id, c]));
  const landmarks: Landmark[] = [];
  journey.stages.forEach((s, i) => {
    const cited = (s.key_meanings ?? []).map((id) => byId.get(id)).filter((c): c is Construction => !!c && isEstablished(c));
    const st = stages[i];
    const step = Math.min(78, (st.x1 - st.x0) / Math.max(1, cited.length));
    cited.forEach((c, j) => {
      const bySource = new Map<number, boolean>();
      for (const x of c.contributors) {
        const u = units.get(x.unit_id);
        if (!u) continue;
        const from = stageOf(journey, u.introduced_at);
        const later = x.added_at !== null && x.added_at !== undefined;
        bySource.set(from, (bySource.get(from) ?? true) && later);
      }
      const ps = [...new Set(c.evidence.map((e) => e.passage))].sort((a, b) => a - b);
      landmarks.push({
        construction: c, stage: i, x: st.cx + (j - (cited.length - 1) / 2) * step, captionRow: 0,
        sources: [...bySource.entries()].sort((a, b) => a[0] - b[0]).map(([stage, reinforcement]) => ({ stage, reinforcement })),
        passages: ps.length ? ps : [c.passage],
      });
    });
  });

  spaceOut(landmarks);
  return { passages: n, stages, moves, returns, landmarks };
}

/** Stage titles: each gets a box of at least LABEL_MIN around its knot, shifted sideways just enough that no two
 *  boxes touch and none leaves the figure. Only the box moves; the knot and its tether stay where the data puts them. */
export function placeLabels(stages: PathStage[]): void {
  const lo = 10;
  const hi = VIEW.w - 10;
  const ws = stages.map((s) => Math.min(LABEL_MAX, Math.max(LABEL_MIN, s.x1 - s.x0)));
  const left = stages.map((s, i) => s.cx - ws[i] / 2);
  for (let i = 0; i < left.length; i++) {
    left[i] = Math.max(left[i], lo, i ? left[i - 1] + ws[i - 1] + LABEL_GAP : lo);
  }
  const overflow = left.length ? left[left.length - 1] + ws[ws.length - 1] - hi : 0;
  if (overflow > 0) left[left.length - 1] -= overflow;
  for (let i = left.length - 2; i >= 0; i--) left[i] = Math.min(left[i], left[i + 1] - LABEL_GAP - ws[i]);
  stages.forEach((s, i) => { s.labelLeft = left[i]; s.labelWidth = ws[i]; });
}

/** Place landmarks left to right, no closer than ROSETTE_GAP, putting each caption in whichever of two rows keeps it
 *  at least LANDMARK_GAP from the previous caption in that row. Order and data are untouched; only x and the row change. */
function spaceOut(ls: Landmark[]): void {
  const sorted = [...ls].sort((a, b) => a.x - b.x);
  const place = (list: Landmark[], fromRight: boolean) => {
    const order = fromRight ? [...list].reverse() : list;
    const dir = fromRight ? -1 : 1;
    const last: [number, number] = [-Infinity * dir, -Infinity * dir];
    let prev = -Infinity * dir;
    for (const l of order) {
      const want = (row: 0 | 1) => (fromRight ? Math.min(l.x, last[row] - LANDMARK_GAP, prev - ROSETTE_GAP) : Math.max(l.x, last[row] + LANDMARK_GAP, prev + ROSETTE_GAP));
      const x0 = want(0);
      const x1 = want(1);
      const useRow1 = fromRight ? x1 > x0 : x1 < x0;
      l.captionRow = useRow1 ? 1 : 0;
      l.x = useRow1 ? x1 : x0;
      last[l.captionRow] = l.x;
      prev = l.x;
    }
  };
  place(sorted, false);
  const right = VIEW.w - VIEW.margin;
  const overflow = sorted.length ? sorted[sorted.length - 1].x - right : 0;
  if (overflow > 0) {
    for (const l of sorted) l.x -= overflow;
    place(sorted, true);
  }
}

/** Passage numbers as ordinary digits (1-based), compressing only consecutive runs: [0,1,2,3] -> "passages 1–4",
 *  [2,5] -> "passages 3, 6". With maxRuns, a long list is abbreviated to its first runs and its last: "passages 5, 7 … 13". */
export function formatPassages(ps: number[], num: (n: number) => string = String, maxRuns = Infinity): string {
  const runs: [number, number][] = [];
  for (const p of ps) {
    const last = runs[runs.length - 1];
    if (last && p === last[1] + 1) last[1] = p;
    else runs.push([p, p]);
  }
  const fmt = ([a, b]: [number, number]) => (a === b ? num(a + 1) : `${num(a + 1)}–${num(b + 1)}`);
  const shown = runs.length > maxRuns ? `${runs.slice(0, maxRuns - 1).map(fmt).join(", ")} … ${fmt(runs[runs.length - 1])}` : runs.map(fmt).join(", ");
  return `${ps.length === 1 ? "passage" : "passages"} ${shown}`;
}

// ---------- path geometry (SVG "d" strings) ----------

const Y = VIEW.threadY;

/** The main thread between two knots: a gentle wave, alternating up and down. */
export function movePath(m: PathMove, offset = 0): string {
  const dy = m.from % 2 === 0 ? -10 : 10;
  const a = m.x1 + (m.x2 - m.x1) / 3;
  const b = m.x1 + (2 * (m.x2 - m.x1)) / 3;
  return `M ${m.x1} ${Y + offset} C ${a} ${Y + dy + offset}, ${b} ${Y - dy + offset}, ${m.x2} ${Y + offset}`;
}

/** Two strands that cross half-way: a challenge or contrast. */
export function crossingPaths(m: PathMove): [string, string] {
  const mx = (m.x1 + m.x2) / 2;
  return [
    `M ${m.x1} ${Y - 5} C ${mx - 20} ${Y - 5}, ${mx - 10} ${Y + 6}, ${mx} ${Y} S ${m.x2 - 20} ${Y + 5}, ${m.x2} ${Y + 5}`,
    `M ${m.x1} ${Y + 5} C ${mx - 20} ${Y + 5}, ${mx - 10} ${Y - 6}, ${mx} ${Y} S ${m.x2 - 20} ${Y - 5}, ${m.x2} ${Y - 5}`,
  ];
}

/** A small loop where the thread turns back on itself: a reinterpretation. */
export function loopPath(m: PathMove): string {
  const mx = (m.x1 + m.x2) / 2;
  return `M ${mx - 16} ${Y} C ${mx + 12} ${Y}, ${mx + 13} ${Y - 26}, ${mx} ${Y - 26} C ${mx - 13} ${Y - 26}, ${mx - 12} ${Y}, ${mx + 16} ${Y}`;
}

/** A small chevron pointing onward: a consequence. */
export function chevronPath(m: PathMove): string {
  const mx = (m.x1 + m.x2) / 2;
  return `M ${mx - 5} ${Y - 7} L ${mx + 4} ${Y} L ${mx - 5} ${Y + 7}`;
}

/** Arcs rise with the distance they reach back, staying below the stage titles. */
function arcHeight(r: Return, a: number, b: number): number {
  return Math.min(Y - VIEW.titleBottom - 6, 36 + 22 * (r.from - r.to - 1) + Math.abs(b - a) * 0.07);
}

/** An arc from a later knot back to an earlier one, above the thread. */
export function returnPath(r: Return, stages: PathStage[]): string {
  const a = stages[r.to].cx;
  const b = stages[r.from].cx;
  const h = arcHeight(r, a, b);
  return `M ${b} ${Y - stages[r.from].r} C ${b} ${Y - h}, ${a} ${Y - h}, ${a} ${Y - stages[r.to].r - 3}`;
}

/** The apex of a return arc, for its label. */
export function returnApex(r: Return, stages: PathStage[]): { x: number; y: number } {
  const a = stages[r.to].cx;
  const b = stages[r.from].cx;
  return { x: (a + b) / 2, y: Y - 0.75 * arcHeight(r, a, b) };
}

/** A thread from a contributing stage's knot down to a landmark below. */
export function convergencePath(sourceX: number, l: Landmark, r: number): string {
  const ly = VIEW.meaningY - 13;
  return `M ${sourceX} ${Y + r} C ${sourceX} ${Y + 70}, ${l.x} ${ly - 60}, ${l.x} ${ly}`;
}

/** A small lace rosette: six petals around a centre. */
export function rosettePath(x: number, y: number, r = 11): string {
  const petals: string[] = [];
  for (let k = 0; k < 6; k++) {
    const t = (Math.PI / 3) * k;
    const px = x + Math.cos(t) * r * 0.62;
    const py = y + Math.sin(t) * r * 0.62;
    petals.push(`M ${x} ${y} Q ${px + Math.cos(t + 1) * r * 0.55} ${py + Math.sin(t + 1) * r * 0.55}, ${x + Math.cos(t) * r} ${y + Math.sin(t) * r} Q ${px + Math.cos(t - 1) * r * 0.55} ${py + Math.sin(t - 1) * r * 0.55}, ${x} ${y}`);
  }
  return petals.join(" ");
}
