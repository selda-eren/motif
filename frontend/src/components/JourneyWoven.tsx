import { useState } from "react";
import type { Construction, Journey as JourneyData, Relation, Revision, Selection, Snapshot, TransitionEvidence, TransitionKind, Unit } from "../types";
import {
  VIEW, chevronPath, convergencePath, crossingPaths, formatPassages, loopPath, movePath, returnApex, returnPath, rosettePath,
  type JourneyLayout, type Landmark, type PathMove, type Return,
} from "../journeyLayout";
import { PassageNo } from "../passageRef";
import { RELATION_STYLE, TRANSITION_KIND, passageNo, roman } from "../vocab";
import { KindBadge, MeaningCard } from "./Journey";

export type Focus =
  | { kind: "move"; index: number }
  | { kind: "return"; from: number; to: number }
  | { kind: "meaning"; id: string }
  | null;

const pctX = (x: number) => `${(x / VIEW.w) * 100}%`;
const pctY = (y: number) => `${(y / VIEW.h) * 100}%`;
const passages = (a: number, b: number) => (a === b ? `passage ${passageNo(a)}` : `passages ${passageNo(a)}–${passageNo(b)}`);

interface PathProps {
  layout: JourneyLayout;
  journey: JourneyData;
  selectedStage: number | null;
  focus: Focus;
  onStage: (i: number) => void;
  onFocus: (f: Focus) => void;
}

/** The woven Journey: one thread through the book, loops back to earlier ideas, and lace knots where
 *  several passages converge into a constructed meaning. Every mark comes from `layout` (journeyLayout.ts). */
export function JourneyPath({ layout, journey, selectedStage, focus, onStage, onFocus }: PathProps) {
  const { stages, moves, returns, landmarks } = layout;
  const Y = VIEW.threadY;
  const first = stages[0];
  const last = stages[stages.length - 1];
  const isMove = (i: number) => focus?.kind === "move" && focus.index === i;
  const isReturn = (r: Return) => focus?.kind === "return" && focus.from === r.from && focus.to === r.to;
  const [hover, setHover] = useState<string | null>(null);
  const isMeaning = (id: string) => focus?.kind === "meaning" && focus.id === id;
  const lit = (id: string) => isMeaning(id) || hover === id;

  return (
    <div className="jp-scroll">
      <div className="jp" data-testid="journey-path" style={{ aspectRatio: `${VIEW.w} / ${VIEW.h}` }}>
        <svg className="jp__svg" viewBox={`0 0 ${VIEW.w} ${VIEW.h}`} aria-hidden="true">
          <defs>
            <marker id="jp-return-end" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 1 1 L 8 5 L 1 9" fill="none" stroke="var(--lapis)" strokeWidth="1.4" />
            </marker>
          </defs>

          {/* Where each stage sits in the book: a faint bracket along the thread. */}
          {stages.map((s) => (
            <path key={`span${s.index}`} className="jp__span" d={`M ${s.x0 + 3} ${Y + 44} L ${s.x1 - 3} ${Y + 44}`} />
          ))}

          {/* Lead-in and tail: where the journey begins and where it ends. */}
          <path className="jp__thread jp__thread--end" pathLength={1} d={`M ${VIEW.margin - 30} ${Y} C ${VIEW.margin - 10} ${Y - 8}, ${first.cx - 30} ${Y + 8}, ${first.cx} ${Y}`} />
          <path className="jp__thread jp__thread--end" pathLength={1} d={`M ${last.cx} ${Y} C ${last.cx + 30} ${Y - 8}, ${VIEW.w - VIEW.margin + 10} ${Y + 8}, ${VIEW.w - VIEW.margin + 26} ${Y}`} />
          <circle className="jp__end-knot" cx={VIEW.w - VIEW.margin + 29} cy={Y} r={3.2} />
          <circle className="jp__end-knot" cx={VIEW.margin - 33} cy={Y} r={3.2} />

          {/* Moves between stages: the thread's form shows the kind of move. */}
          {moves.map((m) => <MoveThread key={`m${m.from}`} m={m} selected={isMove(m.from)} />)}

          {/* Returns: a later stage rereads or reframes ideas from an earlier one. */}
          {returns.map((r) => (
            <path key={`r${r.from}-${r.to}`} className={`jp__return${isReturn(r) ? " is-selected" : ""}`} d={returnPath(r, stages)}
              strokeWidth={1 + 0.45 * Math.min(6, r.count)} markerEnd="url(#jp-return-end)" />
          ))}

          {/* Convergences: threads from contributing stages into a constructed meaning. */}
          {landmarks.map((l) => (
            <g key={`l${l.construction.id}`} className={`jp__meaning${lit(l.construction.id) ? " is-selected" : ""}`}>
              {l.sources.map((src) => (
                <path key={src.stage} className={`jp__converge${src.reinforcement ? " is-later" : ""}`}
                  d={convergencePath(stages[src.stage].cx, l, stages[src.stage].r)} />
              ))}
              <path className="jp__rosette" d={rosettePath(l.x, VIEW.meaningY)} />
              <circle className="jp__rosette-core" cx={l.x} cy={VIEW.meaningY} r={2.6} />
            </g>
          ))}

          {/* Stage knots: size follows how much the representation changed there. */}
          {stages.map((s) => (
            <g key={`k${s.index}`} className={`jp__knot${selectedStage === s.index ? " is-selected" : ""}`}>
              <line className="jp__tether" x1={s.cx} y1={VIEW.titleBottom} x2={s.cx} y2={Y - s.r - 2} />
              <circle cx={s.cx} cy={Y} r={s.r} />
              <circle className="jp__knot-inner" cx={s.cx} cy={Y} r={Math.max(2, s.r - 4)} />
            </g>
          ))}
        </svg>

        {/* Readable, focusable labels laid over the drawing. */}
        <span className="jp__end-label" style={{ left: pctX(VIEW.margin - 38), top: pctY(Y + 14) }}>beginning</span>
        <span className="jp__end-label jp__end-label--end" style={{ right: pctX(VIEW.margin - 38), top: pctY(Y + 14) }}>end</span>

        {stages.map((s, i) => (
          <button key={`t${i}`} className={`jp__stage${selectedStage === i ? " is-selected" : ""}`} data-testid={`stage-${i}`}
            style={{ left: pctX(s.labelLeft), width: pctX(s.labelWidth), top: pctY(VIEW.titleBottom) }}
            aria-pressed={selectedStage === i} onClick={() => onStage(i)}>
            <span className="jp__numeral">{roman(i + 1)}</span>
            <span className="jp__title gen">{journey.stages[i].title}</span>
            <span className="jp__range">{passages(s.first, s.last)}</span>
          </button>
        ))}

        {moves.map((m) => (
          <button key={`b${m.from}`} className={`jp__move${isMove(m.from) ? " is-selected" : ""}`} data-testid={`transition-${m.from}`}
            style={{ left: pctX((m.x1 + m.x2) / 2), top: pctY(Y + 22) }}
            aria-label={`From stage ${m.from + 1} to ${m.to + 1}: ${m.kind ? TRANSITION_KIND[m.kind].label : "leads on"}${m.tentative ? ", tentative" : ""}`}
            onClick={() => onFocus(isMove(m.from) ? null : { kind: "move", index: m.from })}>
            {m.transition ? <KindBadge t={m.transition} /> : <span className="kind kind--succession">Leads on</span>}
          </button>
        ))}

        {returns.map((r) => {
          const apex = returnApex(r, stages);
          return (
            <button key={`rb${r.from}-${r.to}`} className={`jp__return-handle${isReturn(r) ? " is-selected" : ""}`}
              data-testid={`return-${r.from}-${r.to}`} style={{ left: pctX(apex.x), top: pctY(apex.y) }}
              title={`Stage ${roman(r.from + 1)} returns to ideas first met in stage ${roman(r.to + 1)}`}
              aria-label={`Stage ${r.from + 1} returns to ideas from stage ${r.to + 1}: ${r.revisions.length} revised readings, ${r.relations.length} reframing links`}
              onClick={() => onFocus(isReturn(r) ? null : { kind: "return", from: r.from, to: r.to })}>
              ↺
            </button>
          );
        })}

        {landmarks.map((l) => (
          <button key={`lb${l.construction.id}`} className={`jp__landmark${l.captionRow ? " jp__landmark--low" : ""}${isMeaning(l.construction.id) ? " is-selected" : ""}`}
            data-testid={`meaning-${l.construction.id}`} style={{ left: pctX(l.x), top: pctY(VIEW.meaningY - 14) }}
            title={l.construction.statement}
            aria-label={`Meaning ${l.passages.length === 1 ? "within" : "woven from"} ${formatPassages(l.passages)}: ${l.construction.statement}`}
            onMouseEnter={() => setHover(l.construction.id)} onMouseLeave={() => setHover(null)}
            onFocus={() => setHover(l.construction.id)} onBlur={() => setHover(null)}
            onClick={() => onFocus(isMeaning(l.construction.id) ? null : { kind: "meaning", id: l.construction.id })}>
            <span className="jp__landmark-hit" aria-hidden="true" />
            <span className="jp__landmark-caption">
              {l.passages.length === 1 ? "within" : "woven from"}<br />{formatPassages(l.passages, String, 2)}
            </span>
          </button>
        ))}
      </div>
      <PathLegend layout={layout} />
    </div>
  );
}

function MoveThread({ m, selected }: { m: PathMove; selected: boolean }) {
  const cls = `jp__thread jp__thread--${m.kind ?? "none"}${m.tentative ? " is-tentative" : ""}${selected ? " is-selected" : ""}`;
  if (m.kind === "contradiction") {
    const [a, b] = crossingPaths(m);
    return <g className={cls}><path pathLength={1} d={a} /><path pathLength={1} d={b} /></g>;
  }
  if (m.kind === "analogy") {
    return <g className={cls}><path pathLength={1} d={movePath(m, -3)} /><path pathLength={1} d={movePath(m, 3)} /></g>;
  }
  return (
    <g className={cls}>
      <path pathLength={1} d={movePath(m)} />
      {m.kind === "reinterpretation" && <path className="jp__ornament" d={loopPath(m)} />}
      {m.kind === "consequence" && <path className="jp__ornament" d={chevronPath(m)} />}
    </g>
  );
}

const LEGEND: { kind: TransitionKind; d: string; extra?: string }[] = [
  { kind: "development", d: "M 2 8 C 12 3, 22 13, 32 8" },
  { kind: "consequence", d: "M 2 8 C 12 3, 22 13, 32 8", extra: "M 14 3 L 20 8 L 14 13" },
  { kind: "reinterpretation", d: "M 2 8 C 12 3, 22 13, 32 8", extra: "M 9 8 C 22 8, 22 -3, 17 -3 C 12 -3, 12 8, 25 8" },
  { kind: "contradiction", d: "M 2 5 C 12 5, 22 11, 32 11 M 2 11 C 12 11, 22 5, 32 5" },
  { kind: "analogy", d: "M 2 6 C 12 1, 22 11, 32 6 M 2 11 C 12 6, 22 16, 32 11" },
  { kind: "succession", d: "M 2 8 C 12 3, 22 13, 32 8" },
  { kind: "unclassified", d: "M 2 8 C 12 3, 22 13, 32 8" },
];

function PathLegend({ layout }: { layout: JourneyLayout }) {
  const kinds = new Set(layout.moves.map((m) => m.kind));
  const tentative = layout.moves.some((m) => m.tentative);
  return (
    <ul className="jp-legend" aria-label="How to read the journey">
      {LEGEND.filter((l) => kinds.has(l.kind)).map((l) => (
        <li key={l.kind}>
          <svg viewBox="0 -4 34 20" aria-hidden="true" className={`jp__thread jp__thread--${l.kind} jp-legend__glyph`}>
            <path d={l.d} />{l.extra && <path className="jp__ornament" d={l.extra} />}
          </svg>
          {TRANSITION_KIND[l.kind].label.toLowerCase()}
        </li>
      ))}
      {tentative && (
        <li><svg viewBox="0 -4 34 20" aria-hidden="true" className="jp__thread is-tentative jp-legend__glyph"><path d="M 2 8 C 12 3, 22 13, 32 8" /></svg>tentative: not established by the evidence</li>
      )}
      {layout.returns.length > 0 && (
        <li><svg viewBox="0 -4 34 20" aria-hidden="true" className="jp-legend__glyph"><path className="jp__return" d="M 30 14 C 30 -2, 4 -2, 4 12" markerEnd="url(#jp-return-end)" /></svg>returns to an earlier idea (thicker: more rereadings)</li>
      )}
      {layout.landmarks.length > 0 && (
        <li><svg viewBox="-12 -12 24 24" aria-hidden="true" className="jp-legend__glyph jp-legend__glyph--round"><path className="jp__rosette" d={rosettePath(0, 0, 9)} /></svg>a meaning built from several parts of the text</li>
      )}
      <li className="jp-legend__note">larger knot: more changed in that stage</li>
    </ul>
  );
}

// ---------- detail panels ----------

export function EvidencePairs({ evidence, openInWeave }: { evidence: TransitionEvidence[]; openInWeave: (s: Selection) => void }) {
  return (
    <>
      {evidence.map((e, k) => (
        <figure key={k} className="evidence evidence--pair">
          <blockquote>“{e.earlier.quote}” <span className="muted small">passage <PassageNo i={e.earlier.passage} at={e.earlier.start} /></span></blockquote>
          <blockquote>“{e.later.quote}” <span className="muted small">passage <PassageNo i={e.later.passage} at={e.later.start} /></span></blockquote>
          <figcaption>
            {e.kind === "construction" ? <span className="badge badge--gloss">constructed meaning</span>
              : e.kind === "revision" ? <span className="badge badge--gloss">revised reading</span>
              : <span className="badge badge--relation">{RELATION_STYLE[e.type as keyof typeof RELATION_STYLE]?.verb ?? e.type.toLowerCase()}</span>}{" "}
            <span className="gen">{e.how_it_supports}</span>{" "}
            {e.relation_id && <button className="link small" onClick={() => openInWeave({ kind: "relation", id: e.relation_id! })}>open in The Weave</button>}
            {!e.relation_id && <button className="link small" onClick={() => openInWeave({ kind: "unit", id: e.later.unit_id })}>open in The Weave</button>}
          </figcaption>
        </figure>
      ))}
    </>
  );
}

export function MoveDetail({ journey, index, openInWeave, onStage }: {
  journey: JourneyData; index: number; openInWeave: (s: Selection) => void; onStage: (i: number) => void;
}) {
  const t = journey.explanation?.transitions.find((x) => x.from_index === index);
  const a = journey.stages[index];
  const b = journey.stages[index + 1];
  return (
    <div className="stage-detail" data-testid="move-detail">
      <section className="level level--1">
        <p className="level__kicker">The move from stage {roman(index + 1)} to stage {roman(index + 2)}</p>
        <h3 className="level__title gen">{a.title} → {b.title}</h3>
        {t ? (
          <>
            <p><KindBadge t={t} /> <span className="muted small">{TRANSITION_KIND[t.kind].gloss}</span></p>
            {t.what_changes && <p><span className="level__label">What changes</span> <span className="gen">{t.what_changes}</span></p>}
            {t.why && <p><span className="level__label">Why the book moves this way</span> <span className="gen">{t.why}</span></p>}
            {(t.grounding_note || t.limitation || t.beyond_evidence) && (
              <p className="caveat" data-testid="caveat">
                <span className="caveat__label">Limits</span>
                {t.grounding_note && <span>{t.grounding_note} </span>}
                {t.beyond_evidence && <span className="gen">Beyond the recorded evidence: {t.beyond_evidence} </span>}
                {t.limitation && <span className="gen">{t.limitation}</span>}
              </p>
            )}
          </>
        ) : (
          <p><span className="gen">{a.leads_to_next}</span> <span className="muted small">(no explanation layer: the kind of move is not classified)</span></p>
        )}
        <p className="small"><button className="link" onClick={() => onStage(index)}>Stage {roman(index + 1)}</button> · <button className="link" onClick={() => onStage(index + 1)}>Stage {roman(index + 2)}</button></p>
      </section>
      {t && t.evidence.length > 0 && (
        <section className="level level--2">
          <h4>What MOTIF recorded between these stages <span className="muted small">· quotations at both ends</span></h4>
          <EvidencePairs evidence={t.evidence} openInWeave={openInWeave} />
        </section>
      )}
      {t && t.evidence.length === 0 && <p className="caveat">No recorded link is cited for this move.</p>}
    </div>
  );
}

export function MeaningDetail({ snap, construction, openInWeave }: { snap: Snapshot; construction: Construction; openInWeave: (s: Selection) => void }) {
  const units = new Map<string, Unit>(snap.units.map((u) => [u.id, u]));
  return (
    <div className="stage-detail" data-testid="meaning-detail">
      <section className="level level--1">
        <p className="level__kicker">Woven meaning · {formatPassages([...new Set(construction.evidence.map((e) => e.passage))].sort((a, b) => a - b))}</p>
        <MeaningCard c={construction} units={units} />
        {construction.justification && (
          <p><span className="level__label">How the passages combine</span> <span className="gen">{construction.justification}</span></p>
        )}
        <p className="small muted">The units it draws on are unchanged; this meaning is recorded alongside them.</p>
      </section>
      <section className="level level--3">
        <h4>Trace it in The Weave</h4>
        <ul className="stage-links">
          {construction.contributors.map((x) => (
            <li key={x.unit_id}>
              <span className="obs">{units.get(x.unit_id)?.label ?? x.unit_id}</span>{" "}
              <button className="link small" onClick={() => openInWeave({ kind: "unit", id: x.unit_id })}>open in The Weave</button>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

/** How many passages a recorded rereading reaches back: the strongest long-distance evidence comes first. */
const reachOfRevision = (units: Map<string, Unit>, v: Revision) => v.passage - (units.get(v.unit_id)?.introduced_at ?? v.passage);
const reachOfRelation = (units: Map<string, Unit>, r: Relation) =>
  r.created_at - Math.min(units.get(r.source)?.introduced_at ?? r.created_at, units.get(r.target)?.introduced_at ?? r.created_at);
export const RETURN_PREVIEW = 3;

export function ReturnDetail({ snap, journey, ret, openInWeave }: {
  snap: Snapshot; journey: JourneyData; ret: Return; openInWeave: (s: Selection) => void;
}) {
  const [all, setAll] = useState(false);
  const units = new Map<string, Unit>(snap.units.map((u) => [u.id, u]));
  const label = (id: string | null) => (id ? units.get(id)?.label ?? id : "");
  // Strongest first (reach, then the order MORe recorded them). Nothing is dropped: "show all" reveals the rest.
  const revs = ret.revisions.map((v, k) => ({ v, k })).sort((a, b) => reachOfRevision(units, b.v) - reachOfRevision(units, a.v) || a.k - b.k);
  const rels = ret.relations.map((r, k) => ({ r, k })).sort((a, b) => reachOfRelation(units, b.r) - reachOfRelation(units, a.r) || a.k - b.k);
  const shownRevs = all ? revs : revs.slice(0, RETURN_PREVIEW);
  const shownRels = all ? rels : rels.slice(0, RETURN_PREVIEW);
  const hidden = revs.length - shownRevs.length + (rels.length - shownRels.length);
  return (
    <div className="stage-detail" data-testid="return-detail">
      <section className="level level--1">
        <p className="level__kicker">A return · stage {roman(ret.from + 1)} rereads stage {roman(ret.to + 1)}</p>
        <h3 className="level__title gen">{journey.stages[ret.from].title} → back to {journey.stages[ret.to].title}</h3>
        <p className="muted">
          What the book says in stage {roman(ret.from + 1)} changes how ideas from stage {roman(ret.to + 1)} should be read.
          MOTIF recorded {count(ret.revisions.length, "revised reading")}
          {ret.relations.length > 0 && <> and {count(ret.relations.length, "reframing link")}</>}, each with the original words.
          {!all && hidden > 0 && <> The ones that reach furthest back are shown first.</>}
        </p>
      </section>
      <section className="level level--2">
        {shownRels.length > 0 && <h4>Reframing links{!all && rels.length > shownRels.length ? <span className="muted small"> · {shownRels.length} of {rels.length}</span> : null}</h4>}
        <ul className="stage-links" data-testid="return-relations">
          {shownRels.map(({ r }) => (
            <li key={r.id}>
              <p><b>{label(r.source)}</b> <em>{RELATION_STYLE[r.type].verb}</em> <b>{label(r.target)}</b>
                <span className="muted small"> (reaches back {reachOfRelation(units, r)} passages)</span></p>
              <p className="gen small">{r.rationale}</p>
              <button className="link small" onClick={() => openInWeave({ kind: "relation", id: r.id })}>open in The Weave</button>
            </li>
          ))}
        </ul>
        {shownRevs.length > 0 && <h4>Revised readings{!all && revs.length > shownRevs.length ? <span className="muted small"> · {shownRevs.length} of {revs.length}</span> : null}</h4>}
        <ul className="stage-links" data-testid="return-revisions">
          {shownRevs.map(({ v }, k) => {
            const u = units.get(v.unit_id);
            return (
              <li key={`v${k}`}>
                <p><b>{label(v.unit_id)}</b> <span className="muted small">(first met in passage <PassageNo i={u?.introduced_at ?? 0} at={u?.evidence[0]?.start} />, reread in passage <PassageNo i={v.passage} />)</span></p>
                {u?.evidence[0] && <blockquote className="quote-inline">“{u.evidence[0].quote}”</blockquote>}
                <p className="small"><span className="badge badge--gloss">revised reading</span> <span className="gen">{v.new_reading}</span></p>
                <button className="link small" onClick={() => openInWeave({ kind: "unit", id: v.unit_id })}>see its history in The Weave</button>
              </li>
            );
          })}
        </ul>
        {(hidden > 0 || all) && (
          <p><button className="button" data-testid="return-show-all" aria-expanded={all} onClick={() => setAll((v) => !v)}>
            {all ? "Show only the strongest" : `Show all ${count(revs.length, "revised reading")} and ${count(rels.length, "reframing link")} (${hidden} more)`}
          </button></p>
        )}
      </section>
    </div>
  );
}

const count = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

export function findLandmark(layout: JourneyLayout, id: string): Landmark | undefined {
  return layout.landmarks.find((l) => l.construction.id === id);
}
