import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Inspector } from "./components/Inspector";
import { Journey } from "./components/Journey";
import { Legend } from "./components/Legend";
import { Loom } from "./components/Loom";
import { ModelNote } from "./components/ModelNote";
import { ChapterContext, chapterLabeller } from "./passageRef";
import type { Book, ChapterMap, Journey as JourneyData, RelationDetail, RelationType, Selection, Snapshot, View } from "./types";
import { isDemo, RELATION_ORDER } from "./vocab";

// View and selection are mirrored in the URL hash so any view can be linked:
//   (empty) or #journey   Journey            #stage=2            Journey, stage 2 open
//   #weave                The Weave          #rel=r05_2 / #unit=u00_3 / #p=4   The Weave with a selection
interface Route { view: View; selection: Selection; stage: number | null }

function readHash(): Route {
  const h = window.location.hash;
  const m = h.match(/^#(rel|unit|p|stage)=(.+)$/);
  if (m?.[1] === "stage") return { view: "journey", selection: null, stage: Number(m[2]) - 1 };
  if (m?.[1] === "rel") return { view: "weave", selection: { kind: "relation", id: decodeURIComponent(m[2]) }, stage: null };
  if (m?.[1] === "unit") return { view: "weave", selection: { kind: "unit", id: decodeURIComponent(m[2]) }, stage: null };
  if (m?.[1] === "p") return { view: "weave", selection: { kind: "passage", idx: Number(m[2]) - 1 }, stage: null };
  return { view: h === "#weave" ? "weave" : "journey", selection: null, stage: null };
}

function writeHash(r: Route) {
  let h = "";
  if (r.view === "journey") h = r.stage !== null ? `#stage=${r.stage + 1}` : "";
  else {
    const s = r.selection;
    h = !s ? "#weave" : s.kind === "relation" ? `#rel=${s.id}` : s.kind === "unit" ? `#unit=${s.id}` : `#p=${s.idx + 1}`;
  }
  window.history.replaceState(null, "", h || window.location.pathname);
}

export function App() {
  const [books, setBooks] = useState<Book[] | null>(null);
  const [bookId, setBookId] = useState<string | null>(null);
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [connections, setConnections] = useState<RelationDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [route, setRoute] = useState<Route>(readHash);
  const { view, selection, stage } = route;
  const [journey, setJourney] = useState<JourneyData | null>(null);
  const [chapterMap, setChapterMap] = useState<ChapterMap | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<RelationType>>(new Set(RELATION_ORDER));
  const [showWithinPassage, setShowWithinPassage] = useState(true);

  useEffect(() => {
    api.books()
      .then((b) => {
        setBooks(b);
        // ?book=<id> opens a particular book, so each book's Journey can be linked.
        const wanted = new URLSearchParams(window.location.search).get("book");
        setBookId(b.find((x) => x.id === wanted)?.id ?? b[0]?.id ?? null);
      })
      .catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!bookId) return;
    setSnap(null);
    setConnections(null);
    setJourney(null);
    setChapterMap(null);
    api.chapters(bookId).then(setChapterMap).catch(() => setChapterMap(null));
    api.journey(bookId).then(setJourney).catch(() => setJourney(null));
    api.snapshot(bookId).then(setSnap).catch((e) => setError(String(e)));
    api.connections(bookId).then(setConnections).catch(() => setConnections([]));
  }, [bookId]);

  const go = useCallback((r: Route) => {
    setRoute(r);
    writeHash(r);
  }, []);
  const select = useCallback((s: Selection) => go({ view: "weave", selection: s, stage: null }), [go]);
  const selectStage = useCallback((i: number | null) => go({ view: "journey", selection: null, stage: i }), [go]);
  const openInWeave = useCallback(
    (s: Selection) => {
      go({ view: "weave", selection: s, stage: null });
      window.scrollTo({ top: 0 });
    },
    [go],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (view === "weave") select(null);
      else selectStage(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [select, selectStage, view]);

  const toggleType = (t: RelationType) =>
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });

  if (error) {
    return (
      <main className="page">
        <p className="error">Could not reach the MOTIF API. Is the backend running on port 8000?<br />{error}</p>
      </main>
    );
  }
  if (books && books.length === 0) {
    return (
      <main className="page">
        <p className="error">No processed books in this database. Run the CLI first (see README).</p>
      </main>
    );
  }
  if (!snap) return <main className="page muted">Opening the book…</main>;

  const demo = isDemo(snap.book.provenance);
  const meta = snap.book.meta;
  const chapterOf = chapterLabeller(chapterMap);

  return (
    <ChapterContext.Provider value={chapterOf}>
    <main className="page">
      {demo && (
        <div className="provenance provenance--demo" role="note">
          <strong>Demonstration data.</strong> These representations were written by hand to exercise the pipeline
          offline. They are not model output and do not show what the system can infer.
        </div>
      )}

      <header className="masthead">
        <div className="masthead__top">
          <p className="masthead__brand">
            <span className="masthead__mark">MOTIF</span>
          </p>
          {books && books.length > 1 && (
            <select className="masthead__books" aria-label="Book" value={bookId ?? ""}
              onChange={(e) => { go({ view, selection: null, stage: null }); setBookId(e.target.value); }}>
              {books.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}
            </select>
          )}
        </div>
        <div className="masthead__book">
          <h1>{snap.book.title}</h1>
          <p className="masthead__byline">
            {snap.book.author}
            {meta.translator ? `, translated by ${meta.translator}` : ""} · {meta.source}
          </p>
          {!demo && <ModelNote model={snap.book.model} />}
        </div>
        <nav className="views" aria-label="Views">
          <button className={`views__tab${view === "journey" ? " is-current" : ""}`} aria-current={view === "journey"}
            onClick={() => go({ view: "journey", selection: null, stage: stage })}>
            <span className="views__name">Journey</span> <span className="views__hint">the path of ideas</span>
          </button>
          <button className={`views__tab${view === "weave" ? " is-current" : ""}`} aria-current={view === "weave"}
            onClick={() => go({ view: "weave", selection, stage: null })}>
            <span className="views__name">The Weave</span> <span className="views__hint">every thread and connection</span>
          </button>
        </nav>
      </header>

      {view === "journey" && (
        <Journey snap={snap} journey={journey} selectedStage={stage} onSelectStage={selectStage} openInWeave={openInWeave} />
      )}

      {view === "weave" && (
      <div className="workspace">
        <div className="loom-wrap">
          <Loom snap={snap} selection={selection} onSelect={select} visibleTypes={visibleTypes} showWithinPassage={showWithinPassage} />
          <Legend
            visibleTypes={visibleTypes}
            onToggle={toggleType}
            showWithinPassage={showWithinPassage}
            onToggleWithin={() => setShowWithinPassage((v) => !v)}
          />
        </div>
        <aside className={`inspector${demo ? " inspector--demo" : ""}`} aria-live="polite">
          {selection && (
            <button className="inspector__close link" onClick={() => select(null)} aria-label="Close">close ✕</button>
          )}
          <Inspector snap={snap} selection={selection} onSelect={select} connections={connections} />
          {demo && <p className="inspector__stamp">demonstration data · not model output</p>}
        </aside>
      </div>
      )}
    </main>
    </ChapterContext.Provider>
  );
}
