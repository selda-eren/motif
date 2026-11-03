# Milestone 4: expectations, recorded before any model call

Written 2026-10-27, after implementation and tests and before any live run. Thresholds and trigger rules are as
committed in `backend/motif/construct.py` at this point. They are not to be tuned after seeing results.

## Design of the comparison

| Run | Integration and propagation | Construction | Note |
|---|---|---|---|
| magi_noC | Exp 3 prompts (cache hits, identical to Exp 3 run C) | off | control |
| magi_C | same (cache hits) | **on** | only new calls are construction, Journey and explain |
| plato_noC | Exp 3 prompts (new calls: Plato has not been processed with them yet) | off | control |
| plato_C | same (cache hits from plato_noC) | **on** | |

- **Construction changes nothing upstream.** It never modifies units, relations or readings, so every call before
  it is byte-identical with and without it. Differences between noC and C come only from the new operation and
  from what Journey does with it.
- **Journey and explain** are regenerated under the current code for all four runs.
- **Isolation.** The runs use their own database, `data/motif.m4.db`, copied from the Experiment 4 database so that the
  caches carry over. The budget guard is set to $1.08 already recorded + **$3.00**.

## Gift of the Magi: expected constructed meanings (reference `gift_of_the_magi/reference_evaluation.md`)

| ID | Expected | Reference |
|---|---|---|
| G1 | Mutual sacrifice: both sold their treasure for the other (P6, reaching back to P2-P3) | D2, D6 |
| G2 | The watch sale makes the chain useless; reciprocal or mirrored gifts | D5, D6 |
| G3 | Practically useless, yet valuable as love; "foolish" becomes "wisest" | D7 |
| G4 | (P3) Della turns her treasure into an adornment for his | D3 |
| G5 | Poverty is what makes the gift a sacrifice | D1 |
| — | Jim's stare explained by the ending | D4. Expected **miss**: not likely in context (activation) |

Expected duplicates to test memory: the Exp 4 run proposed the same meaning at P3 and again at P4. With memory, the P4
repeat should be rejected or not proposed.

## Plato, Allegory of the Cave: expected constructed meanings (written now, from the text; no prior reference)

| ID | Expected meaning | Passages |
|---|---|---|
| L1 | The cave is our own condition: "like ourselves" + the decoding of the cave as the visible world | P1, P4 |
| L2 | Liberation is a reorientation of an existing capacity, not new sight: the prisoner's turning around + education as turning the soul | P2-3, P6 |
| L3 | The philosopher's return is both dangerous and obligatory: ridicule and threat of death + the duty to descend and rule | P4-5, P7-8 |
| L4 | Political life is a contest over shadows: the cave's shadows + the "shadows of justice" disputed in courts and the political "fighting about shadows" | P1, P5, P8 |
| L5 | The best rulers are those who do not want to rule, because they have seen something better | P7-9 |

**Known risk.** Day 1's perception missed "fight about shadows" (P8), so L4 may be an activation or perception limit.

## What would count as failure

- Any constructed meaning rated **unsupported** that cites only associated units, or that depends on knowledge of
  later passages.
- A paraphrase of an earlier constructed meaning or stored reading accepted as new.
- Any change to units, relations or revisions between noC and C. This is checked by fingerprint.
- Journey quality worse with construction than without, judged against the same references.

## Ratings

Same scale as Experiment 4: S supported and meaningful, P plausible but weak, T trivial or redundant, U unsupported.
One rater (an AI assistant), independent of the model's confidence.
