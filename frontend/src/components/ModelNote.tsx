import { useEffect, useId, useRef, useState } from "react";

/** "muse-spark-1.3" -> "Muse Spark 1.3"; any other id is shown as given. */
export function modelLabel(model: string | null | undefined): string {
  const m = model?.match(/^muse-spark-(.+)$/i);
  return m ? `Muse Spark ${m[1]}` : model || "a language model";
}

/** The compact disclosure under the book title: who produced the interpretations, with the fuller
 *  statement of what is verified and what is not behind a small information button.
 *  The popover opens on click, Enter or Space, also shows on hover, and closes on Escape or outside click. */
export function ModelNote({ model }: { model: string | null | undefined }) {
  const [pinned, setPinned] = useState(false);
  const [hover, setHover] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  const name = modelLabel(model);
  const open = pinned || hover;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.stopPropagation(); // do not also clear the current selection
      setPinned(false);
      setHover(false);
    };
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setPinned(false);
    };
    window.addEventListener("keydown", onKey, true);
    document.addEventListener("mousedown", onDown);
    return () => {
      window.removeEventListener("keydown", onKey, true);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  return (
    <span className="modelnote" ref={ref} onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}>
      <span className="modelnote__line">
        <span className="modelnote__spark" aria-hidden="true">✧</span> Powered by {name}
      </span>
      <button
        type="button"
        className="modelnote__info"
        aria-label="About these interpretations"
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setPinned((v) => !v)}
      >
        <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
          <circle cx="8" cy="8" r="7" fill="none" stroke="currentColor" strokeWidth="1" />
          <circle cx="8" cy="4.6" r="0.95" fill="currentColor" />
          <path d="M8 7.2 V12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
        </svg>
      </button>
      <span id={id} role="note" className="modelnote__pop" hidden={!open}>
        MOTIF uses Meta's {name} to construct evidence-linked interpretations.{" "}
        <span className="key--text">Quotations are verified against the source text;</span>{" "}
        <span className="key--gen">AI-generated interpretations have not been independently validated.</span>
      </span>
    </span>
  );
}
