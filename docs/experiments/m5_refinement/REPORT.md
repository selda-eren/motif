# Milestone 5: refining constructive meaning and memory

**Result.** The refinements work as mechanisms. Consolidation, distinct-evidence strength, the three-way basis and
richer transition evidence all behave as specified in tests and in the live runs. They did **not** clearly improve the
constructed meanings themselves:

| Run | Meanings | S | P | T | U |
|---|---|---|---|---|---|
| M4 | 17 | 9 | 7 | 1 | 0 |
| M5 replicate A | 15 | 8 | 5 | 2 | 0 |
| M5 replicate B | 14 | 7 | 4 | 3 | 0 |

(S supported and meaningful, P plausible but weak, T trivial or redundant, U unsupported.)

- **Clearer improvement:** Journey transitions now draw on stored meanings much more often, in both replicates.
- **Little change:** construction frequency fell only from 11 to 10 calls.
- **Two new problems:**
  - "explicit" swung from over-used to never used;
  - in one replicate a valid meaning was suppressed by the model's own "state consequence" label.

## 1. What changed

| Change | Where |
|---|---|
| **Triggers.** A long-range link alone no longer triggers. **R1** reinterpretation (interpretive revision, or a REFRAMES/CONTRADICTS link); **R2** bridging of *previously separate* units (no path of length ≤2 before); **R3** a state change of an *established* unit (≥2 relations other than RELATES_TO/CHANGES_STATE); **R4** extension, when a new unit touches ≥2 contributors of an existing meaning. The prompt now says "no new meaning" is normal. | `construct.py` |
| **Basis.** Explicit / inferred / speculative. "Explicit" must name the contributor whose quotation states the meaning itself (`stated_by`), or code downgrades it to inferred. Speculative proposals are recorded, not stored. | `schema.py`, `construct.py` |
| **Redundancy.** A *duplicate* (declared `reinforces`, or wording overlap ≥0.5) is **consolidated**: new contributors and quotations are added with their passage, and the new wording is kept as a reinforcement record. A repeat with no new evidence is only noted (`repeated_at`). An *overlap* (shared contributors and some wording) is stored separately and linked `overlaps`. *Independent* meanings are stored as new. No embeddings and no extra calls. | `construct.py`, `store.update_construction` |
| **Memory strength (minimal).** `strength` counts distinct contributing units, distinct passages and reinforcements with new evidence. It is never model confidence and never repetitions. The recall algorithm is unchanged. | `schema.py` |
| **Journey.** The digest shows each meaning's basis, support and reinforcements. Explain uses a meaning as transition evidence if it was formed **or reinforced** in the later stage, and asks the model to state `beyond_evidence`: what its explanation adds beyond the cited evidence. The UI adds one support line on the meaning card and shows that note in the existing caveat. | `journey.py`, `explain.py`, `Journey.tsx` |

**Tests.** 77 backend (10 new) and 18 frontend pass. The new tests cover:
- each trigger rule, including "a long-range link alone does not trigger";
- reinforcement adding distinct evidence while keeping the original wording;
- a repeat adding no strength (even at higher model confidence);
- near-identical wording being consolidated;
- overlapping and independent meanings being preserved separately;
- a reading restatement being rejected;
- the explicit/inferred/speculative handling;
- a reinforced meaning explaining the transition into its stage.

## 2. Comparison with Milestone 4

**Controls.** Upstream (perception, integration, propagation) is cache-identical in all runs. Units, relations and
revisions equal M4's exactly. Each replicate ran in its own database copy (`motif.m5.db`, `motif.m5b.db`), so B
re-samples A.

| | M4 | M5 A | M5 B |
|---|---|---|---|
| Construction calls (Magi + Plato) | 4 + 7 = 11 | 4 + 6 = 10 | 4 + 6 = 10 |
| Construction cost | $0.2026 | $0.2144 | $0.2010 |
| Construction time | 154 s | 163 s | 149 s |
| Meanings stored | 17 | 15 | 14 |
| Consolidations / repeats / rejections | 0 / 0 / 0 | **1** / 0 / 0 | 0 / 0 / **1** |
| "Explicit" meanings | 8 | **0** | **0** |
| Transitions citing a stored meaning: Magi | 3/4 | **4/4** | **3/3** |
| Transitions citing a stored meaning: Plato | 0/4 | **2/4** | **2/5** |

**Selectivity.** Construction now skips Plato P3, but Plato reinterprets *established* units at every passage from P4,
so R1 keeps firing. The offline check on M4's representations predicted 10 of 15 before any call
(`offline_trigger_check.txt`). I did not tighten R1 further, because that would have meant tuning to these two books.
The model said "no further meaning" after its first proposal at a few passages, but never declined a triggered
passage outright.

**Important meanings.**
- **Retained:** Magi G1–G4 in A; Plato L2, L3 and L5 in both.
- **Missing, as before:** L1 (perception) and L4 (construction).
- **Lost relative to M4:**
  - "the returner's ridiculed blindness becomes learnable night-vision" (M4, rated S). Absent in both replicates
    although P8 triggered.
  - "liberation as staged retraining" (M4, rated P). P3 no longer triggers.

## 3. Consolidated, reinforced and preserved interpretations

**Reinforced (Magi A, P4).** c02_1, *"Constrained by poverty, Della sacrifices one of the couple's two proud
possessions — her hair — to buy a worthy adornment for the other — Jim's watch"*, was declared reinforced. It gained
two distinct units:
- the anxious wait **clutching the chain**: "Della doubled the fob chain in her hand…";
- "I had my hair cut off and sold because I couldn't have lived through Christmas without giving you a present".

Strength went from 5 units / 3 passages to **7 units / 4 passages**. The original wording was kept, and the P4 wording
was recorded with the reinforcement.

**Repeats.** None occurred in live runs. The test suite shows that a repeat without new evidence adds no strength.

**Preserved as distinct (linked by `extends`, declared by the model).**
- Magi: the fear meaning (P4) and its resolution (P5); mutual sacrifice (P6) extends Della's sacrifice (P3).
- Plato: 6 per replicate, for example the reluctant-rulers chain P7 → P8 → P9.

**Alternative interpretations across replicates.** A kept "the two dazzles must be diagnosed" and "the philosopher's
blinking is a happy, excusable effect" as two meanings. B proposed them as one. Both are defensible.
Consolidation was not involved: the model chose how to divide them.

## 4. Lost or incorrectly combined

- **Suppressed (B, Magi P6).** The full mutual-sacrifice meaning (both sales, both gifts useless) was labelled
  `state_consequence` by the model and rejected by code. Only a narrower "useless gifts called wisest" (3 units,
  rated P) remained. The guard is right in principle; the model's label was wrong. This varies with sampling: A got it right.
- **Overlap not linked (B, Magi P3).** "Unable to afford… funds it by selling her hair" shares 3 of 4 contributors with
  c02_1, but its wording overlaps by only 0.06. The word-based overlap rule did not link them.
- **Nothing was incorrectly combined by consolidation.** The one consolidation was valid.

## 5. Explicit versus inferred

M4 labelled 8 of 17 meanings explicit, several of them only partly stated. M5 labelled **none** explicit in either
replicate, and the model never claimed explicit, so no downgrade happened. By my reading, 4–5 Plato meanings per
replicate state Socrates' own conclusions and should be explicit. These include "the State in which the rulers are most
reluctant to govern is always the best" (P8) and the two kinds of bewilderment (P5). The prompt change flipped the
bias rather than fixing the classification.

## 6. Journey

**Grounding.**
- **Magi:** every transition in both replicates cites a stored meaning.
- **Plato:** went from 0 transitions citing one to 2 per replicate.
- The `why` sentences are more explanatory. M5 A Magi:
  - "Lack of money leaves giving up a cherished possession as the only way to afford a worthy gift";
  - "Paying for love with beauty naturally creates worry about still seeming pretty to him";
  - "His difficulty absorbing the haircut explains the earlier stare";
  - "Discovery of his parallel sacrifice empties both presents of use yet proves devotion".

  M4's equivalents described sequence more than cause, for example "Longing without money turns into determined movement toward the street".

**Synthesis vs stored meaning.** `beyond_evidence` was left **empty in all 16 transitions**. Self-report does not
separate the model's own synthesis from stored meanings. The distinction is still visible structurally: cited evidence
is stored, and the rest is generated.

**Artifact.** Two Plato transitions citing only constructed meanings were marked "tentative" by code. The reason:
`CONSTRUCTED` is not listed as evidence that can show a *consequence*, a mapping choice from Milestone 4. It was not
changed after evaluation.

## 7. Sampling variation

The two replicates differ in:
- meaning counts (15 vs 14);
- whether the key Magi meaning survived;
- how Plato's P5 meanings were divided;
- Journey stage counts (Magi 5 vs 4, Plato 5 vs 6).

Differences from M4 of this size (17 → 14–15 meanings, 9 → 7–8 supported) are **within the variation between the two
M5 replicates**, so they cannot be attributed to the changes. Three changes appear in both replicates and in the
direction predicted, so they are more likely real effects:
- more transitions grounded in stored meanings;
- the disappearance of "explicit";
- Plato P3 no longer triggering.

M4 itself was a single run.

## 8. Cost and time

| | Calls | Cost | Time |
|---|---|---|---|
| Construction, replicate A | 10 | $0.2144 | 163 s |
| Construction, replicate B | 10 | $0.2010 | 149 s |
| Journey and explain (4 runs) | 8 | $0.2225 | — |
| **Total new spend, both replicates** | 28 | **$0.6380** | — |

The allowance was $2.

## 9. Remaining limitations and future research

1. **Triggering** is principled but not selective on argumentative texts that keep reinterpreting themselves. Real
   selectivity probably needs an estimate of whether anything *new* could be built, for example comparing the trigger
   units with the contributors of existing meanings, rather than more rules.
2. **Guards depend on the model's self-labels** (kind, basis, assumptions, `beyond_evidence`). They suppressed one valid
   meaning and caught no invalid one. A cheap independent check of the label, rather than the meaning, is the obvious
   next step.
3. **Overlap detection by wording** misses paraphrases with shared evidence. Contributor overlap alone may be the better
   signal for linking (not merging).
4. **Explicit vs inferred** needs per-meaning grounding: the quoted span that states the meaning, not just a unit id.
5. **Memory strength and activation (future).** Strength now counts distinct support but is not used anywhere:
   - recall ignores it;
   - only 1 of 29 meanings was reinforced, so it barely accumulates.

   A future version could make activation depend on current context (overlap of a meaning's contributors with the
   working memory) and use strength only as a tie-breaker or a decay-resistant prior. The two would stay separate, so a
   strong meaning is not always active and a weak one can be activated by context.
6. **Single-passage restatements** (Plato P4, P9) are still accepted as constructions. Requiring contributors from at
   least two passages would remove them; that is a design decision for review.

No changes were made after evaluation.
