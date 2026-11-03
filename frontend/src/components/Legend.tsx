import type { RelationType } from "../types";
import { RELATION_ORDER, RELATION_STYLE } from "../vocab";

interface Props {
  visibleTypes: Set<RelationType>;
  onToggle: (t: RelationType) => void;
  showWithinPassage: boolean;
  onToggleWithin: () => void;
}

export function Legend({ visibleTypes, onToggle, showWithinPassage, onToggleWithin }: Props) {
  return (
    <section className="legend" aria-label="Key">
      <div className="legend__group">
        <h3>Inferred relations</h3>
        {RELATION_ORDER.map((t) => {
          const st = RELATION_STYLE[t];
          return (
            <label key={t} className={`legend__item${st.primary ? "" : " legend__item--minor"}`}>
              <input type="checkbox" checked={visibleTypes.has(t)} onChange={() => onToggle(t)} />
              <svg width="34" height="10" aria-hidden>
                <line x1="2" x2="32" y1="5" y2="5" stroke={st.color} strokeWidth={st.width + 0.4} strokeDasharray={st.dash} />
              </svg>
              {st.label}
            </label>
          );
        })}
        <label className="legend__item legend__item--minor">
          <input type="checkbox" checked={showWithinPassage} onChange={onToggleWithin} />
          links within one passage
        </label>
      </div>
      <div className="legend__group">
        <h3>Kinds of knowledge</h3>
        <p className="legend__row">
          <span className="sample sample--text">“…”</span> <span><b>Textual evidence</b>: verbatim quotation</span>
        </p>
        <p className="legend__row">
          <svg width="14" height="12" aria-hidden><circle cx="7" cy="6" r="3.6" className="thread__origin thread__origin--observation" /></svg>
          <span><b>Observation</b>: stated in the passage</span>
        </p>
        <p className="legend__row">
          <svg width="14" height="12" aria-hidden><circle cx="7" cy="6" r="3.6" className="thread__origin thread__origin--interpretation" /></svg>
          <span><b>Inferred unit</b>: the system's interpretation</span>
        </p>
        <p className="legend__row">
          <svg width="14" height="12" aria-hidden><g className="thread__revised"><circle cx="7" cy="6" r="4.6" /><circle cx="7" cy="6" r="1.4" className="dot" /></g></svg>
          <span><b>Revised reading</b>: higher-level interpretation, revisable</span>
        </p>
        <p className="legend__row">
          <svg width="14" height="12" aria-hidden><circle cx="7" cy="6" r="2.2" className="thread__reinforced" /></svg>
          restated in a later passage
        </p>
      </div>
    </section>
  );
}
