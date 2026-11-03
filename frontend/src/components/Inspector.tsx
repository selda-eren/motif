import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import type { QuoteInContext, RelationDetail, Revision, Selection, Snapshot, Unit } from "../types";
import { PassageNo } from "../passageRef";
import { RELATION_STYLE } from "../vocab";

interface Props {
  snap: Snapshot;
  selection: Selection;
  onSelect: (s: Selection) => void;
  connections: RelationDetail[] | null;
}

export function Inspector({ snap, selection, onSelect, connections }: Props) {
  if (!selection) return <Overview snap={snap} connections={connections} onSelect={onSelect} />;
  if (selection.kind === "relation") return <RelationView key={selection.id} snap={snap} relId={selection.id} onSelect={onSelect} />;
  if (selection.kind === "unit") return <UnitView snap={snap} unitId={selection.id} onSelect={onSelect} />;
  return <PassageView snap={snap} idx={selection.idx} onSelect={onSelect} />;
}

/* ---------- shared pieces ---------- */

function LayerBadge({ layer }: { layer: Unit["layer"] }) {
  return layer === "observation" ? (
    <span className="badge badge--observation" title="Directly stated in the passage">Observation</span>
  ) : (
    <span className="badge badge--interpretation" title="Inferred by the system, anchored to a quotation">Inferred unit</span>
  );
}

function Quote({ q, onPassage }: { q: QuoteInContext; onPassage?: (i: number) => void }) {
  return (
    <figure className="quote">
      <figcaption>
        <button className="link" onClick={() => onPassage?.(q.passage)}>Passage <PassageNo i={q.passage} at={q.start} /></button> · textual evidence
      </figcaption>
      <blockquote>
        {q.before && <span className="quote__context">…{q.before}</span>}
        <mark>{q.quote}</mark>
        {q.after && <span className="quote__context">{q.after}…</span>}
      </blockquote>
    </figure>
  );
}

function quotesFromSnapshot(snap: Snapshot, u: Unit, window = 160): QuoteInContext[] {
  return u.evidence.map((ev) => {
    const text = snap.passages.find((p) => p.idx === ev.passage)?.text ?? "";
    return { passage: ev.passage, quote: ev.quote, start: ev.start, before: text.slice(Math.max(0, ev.start - window), ev.start), after: text.slice(ev.end, ev.end + window) };
  });
}

function ReadingHistory({ revisions, snap, onSelect }: { revisions: Revision[]; snap: Snapshot; onSelect: (s: Selection) => void }) {
  if (!revisions.length) return null;
  const label = (id: string | null) => snap.units.find((u) => u.id === id)?.label ?? id;
  return (
    <section className="gloss">
      <h4>How its reading changed <span className="badge badge--gloss">Interpretation · revisable</span></h4>
      <ol>
        {revisions.map((r, i) => (
          <li key={i}>
            <div className="gloss__when">
              Passage <PassageNo i={r.passage} />, prompted by{" "}
              {r.cause_unit ? (
                <button className="link" onClick={() => onSelect({ kind: "unit", id: r.cause_unit! })}>{label(r.cause_unit)}</button>
              ) : "—"}
            </div>
            <p className="gloss__reading">{r.new_reading}</p>
            <p className="gloss__why">{r.rationale}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

function UnitCard({ u, quotes, onSelect, role }: { u: Unit; quotes: QuoteInContext[]; onSelect: (s: Selection) => void; role: string }) {
  return (
    <article className="unitcard">
      <header>
        <span className="unitcard__role">{role}</span>
        <button className="unitcard__label link" onClick={() => onSelect({ kind: "unit", id: u.id })}>{u.label}</button>
        <LayerBadge layer={u.layer} />
      </header>
      <p className="unitcard__content">{u.content}</p>
      {quotes.map((q, i) => <Quote key={i} q={q} onPassage={(p) => onSelect({ kind: "passage", idx: p })} />)}
      {u.reading && (
        <p className="unitcard__reading"><span className="badge badge--gloss">Current reading</span> {u.reading}</p>
      )}
    </article>
  );
}

/* ---------- views ---------- */

function Overview({ snap, connections, onSelect }: { snap: Snapshot; connections: RelationDetail[] | null; onSelect: (s: Selection) => void }) {
  return (
    <div className="inspector__body">
      <h2>Reading the loom</h2>
      <p>
        Passages run left to right. Each thread is an idea, image or claim, beginning where it is first perceived
        and continuing as long as later passages return to it. Coloured loops are relations, tied at the passage
        where the system formed them. Select a loop to see the quotations on both sides.
      </p>
      <h3>Threads worth following</h3>
      {!connections && <p className="muted">Loading…</p>}
      <ul className="connections">
        {connections?.map((c) => {
          const st = RELATION_STYLE[c.relation.type];
          const earlier = c.earlier === c.source.id ? c.source : c.target;
          const later = c.later === c.source.id ? c.source : c.target;
          return (
            <li key={c.relation.id}>
              <button className="connection" onClick={() => onSelect({ kind: "relation", id: c.relation.id })}>
                <span className="connection__type" style={{ color: st.color }}>{st.label}</span>
                <span className="connection__ends">
                  {later.label} <span className="muted">({later.introduced_at + 1})</span> · {earlier.label}{" "}
                  <span className="muted">({earlier.introduced_at + 1})</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="muted small">
        {snap.units.length} units · {snap.relations.length} inferred relations · {snap.revisions.length} revised readings
      </p>
    </div>
  );
}

function RelationView({ snap, relId, onSelect }: { snap: Snapshot; relId: string; onSelect: (s: Selection) => void }) {
  const [detail, setDetail] = useState<RelationDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.relation(snap.book.id, relId).then(setDetail).catch((e) => setError(String(e)));
  }, [snap.book.id, relId]);

  if (error) return <div className="inspector__body error">{error}</div>;
  if (!detail) return <div className="inspector__body muted">Loading…</div>;
  const { relation: r, source, target } = detail;
  const st = RELATION_STYLE[r.type];
  const ordered = [
    { u: source, quotes: detail.source_evidence },
    { u: target, quotes: detail.target_evidence },
  ].sort((a, b) => a.u.introduced_at - b.u.introduced_at);
  const earlier = ordered[0].u;
  const revisions = snap.revisions.filter((v) => v.unit_id === earlier.id);

  return (
    <div className="inspector__body">
      <p className="kicker"><span className="badge badge--relation">Inferred relation</span> confidence {r.confidence.toFixed(2)}</p>
      <h2 className="relation-title">
        {source.label} <em style={{ color: st.color }}>{st.verb}</em> {target.label}
      </h2>
      <p className="muted">
        Formed while reading passage <PassageNo i={r.created_at} />
        {earlier.introduced_at < r.created_at ? <>, reaching back to passage <PassageNo i={earlier.introduced_at} /></> : ", within the same passage"}.
      </p>
      <section className="rationale">
        <h4>Why the system linked them</h4>
        <p>{r.rationale}</p>
      </section>
      {ordered.map(({ u, quotes }) => (
        <UnitCard key={u.id} u={u} quotes={quotes} onSelect={onSelect} role={`Passage ${u.introduced_at + 1}`} />
      ))}
      <ReadingHistory revisions={revisions} snap={snap} onSelect={onSelect} />
    </div>
  );
}

function UnitView({ snap, unitId, onSelect }: { snap: Snapshot; unitId: string; onSelect: (s: Selection) => void }) {
  const u = snap.units.find((x) => x.id === unitId);
  if (!u) return <div className="inspector__body error">Unknown unit {unitId}</div>;
  const rels = snap.relations.filter((r) => r.source === u.id || r.target === u.id);
  const label = (id: string) => snap.units.find((x) => x.id === id)?.label ?? id;
  return (
    <div className="inspector__body">
      <p className="kicker">{u.kind} · first perceived in passage <PassageNo i={u.introduced_at} />{u.status === "contested" ? " · contested" : ""}</p>
      <h2>{u.label}</h2>
      <p><LayerBadge layer={u.layer} /> <span className="muted">confidence {u.confidence.toFixed(2)}</span></p>
      <p className="unitcard__content">{u.content}</p>
      {quotesFromSnapshot(snap, u).map((q, i) => <Quote key={i} q={q} onPassage={(p) => onSelect({ kind: "passage", idx: p })} />)}
      <ReadingHistory revisions={snap.revisions.filter((v) => v.unit_id === u.id)} snap={snap} onSelect={onSelect} />
      {rels.length > 0 && (
        <>
          <h4>Relations</h4>
          <ul className="connections">
            {rels.map((r) => {
              const st = RELATION_STYLE[r.type];
              return (
                <li key={r.id}>
                  <button className="connection" onClick={() => onSelect({ kind: "relation", id: r.id })}>
                    <span className="connection__ends">
                      {label(r.source)} <em style={{ color: st.color }}>{st.verb}</em> {label(r.target)}
                    </span>
                    <span className="muted small">passage {r.created_at + 1}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </>
      )}
    </div>
  );
}

function PassageView({ snap, idx, onSelect }: { snap: Snapshot; idx: number; onSelect: (s: Selection) => void }) {
  const p = snap.passages.find((x) => x.idx === idx);
  const change = snap.changes.find((c) => c.passage === idx);
  if (!p) return <div className="inspector__body error">Unknown passage</div>;
  // Evidence spans from every unit, in text order, for highlighting (overlaps: first wins).
  const spans = snap.units
    .flatMap((u) => u.evidence.filter((e) => e.passage === idx).map((e) => ({ ...e, unit: u })))
    .sort((a, b) => a.start - b.start);
  const parts: ReactNode[] = [];
  let cursor = 0;
  spans.forEach((s, i) => {
    if (s.start < cursor) return;
    parts.push(<span key={`t${i}`}>{p.text.slice(cursor, s.start)}</span>);
    parts.push(
      <mark key={`m${i}`} className={`span span--${s.unit.layer}`} title={s.unit.label} onClick={() => onSelect({ kind: "unit", id: s.unit.id })}>
        {p.text.slice(s.start, s.end)}
      </mark>,
    );
    cursor = s.end;
  });
  parts.push(<span key="end">{p.text.slice(cursor)}</span>);

  return (
    <div className="inspector__body">
      <p className="kicker">Passage <PassageNo i={idx} /> of {snap.passages.length}</p>
      {p.gist && (
        <p className="gist"><span className="badge badge--interpretation">System gist</span> {p.gist}</p>
      )}
      {change && (
        <p className="muted small">
          {change.introduced.length} new units · {change.reinforced.length} restated · {change.cross_passage_relations.length} links to earlier passages · {change.revisions.length} readings revised · change score {change.change_score}
        </p>
      )}
      <div className="passage-text">{parts}</div>
    </div>
  );
}
