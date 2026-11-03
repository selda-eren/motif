# Day 2: first fiction experiment, "The Gift of the Magi"

**Question.** Can MORe build evolving representations of a fictional narrative, and discover how later events
change the significance of earlier ones, without being redesigned for fiction?

**Short answer.** Partly. The unchanged pipeline followed the plot, linked the ending back to the set-up,
and revised two earlier readings at the final passage. Plato had no revisions at its last passage. But the
revisions are mostly **state updates** ("the watch is now gone") rather than **changes of significance**.
The central irony, that her chain is useless because his watch is gone, is never represented as such. The
Journey states it anyway, by composing it from separate pieces.

## Setup

- **Baseline preserved.** The Plato results are unchanged (same SHA-256 hashes). The database is backed up to
  `data/baseline/motif.plato-baseline.2026-10-26.db`, and git tag `plato-baseline` marks the baseline commit.
- **Text.** Gutenberg #7256, with the licence header and footer, title and byline removed. 2,057 words.
  `data/texts/gift_of_the_magi.txt`.
- **Segmentation.** The existing `segment()` gives 6 passages. P6 contains both reveals and the coda.
- **Reference evaluation.** `reference_evaluation.md`, written before any model call. SHA-256 is recorded in
  `reference_evaluation.sha256`, and its timestamp is 17:24:52Z, before the first call at 17:25:05Z.
- **Pipeline.** `git diff plato-baseline -- backend/` is empty. Same settings as Plato: muse-spark-1.3,
  reasoning_effort=medium, 12k output cap, 1 attempt, $2 cumulative budget.
- **Raw output.** `data/results/gift_of_the_magi.muse-spark-1.3.json` has the same shape as Plato's.
  `…raw…json` holds every request and response, the per-passage notes and working memory. The usage CSV
  and the run logs are in this folder.

## 1. What was extracted

| | Count |
|---|---|
| Units | 31 (all `observation`; 0 inferred). 12 events, 6 situations, 4 entities, 4 claims, 3 concepts, 2 images |
| Quotation grounding | 32/32 grounded, 0 rejected |
| Relations | 45, of which 32 link different passages. CAUSES 16, REFINES 11, SUPPORTS 10, RELATES_TO 4, CONTRADICTS 3, REFRAMES 1 |
| Revisions | 6: two at P3, two at P5, two at P6 |
| Merges | 1 (P5's "sold it" merged into P4's "Hair Sold for Christmas") |

## 2. Reference developments (single rater, who also wrote the key)

| | Development | Result | Where it came from |
|---|---|---|---|
| D1 | Poverty as the constraint | **Hit** | $1.87 CAUSES hair sale (P1→P3); the magi remark REFRAMES the shrunken household, with a revision (P5→P1) |
| D2 | Two treasures, watch and hair | **Hit** | Both extracted in P2 together with "Couple's Two Proud Possessions"; linked from P3 and P6 |
| D3 | Hair sold for a chain for the watch | **Hit** | Chain SUPPORTS watch (P3→P2). P2's tearful faltering is revised as "hesitation before going to sell her hair" |
| D4 | Jim's unreadable stare, explained by the ending | **Partial** | Revised at P5 as "stunned confusion … not disapproval". **Never revised at P6**, although it was in working memory there. |
| D5 | Combs for the hair that is gone | **Hit** | Combs RELATES_TO hair (P6→P2); hair sale CAUSES useless adornments (P3→P6) |
| D6 | Watch sold, so the chain is useless | **Hit by the rule, partial in substance** | Watch revised ("gone, sold … a sacrificed [possession]"), plus CONTRADICTS. **The chain is never revised**, and no relation connects the watch sale to the chain. |
| D7 | Foolish or wise: the magi | **Hit (shallow)** | Wisest REFINES the magi remark (P6→P5). The Journey ends on it. "Foolish" is never revised to "wise". |
| D8 | Della's fear answered | **Hit** | Jim's "love unchanged" SUPPORTS "Prayer for Prettiness" (P5→P4) |

By the pre-registered rules that is 7 hits and 1 partial. The rules were lenient in hindsight. The three
deepest reinterpretations, chain, stare and foolish→wise, are all weak or missing.

## 3. Missed connections and what caused them

| Miss | Cause |
|---|---|
| Watch sale → chain is useless (no revision of "Buys platinum fob chain") | **Integration.** The chain was in working memory at P6, and chain SUPPORTS watch already existed. Revising the watch did not reach units that depend on it. |
| Watch sale / combs → Jim's stare re-read | **Integration.** The stare and "Jim stunned confusion" were both recalled at P6. My prediction of a recall failure was wrong. |
| "Couple's Two Proud Possessions" ↔ "the greatest treasures of their house" (P6) | **Perception and integration.** Perception quoted only the "wisest" half of the coda sentence. The P2 unit was in memory but never linked, so the double sacrifice never forms one structure. |
| "Let's put our Christmas presents away … too nice to use just at present" (P6) | **Perception.** This is the text's own statement that both gifts are useless, and it was not extracted. |
| "You had me going a while at first" (P5) | **Perception.** Jim's own hint about the stare. |
| "This dark assertion will be illuminated later on" (P5) | **Perception (partial).** The neighbouring sentence was extracted, but the explicit forward promise was not. |
| "Love unchanged", "Chain mirrors Jim", "Anxious wait (holding chain)" not recalled at P6 | **Recall.** Not decisive here, because related units were recalled. |

**Recall was hardly tested.** At P6, 19 of the 26 earlier units were in working memory. A 6-passage story
does not stress recall. The failures that matter are in integration.

## 4. Unsupported or misleading interpretations

- **CONTRADICTS used for a change of state, three times.** The links are curls ↔ hair, useless combs ↔ hair,
  and watch sale ↔ watch. The facts are right, but the text never contradicts itself; the hair and the watch
  are later gone. Code then marks "Cascade Of Brown Hair" and "Jim's Inherited Gold Watch" as **contested**, and
  The Weave ranks these three links at the top of "Threads worth following". Plato showed the same misuse.
- **Stare reading (P5).** "Stunned confusion … that her hair is gone." This is plausible at P5, but it stays the
  current reading after the ending. The Journey's stage III then quotes the stare as frightening her "about her changed
  appearance". The surface reading survives.
- **"Magi valuable gifts" content is garbled.** It merges two sentences ("contrasts eight dollars a week with a
  million a year through the magi's gifts"). The resulting revision of the household calls the $20-a-week income the
  "eight-dollars-a-week backdrop", but $8 is the rent. Plausible overall, imprecise in detail.
- **Weak link.** "Prayer for Prettiness" SUPPORTS "Jim beloved husband".
- **Precision of the pre-registered types.**
  - CAUSES: 11 supported, 5 plausible, 0 unsupported.
  - CONTRADICTS: 3 misleading in type.
  - REFRAMES: 1 plausible.
  - Revisions: 4 supported, 2 plausible.
- **Overconfident self-assessment.** The explanation for the III→IV transition reports "No major gap", while the chain and stare
  revisions are missing.
- **No leakage found.** I checked units, relations, revisions and gists formed before P6 for knowledge of the
  ending (combs, watch sold, irony, "wise"). There was none.

## 5. Does the ending revise earlier representations?

**Yes, but literally.** P6 made 2 of the 6 revisions:
- The P5 package now reads as "the combs Jim bought with money from selling his watch". This is a supported, genuine retrospective reading.
- The P2 watch now reads as "gone, sold to pay for the combs". This records a change of state, not of significance.

Plato's last passage made **no** revisions, so this is a real difference. Fiction's late reveal did trigger
retrospective revision. What did not happen is the second-order reinterpretation: the chain, the stare, the
two treasures, and foolishness re-read as wisdom.

## 6. Does the Journey explain the narrative?

**Yes, clearly, and better than the representation underneath it.** It has 4 stages (want → sacrifice → reunion →
double reversal and magi). Transitions are classified consequence → development → reinterpretation. That matches the
reference arc, and unlike Plato it does not skew to reinterpretation. The overview sentence is an accurate
one-line retelling. Caveats:
- "Their useless gifts" (plural) is composed by the Journey step from "watch sold" plus "chain SUPPORTS watch". The
  representation never says the chain is useless.
- Stage III presents the stare as fear about her looks. Its mystery is never resolved.
- Because P6 holds both reveals and the coda, the magi reframing shares a stage with the reveals instead of being a
  final turn.

## 7. Processing time and cost

| | Calls | Input | Output (incl. reasoning) | Reasoning | Cost | Model time |
|---|---|---|---|---|---|---|
| Pipeline (perceive + integrate) | 12 ok + 1 timeout | 20,382 | 44,734 | 36,893 | $0.2156 | 230 s |
| Journey | 1 | 4,788 | 2,902 | 2,424 | $0.0183 | 13 s |
| Explain | 1 | 5,039 | 4,822 | 3,880 | $0.0268 | 24 s |
| **Total** | 15 | 30,209 | 52,458 | 43,197 | **$0.2607** | 267 s |

- **Wall clock.** About 9.5 minutes in total. Of that, about 300 s was one timed-out perception call for P3, followed by a manual resume.
- **Logging gap.** The local log records the timeout as 0.0 s and $0. If the server finished generating and billed it, up to about $0.05 more may appear on the provider's bill. Check the dashboard.
- **Database total.** $0.5877 of $2.00, including Plato's $0.3721.
- **No cache hits.** 0 cached tokens; every call was new.

## Plato vs. Magi

| | Plato, *Allegory of the Cave* | O. Henry, *Gift of the Magi* |
|---|---|---|
| Genre / words / passages | Philosophical dialogue / 2,895 / 9 | Fiction / 2,057 / 6 |
| Units (inferred) | 46 (1) | 31 (0) |
| Dominant unit kinds | claims 18, events 10 | events 12, situations 6 |
| Relations (cross-passage) | 73 (51) | 45 (32) |
| Dominant relation types | REFINES 26, SUPPORTS 23, REFRAMES 9 | CAUSES 16, REFINES 11, SUPPORTS 10, REFRAMES 1 |
| CONTRADICTS (contested units) | 2 (2) | 3 (2) |
| Revisions (at last passage) | 13 (0) | 6 (2) |
| Grounding | 100% | 100% |
| Journey stages / transitions | 5 / dev, reint, reint, reint | 4 / consequence, development, reinterpretation |
| Cost / per 1k words | $0.372 / $0.128 | $0.261 / $0.127 |
| Model time | 235 s | 267 s (+ ~300 s timeout) |

## The most important limitation

**Revisions do not propagate along the representation's own dependencies.** When P6 revised the watch,
nothing re-examined the units whose meaning depended on it. The chain was linked to the watch with SUPPORTS, and
the stare was the unexplained reaction to the gift. Both were in working memory, and both kept their pre-ending
readings. Integration judges each new unit against earlier units one at a time. It does not ask "what else now
reads differently because this changed?" In fiction, retrospective meaning is mostly that second-order effect,
so the system catches the reveal but not what the reveal does to everything else.

A close second, which recurs in both books: **CONTRADICTS is used for a change of state over time.** It marks
the hair and the watch as "contested" and pushes those links to the top of The Weave.

Neither was changed during this experiment.
