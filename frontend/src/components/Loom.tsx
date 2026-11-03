import { useEffect, useMemo, useRef, useState } from "react";
import { layoutLoom, turningPoints, type KnotLayout } from "../layout";
import type { RelationType, Selection, Snapshot } from "../types";
import { RELATION_STYLE } from "../vocab";

const HEADER = 74;

/** In a large representation the selected item may be far off screen (the Time Machine's Weave is ~9,600 px wide).
 *  Bring it into view, centred, when a selection is made from elsewhere (e.g. "open in The Weave"); do nothing if it is visible. */
export function bringIntoView(svg: SVGSVGElement | null, selection: Selection): boolean {
  if (!svg || !selection) return false;
  const id = selection.kind === "unit" ? `unit-${selection.id}` : selection.kind === "relation" ? `relation-${selection.id}` : `passage-${selection.idx}`;
  const el = [...svg.querySelectorAll("[data-testid]")].find((e) => e.getAttribute("data-testid") === id);
  if (!el) return false;
  // A thread or a loop is as long as the distance it spans: centre on its marker (a unit's first dot, a relation's first end), not its middle.
  // For a unit that is its own dot (`.thread__origin`: reinforcements and revisions are further along the thread).
  const target = (selection.kind === "passage" ? el : el.querySelector(".thread__origin") ?? el.querySelector("circle") ?? el) as Element;
  if (typeof target.scrollIntoView !== "function") return false;
  const r = target.getBoundingClientRect();
  const wrap = svg.parentElement?.getBoundingClientRect();
  const inX = !wrap || (r.left >= wrap.left && r.right <= wrap.right);
  const inY = r.top >= 0 && r.bottom <= window.innerHeight;
  if (inX && inY) return false;
  const reduce = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // A passage column is as tall as the whole figure: only bring it into view sideways.
  target.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: selection.kind === "passage" ? "nearest" : "center", inline: "center" });
  return true;
}

const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

interface Props {
  snap: Snapshot;
  selection: Selection;
  onSelect: (s: Selection) => void;
  visibleTypes: Set<RelationType>;
  showWithinPassage: boolean;
}

export function Loom({ snap, selection, onSelect, visibleTypes, showWithinPassage }: Props) {
  const layout = useMemo(() => layoutLoom(snap), [snap]);
  const turns = useMemo(() => turningPoints(snap), [snap]);
  const [hoverUnit, setHoverUnit] = useState<string | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  useEffect(() => { bringIntoView(svgRef.current, selection); }, [selection]);
  const maxScore = Math.max(1, ...snap.changes.map((c) => c.change_score));

  const knots = layout.knots.filter(
    (k) => visibleTypes.has(k.relation.type) && (showWithinPassage || k.crossPassage),
  );

  // What is "in focus": a selected relation, or a selected/hovered unit and its relations.
  const focusUnit = hoverUnit ?? (selection?.kind === "unit" ? selection.id : null);
  const focusRel = selection?.kind === "relation" ? selection.id : null;
  const knotActive = (k: KnotLayout) =>
    focusRel ? k.relation.id === focusRel : focusUnit ? k.relation.source === focusUnit || k.relation.target === focusUnit : false;
  const anyFocus = Boolean(focusRel || focusUnit);
  const activeKnots = knots.filter(knotActive);
  const activeUnits = new Set<string>(activeKnots.flatMap((k) => [k.relation.source, k.relation.target]));
  if (focusUnit) activeUnits.add(focusUnit);
  const selectedPassage = selection?.kind === "passage" ? selection.idx : null;

  return (
    <svg
      ref={svgRef}
      className="loom"
      width={layout.width}
      height={layout.height + HEADER}
      role="img"
      aria-label={`Journey of ideas through ${snap.passages.length} passages`}
    >
      {/* Passage columns: ruled like a manuscript page */}
      {snap.passages.map((p) => {
        const x = layout.columnX(p.idx);
        const change = snap.changes.find((c) => c.passage === p.idx);
        const score = change?.change_score ?? 0;
        const isTurn = turns.has(p.idx);
        return (
          <g
            key={p.idx}
            className={`column${selectedPassage === p.idx ? " column--selected" : ""}`}
            onClick={() => onSelect({ kind: "passage", idx: p.idx })}
            data-testid={`passage-${p.idx}`}
          >
            <title>{`Passage ${p.idx + 1}: ${p.gist ?? "(not processed)"}`}</title>
            <rect x={x - 12} y={0} width={110} height={layout.height + HEADER} className="column__band" />
            <line x1={x} x2={x} y1={HEADER - 8} y2={layout.height + HEADER} className="column__rule" />
            <text x={x - 6} y={22} className="column__numeral">
              {isTurn ? "❦ " : ""}
              {p.idx + 1}
            </text>
            <rect x={x - 6} y={34} width={(score / maxScore) * 96} height={3} className="column__change" />
            <text x={x - 6} y={52} className="column__caption">
              {isTurn ? "turning point" : `${change?.cross_passage_relations.length ?? 0} links back`}
            </text>
          </g>
        );
      })}

      <g transform={`translate(0, ${HEADER})`}>
        {/* Threads */}
        {[...layout.threads.values()].map((t) => {
          const dim = anyFocus && !activeUnits.has(t.unit.id);
          const selected = selection?.kind === "unit" && selection.id === t.unit.id;
          return (
            <g
              key={t.unit.id}
              className={`thread${dim ? " is-dim" : ""}${selected ? " is-selected" : ""}`}
              onMouseEnter={() => setHoverUnit(t.unit.id)}
              onMouseLeave={() => setHoverUnit(null)}
              onClick={() => onSelect({ kind: "unit", id: t.unit.id })}
              data-testid={`unit-${t.unit.id}`}
            >
              <title>{`${t.unit.label} (${t.unit.layer === "observation" ? "observation" : "inferred"}): ${t.unit.content}`}</title>
              <line x1={t.x0} x2={Math.max(t.x1, t.x0)} y1={t.y} y2={t.y} className="thread__line" />
              {t.reinforcedAt.map((p) => (
                <circle key={`r${p}`} cx={layout.columnX(p)} cy={t.y} r={2.2} className="thread__reinforced">
                  <title>Restated in passage {p + 1}</title>
                </circle>
              ))}
              {t.revisedAt.map((p) => (
                <g key={`v${p}`} className="thread__revised">
                  <circle cx={layout.columnX(p)} cy={t.y} r={4.6} />
                  <circle cx={layout.columnX(p)} cy={t.y} r={1.4} className="dot" />
                  <title>Reading revised in passage {p + 1}</title>
                </g>
              ))}
              <circle
                cx={t.x0}
                cy={t.y}
                r={3.6}
                className={`thread__origin thread__origin--${t.unit.layer}${t.unit.status === "contested" ? " is-contested" : ""}`}
              />
              <text x={t.x0 - 8} y={t.y + 3.5} textAnchor="end" className="thread__label">
                {truncate(t.unit.label, 30)}
              </text>
              <rect x={t.x0 - 170} y={t.y - 7} width={Math.max(t.x1 - t.x0, 0) + 175} height={14} className="hit" />
            </g>
          );
        })}

        {/* Knots: relations formed during integration, drawn at the passage where they formed */}
        {knots.map((k) => {
          const st = RELATION_STYLE[k.relation.type];
          const active = knotActive(k);
          const earlier = layout.threads.get(k.earlierId)!;
          return (
            <g
              key={k.relation.id}
              className={`knot${anyFocus && !active ? " is-dim" : ""}${active ? " is-active" : ""}${k.crossPassage ? "" : " knot--local"}`}
              onClick={() => onSelect({ kind: "relation", id: k.relation.id })}
              data-testid={`relation-${k.relation.id}`}
            >
              <title>{`${k.relation.type}: ${k.relation.rationale}`}</title>
              {active && k.crossPassage && (
                // Light up the earlier thread from its origin to the knot: the distance the link spans.
                <line
                  x1={earlier.x0}
                  x2={k.x}
                  y1={earlier.y}
                  y2={earlier.y}
                  stroke={st.color}
                  strokeWidth={2}
                  className="knot__span"
                />
              )}
              <path d={k.path} className="knot__hit" />
              <path
                d={k.path}
                className="knot__line"
                stroke={st.color}
                strokeWidth={active ? st.width + 1 : st.width}
                strokeDasharray={st.dash}
              />
              <circle cx={k.x} cy={k.ySource} r={1.8} fill={st.color} />
              <circle cx={k.x} cy={k.yTarget} r={1.8} fill={st.color} />
            </g>
          );
        })}
      </g>
    </svg>
  );
}
