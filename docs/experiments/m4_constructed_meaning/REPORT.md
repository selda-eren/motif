# Milestone 4: Constructed Meaning in MORe

**Result.** One new operation, construction, now builds persistent higher-level meanings from several unchanged
units, reactivates them at later passages, and makes them available to the Journey.

| | Gift of the Magi | Plato | Total |
|---|---|---|---|
| Constructed meanings | 5 | 12 | **17** |
| Supported and meaningful (S) | 3 | 6 | **9** |
| Plausible but weak (P) | 2 | 5 | **7** |
| Trivial or redundant (T) | 0 | 1 | **1** |
| Unsupported (U) | 0 | 0 | **0** |
| Rejected by code (duplicates or guards) | 0 | 0 | 0 |

- **Observations unchanged.** Units, relations and revisions are identical with and without construction, and the
  observations equal the Day 1 and Day 2 baselines.
- **Cost.** $0.20 for construction, $0.72 for the whole milestone (allowance $3).

Caveats:
- The guards and the deterministic duplicate check were **never exercised** by live data.
- Triggering turned out **not selective**: construction ran at 11 of 15 passages.
- One rater, one run per condition.

## What was built

| | Where |
|---|---|
| `Construction` type, `constructions` table: statement; ≥2 contributors with roles; relationship; basis (explicit/inferred); relation to existing (new/supplements/challenges/extends + id); justification; limitations; model confidence (labelled as such); evidence snapshot (verbatim quotes from passages read by then); passage where it became possible; trigger rules | `schema.py`, `store.py` |
| Construction operation, its triggers, context, reactivation, validation and duplicate check (rules documented in the module docstring) | `construct.py`, called from `pipeline.py` after propagation; `MOTIF_CONSTRUCT=0` disables it |
| Journey: digest lists constructed meanings; stages cite them (`key_meanings`, checked against the stage's passages); explain can use them as transition evidence | `journey.py`, `explain.py` |
| UI: a stage panel shows each cited meaning with its contributors, their roles and quotations, and its limits. No other UI change | `Journey.tsx`, `types.ts` |
| Tests: 9 backend (persistence; observations untouched; invalid contributors; later-passage leakage; duplicates of meanings and readings; coexisting meanings; extension link; state consequences and assumptions rejected; "no new meaning"; runs only when triggered, once, never on its own output) + 1 frontend | `tests/test_construct.py`, `App.test.tsx` |

**Suite:** 67 backend and 18 frontend tests pass.

**Trigger rules (T1–T5).**
- T1: a long-range link (two or more passages back).
- T2: a REFRAMES or CONTRADICTS link.
- T3: an interpretive revision.
- T4: a new unit bridging two previously unlinked units.
- T5: a state change to a unit that already had at least 2 relations.

**Limits.** 14 earlier units in context, 4 reactivated meanings, at most 2 accepted per passage, 1 call per passage.
Constructed meanings are never contributors and never triggers.

## Controlled runs

- **Isolation.** All runs used `data/motif.m4.db`, a copy of the Experiment 4 database.
- **Identical upstream.** Construction changes nothing upstream, so the runs with it (C) replay the runs without it
  (noC) from the cache, call for call. The differences are attributable to the new operation alone.
- **The Magi control run** reproduces Experiment 3's run C exactly, at $0.
- **Baselines untouched.** The baseline and Experiment 3 and 4 files are unchanged, and all 7 baseline hashes match.

| Run | Integration and propagation | Construction | Journey and explain | Total | Wall |
|---|---|---|---|---|---|
| Magi noC | cache ($0) | — | $0.0420 | $0.0420 | 34 s |
| Magi C | cache ($0) | 4 calls, **$0.0669**, 55 s | $0.0511 | $0.1180 | 95 s |
| Plato noC | 15 new calls, $0.3140 | — | $0.0556 | $0.3696 | 307 s |
| Plato C | cache ($0) | 7 calls, **$0.1357**, 100 s | $0.0592 | $0.1949 | 135 s |
| **Total** | | **$0.2026** | | **$0.7245** | |

**Relative cost of construction.** It adds about 25% to the Magi pipeline ($0.265 for perception, integration and
propagation) and about 30% to Plato's. Per call: $0.017–0.022, 12–17 s.

## The constructed meanings (selection; all 17 are in `ratings.json` and the exports)

**Magi c05_1 (P6, S), extends c02_1.** *"Having each sold the proud possession the other's gift was meant to adorn, Jim
and Della leave both gifts materially useless, and that mutually cancelling sacrifice is declared the wisest giving of all."*

| Contributor | Role | Quotation |
|---|---|---|
| Della sells her hair | removes the use for the combs | "Twenty dollars," said Madame… (P3) |
| Jim's Watch Sale | removes the use for the chain | "I sold the watch to get the money to buy your combs" (P6) |
| Useless Coveted Adornments | the combs' uselessness | "…the tresses that should have adorned the coveted adornments were gone" (P6) |
| Buys platinum fob chain | the chain without a watch | "Twenty-one dollars they took from her for it…" (P3) |
| Wisest Foolish Givers | the narrator's revaluation | "of all who give gifts these two were the wisest" (P6) |

This one meaning covers mutual sacrifice, the chain's lost practical use, and practical uselessness against value
as love.

**Magi c02_1 (P3, S).** *"Unable to honor Jim through saving, Della sacrifices her own proud possession to dignify
his, making devotion measurable by self-cost rather than money."* It draws on the savings, the desire, the two
possessions, the hair sale, the chain and the watch, across P1–P3.

**Plato c07_2 (P8, S), extends c03_1.** *"The darkness-blindness that made the returner ridiculous becomes learnable
night-vision that fits hive-bred philosophers to govern."* It links P4 ("coming suddenly out of the sun to be
replaced in his old situation") to P8 ("must go down to the general underground abode").

**Plato c05_1 (P6, S).** The cave's painful turning (P1–P2) is reread through education as turning an existing sight
(P6): *"not implanting the faculty of sight, for that exists already"*.

**Weakest.**
- **Plato c08_2 (T):** all four contributors are from P9 and restate its argument.
- **Plato c04_2 (P):** adds "not arrogance", which no unit supports.
- **Magi c03_1 (P):** "inseparable" overclaims.

## Expected meanings (pre-registered in `expectations.md`)

| Magi | | Plato | |
|---|---|---|---|
| G1 mutual sacrifice | ✓ c05_1 | L1 the cave is our condition | ✗ **perception**: no "like ourselves" unit exists |
| G2 chain useless / mirrored gifts | ✓ c05_1 | L2 liberation = reorientation | ✓ c05_1 |
| G3 useless yet valuable; foolish → wisest | ✓ c05_1 | L3 the return is dangerous and obligatory | ✓ c03_1, c06_1, c07_2 |
| G4 her treasure adorns his | ✓ c02_1 | L4 politics as a contest over shadows | ✗ **construction**: the units were in context at P5, P7, P8, P9 |
| G5 poverty makes the gift a sacrifice | ✓ c02_1 | L5 reluctant rulers are best | ✓ c07_1 |
| Jim's stare explained by the ending | ✗ **activation**: not in the P6 context | | |

## Duplicates and the guards

- **Rejections.** None. The model proposed 17 meanings and code accepted all 17.
- **Assumption and state-consequence checks.** The model never declared an assumption and never proposed a state consequence.
- **Deterministic duplicate check.** It never fired. The closest pair of accepted meanings shared 0.16 of their words,
  against a threshold of 0.5.
- **Paraphrases.** None among the accepted meanings, by manual review.
- **Prompt-level memory did the work.** 10 of 17 meanings were declared extensions of a reactivated earlier meaning.
  The Experiment 4 repeat at Magi P4 did not recur: at P4 the model extended c02_1 with a new aspect.
- **What this shows.** The code-level safeguards are untested by live data (they are tested only with scripted
  inputs). The structural checks also cannot catch an unsupported framing inside an otherwise grounded meaning (Plato
  c04_2). As expected, structure does not establish semantic correctness.

## Reactivation (higher-level memory)

Earlier meanings were reactivated at every triggered passage after the first: Magi P4–P6, Plato P4–P9. They were
used as context for extension. For example, Plato c08_1 extends c07_1, which extends c06_1. No meaning was used as
a contributor, so nothing recursed. Everything shown came from passages already read, which the test suite checks.

## Journey with and without constructed meanings

| | Gift of the Magi | Plato |
|---|---|---|
| Day 1/2 baseline | 4 stages; ends "Mutual Sacrifice Proved Wisest" (reinterpretation via 2 revisions) | 5 stages, 3 reinterpretations |
| noC (current code) | 4 stages; last transition "mutual useless gifts expressing wise love" (revision, causes, state change) | 4 stages |
| **C** | 5 stages; **3 stages cite constructed meanings**; **3 of 4 transitions cite one**. Last: *"Seemingly foolish unusable gifts come to mean the wisest love through mutual sacrifice"*, backed by c05_1 and its 5 quotations | 5 stages; **4 stages cite 7 meanings**; **no transition cites one**; new stage "Diagnosing Blindness, Turning Soul" (c04_1, c05_1) |

**Judgement.** The Journey *text* is not clearly better: the Magi baseline already said "mutual sacrifice" from pairwise
links. The gain is **traceability**. The ending's reinterpretation now points to one stored meaning with its
contributors and quotations (screenshot: `magi-journey-stage-5.png`), instead of being composed by the Journey step.

## What came from the new operation, and what from existing LLM reasoning

**From the new operation:**
- 17 persistent, reusable meanings, 9 rated supported. None existed as representations before.
- Meanings such as "the returner's blindness becomes learnable night-vision" (P4 → P8) existed nowhere in the
  representation.
- Explicit contributors with roles, and evidence snapshots.
- Reactivation at later passages.
- The Journey and explain can cite them.

**From existing LLM reasoning:**
- The interpretive insight itself. Given the constructive question, the model does the combining.
- The Journey's narrative, which was already good without construction.
- In practice, the duplicate avoidance, through prompt-level memory, not the deterministic check.

**Not attributable to either:** the misses come from activation (the stare), perception ("like ourselves") and
construction (shadows and politics).

## Issues found (not fixed: no changes after evaluation)

1. **Triggering is not selective.** T1 (a long-range link of any type except RELATES_TO) fires at almost every passage after
   P2. Construction ran at 4 of 6 and 7 of 9 passages and never answered "no new meaning". The rules are explicit
   but too permissive.
2. **Guards are passive.** The model never reports assumptions, so the assumption guard never fires. The only
   unsupported framing ("not arrogance") passed. A semantic check remains an open question.
3. **Single-passage restatements pass.** c08_2 cites four units from one passage. The anchor rule does not require
   contributors from two or more passages.
4. **The basis label is generous.** "Explicit" was used where only part of the meaning is stated (Magi c05_1).
5. **Construction misses with evidence present.** Plato L4 (shadows → courts and politics).

## Recommendation for review

Keep the operation; it is stable, cheap, and produced no unsupported meanings in these runs. Before the next
milestone, the decisions worth making are:
- tighter triggers, for example T1 only for REFRAMES/CAUSES/CHANGES_STATE, or a minimum confidence;
- whether to require contributors from at least two passages;
- whether a review step is worth one extra call for the "challenges" and "explicit" labels.

None of these was implemented.
