# Journey of Ideas: visual approaches (Milestone 6)

## What the data offers

Everything a visualization may show must already be stored:

| Element | Source |
|---|---|
| Stages (4–6) | Journey: title, summary, passage range |
| Moves between stages | Journey explanation: kind (develops, consequence, reinterprets, challenges, parallel, succession, unclassified), certainty, evidence |
| Returns to earlier ideas | MORe: interpretive revisions of units first met in an earlier stage, and REFRAMES/CONTRADICTS links that reach back across stages |
| Convergences | MORe: established constructed meanings cited by a stage, with contributing units and the passages they come from |
| Emphasis | MORe: change score per passage |

Pending meanings are never shown.

## 1. A flowing conceptual path

One thread runs left to right through the book, with each stage a knot placed where it falls in the text.

**Data.**
- The space between two knots is drawn by the kind of move: a steady line for "develops", a chevron for "consequence", a
  small loop for "reinterprets", crossing strands for "challenges", a doubled strand for "parallel", a thin line for
  "comes next".
- Tentative moves are dashed.

**15 seconds.** The reader sees how many stages there are, their titles in order, and what kind of move joins each pair.

**Interaction.** Clicking a knot or a move opens its explanation, quotations and evidence.

**Strengths:** very clear; easy to build. **Limitations:** it shows only the main line. Returns and convergences, which
are what makes MOTIF different, stay hidden. **Effort:** low.

## 2. A woven tapestry (path + returns + convergences)

Approach 1, plus two thread families drawn from MORe:
- **Returning loops** above the path arc from a later stage back to an earlier one wherever the later stage reread or
  reframed ideas first met earlier. Thickness grows with the number of recorded rereadings.
- **Converging threads** below the path run from every stage that contributed to a constructed meaning into a small
  lace knot, the landmark, under the stage where that meaning formed.

**15 seconds.** The reader sees all of the following:
- the order of the stages;
- the kind of each move;
- where the book turns back on itself (loops);
- where several parts of the book come together (lace knots).

**Interaction.** Every element opens a plain-language explanation, why it matters, the quotations, and links into The Weave.

**Strengths:** it makes revisiting and convergence perceptible, which is the point of MORe, and the crochet metaphor
carries meaning.

**Limitations:**
- More marks to learn, so a small legend is needed.
- Loop thickness summarizes counts, not importance.
- Landmarks need captions, but constructed meanings have no short titles. Captions say where the meaning draws from
  ("woven from passages I–IV"); the statement appears on selection.

**Effort:** moderate. It is SVG plus a pure layout function.

## 3. A minimalist map of transformations

Stages as nodes in a 2D field, with only reinterpretations and contradictions drawn as arrows. Distance reflects
how much the representation changed.

**15 seconds.** The reader sees where the big turns are. Order and narrative are weaker.

**Interaction.** As above.

**Strengths:** strongly emphasizes change. **Limitations:**
- The 2D placement would be an invented spatial meaning: no stored dimension supports it.
- Development and consequence moves disappear.
- It is harder to read as a journey.

**Effort:** moderate. The layout choices are hard to justify.

## Recommendation: approach 2, the woven tapestry

It is the only option that shows all six things the brief asks for:
- where the journey begins;
- what develops;
- where it transforms;
- where it revisits;
- where threads converge;
- where it ends.

Every mark is derived deterministically from stored data. It degrades gracefully: with no returns or meanings it
becomes approach 1. It fits the existing React + SVG code without a new library.

## Encoding (as implemented)

| Mark | Meaning | Derived from |
|---|---|---|
| Knot on the thread; horizontal position and span | a stage; where it sits in the book | stage passage range ÷ number of passages |
| Knot size | how much the representation changed in that stage | sum of the stage's passage change scores, scaled to the largest |
| Steady line / chevron / loop / crossing strands / doubled strand / thin line / dotted | develops / draws a consequence / reinterprets / challenges / draws a parallel / comes next / unclassified | explanation `kind` |
| Dashed and faint | tentative: the evidence does not establish the move | explanation `certainty` |
| Arc above, from a later stage back to an earlier one | the later stage rereads or reframes ideas first met earlier | interpretive revisions and REFRAMES/CONTRADICTS links, grouped by stage pair |
| Lace knot below, with threads from contributing stages | a meaning MORe built from several representations | established constructed meanings cited by the stage; contributors' stages |

**Not color alone.** Kinds differ in shape and carry text labels. Color only reinforces the shape.

## Implementation

| | Where |
|---|---|
| Layout and geometry: pure, deterministic functions of the Journey and the snapshot | `frontend/src/journeyLayout.ts` |
| Woven view, legend and the move, return and meaning panels | `frontend/src/components/JourneyWoven.tsx` |
| Integration: the woven path is the default; the earlier cards remain as a "Cards" fallback and are used automatically below 760 px. The existing stage panel is reused. | `frontend/src/components/Journey.tsx` |
| `?book=<id>` opens a given book, so each Journey can be linked | `frontend/src/App.tsx` |

**Unchanged:** The Weave, the API, and the backend (`backend/` and `data/` are identical to tag `m5.1-stable`).

**Data source for the screenshots:** the Milestone 5.1 database (`MOTIF_DB=data/motif.m51.db`), which has established
constructed meanings for both books. No model calls were made in this milestone.

**Deterministic rules worth knowing:**
- A return groups interpretive revisions and REFRAMES/CONTRADICTS links by (later stage, earlier stage). At most 6
  are drawn, the largest first.
- Landmarks are placed under their forming stage, then spaced at least 92 units apart (in the 1000-unit drawing) so captions never collide.
- Captions list the exact passages a meaning draws on ("passages III, VI"; "within passage IV"), compressing only
  consecutive runs.

**Tests:** 30 frontend tests (12 new: layout, landmarks, returns, moves, tentative marking, the cards fallback) and
87 backend tests pass.

## Evaluation (by inspection; no human usability test has been run)

**Screenshots** are in `docs/screenshots/m6/`:
- both overviews;
- a selected meaning with its threads lit;
- the stage, move and return panels;
- 1280×800, 1024 and 700 px;
- reduced motion;
- The Weave, unchanged.

**What the view communicates without interaction:**
- The book's arc in one line (the overview) and its 4–5 stages in order, with titles, at a glance.
- How the stages connect: three consequences and a parallel (Magi); three reinterpretations, each with a loop in the thread (Plato).
- Where the book turns back on itself. Plato has four returns, the thickest from stage II back to stage I. Magi has one, from V back to III.
- Where several parts of the book come together: six lace knots per book, with the passages each draws on.
- Where it begins and ends, and which stages changed most (knot size).

**What still needs interaction:**
- What a move, return or woven meaning actually says.
- The quotations, which are deliberately not shown on the overview.
- A landmark's statement (only its passages are captioned) and which stages feed it (faint until hovered or selected).

**Ambiguous or potentially misleading elements:**
- **Return thickness** counts recorded revisions plus reframing links. A count is not importance, and a revision and a
  link can concern the same idea. The panel states the two numbers separately.
- **Landmark position** is near, not always exactly under, its forming stage after spacing; the threads show the true
  sources.
- **"Within passage IV" meanings** still use the lace glyph, although they combine units from one passage only.
- **Knot size** reflects MORe's change score, which counts recorded changes, not narrative importance.
- **The stage titles, moves and meanings are model interpretation**, shown in blue and labelled. The drawing makes them
  look settled. Tentative moves are dashed, but none occur in the current Journeys, so that state is visible only in tests.
- **Constructed meanings have no short titles**, so the overview cannot say *what* converges, only *where*. Adding
  short titles would need new model output, which is out of scope here.

**Remaining usability limitations:**
- Below 880 px the path scrolls horizontally, and below 760 px the cards are shown instead. There is no vertical
  version of the path for phones.
- Stage selection is kept in the URL (`#stage=N`); move, return and meaning selections are not.
- The Journey for a book is one model sample. A different sample would draw a different shape (see the M5
  replicates). The view is faithful to the stored Journey, not to "the book" in general.
