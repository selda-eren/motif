# Milestone 5.1: stabilizing MORe before UI development

**Result.**
- A valid meaning can no longer be lost because of the model's own category label: it is kept as **pending**.
- "Explicit" now requires verified words from the text.
- A constructed meaning supports only the Journey transitions its own content shows.

All behaviour was verified on **saved model outputs** first. The one live run cost **$0.33** and confirmed that
nothing regressed.

One problem remains: the model still never *claims* "explicit". Below, verification is shown to work, but it only
runs when the model makes the claim.

## 1. Fixes

| Problem (M5) | Fix | Where |
|---|---|---|
| A valid meaning was discarded because the model labelled it `state_consequence` | The category is resolved, not trusted. A **pure fact** (relation "new", only event/situation/entity contributors) is withheld as before. An **ambiguous** label (it extends, reinforces, supplements or challenges an interpretation, or draws on a claim, concept or image) is stored with `status: "pending"` and a reason. Pending meanings are never reactivated, never trigger extension, and never reach the Journey digest, stage citations or transition evidence. They become established only if a later valid proposal duplicates them. | `construct.classify_state_consequence`, `apply` |
| Structurally invalid and speculative proposals | Checked **first**, regardless of category; still rejected | `construct.apply` |
| "Explicit" over-used (M4) or never used (M5) | Explicit requires `stated_quote`. Code checks that it occurs **verbatim** in a passage already read that a contributor comes from, and that the meaning **echoes** it (at least 2 shared content words and at least half of the quote's own). Otherwise the basis is inferred and the downgrade is recorded. The verified quote is stored with the meaning. | `construct.verify_explicit_quote` |
| Transitions backed by constructed meanings marked tentative | `CONSTRUCTED` is removed from the fixed compatibility table. Each meaning's supportable kinds are derived from **its own recorded relationship** (cause → consequence, parallel/mirror → analogy, contrast/reframe → reinterpretation, extends/part-and-whole → development, challenge → contradiction), plus reinterpretation cues in its statement. A transition stays tentative when its cited meaning does not show that kind. | `explain.construction_supports`, `shows` |
| Redundancy | Unchanged from M5: consolidation, overlap links and strength metadata are preserved | — |

No new representation types, recall changes, triggers or UI were added. One field was added (`status`, with its
reason), plus the verified quote. Perception, recall and integration are untouched.

## 2. Regression tests

**Results:** 87 backend (10 new in `test_m51_regressions.py`, 1 rewritten) and 18 frontend tests pass.

| # | Required | Test |
|---|---|---|
| 1 | Mutual sacrifice from M5 replicate B | `test_saved_mutual_sacrifice_proposal_is_kept_as_pending_not_discarded`: replays the **saved** response against the store rebuilt from the replicate-B export |
| 2 | Explicit with exact quotation | `test_explicit_requires_exact_words_that_state_the_meaning`, `..._only_supports_a_component_...`, `..._passage_not_yet_read_...` |
| 3 | Inferred from combined evidence | `test_inferred_meaning_from_combined_evidence_is_established` |
| 4 | Ambiguous classification not established | `test_state_consequence_labels_are_resolved_or_kept_pending`, `test_pending_meaning_is_never_presented_as_established`, `test_a_later_valid_duplicate_confirms_a_pending_meaning` |
| 5 | Constructed meanings supporting transitions | `test_a_constructed_meaning_supports_only_the_transitions_its_content_shows`, `test_transition_validation_uses_what_the_constructed_meaning_shows` |
| 6 | Unsupported still rejected | `test_unsupported_proposals_are_still_rejected` (speculative, assumptions, one contributor, no anchor, speculative state consequence) |
| 7 | Observations and overlapping meanings unchanged | Fingerprint and earlier-meaning checks in test 1; M5 overlap and coexistence tests still pass |

## 3. The mutual-sacrifice proposal

**Saved output (M5 replicate B, Magi P6).**
> "Della and Jim have each sold the possession the other's gift was meant to adorn, leaving both the chain and the
> combs unusable."

| Field | Value |
|---|---|
| kind | `state_consequence` |
| relation | `extends c02_1` |
| contributors | hair sale, watch sale, useless combs, chain |

**Replayed with the new code:**
- It is stored as **pending**, with the reason *"labelled a state consequence, yet it extends an existing interpretation"*, and all four contributors.
- The second proposal from the same call is established as before.
- Units and the earlier meanings are byte-identical.
- It is excluded from the Journey digest, reactivation and transition evidence.

**Across all saved M4 and M5 runs** (6 runs, 29 construction calls), this was the **only** proposal ever labelled a
state consequence.

**Live run (M5.1).** The model labelled it correctly this time. It was established as c05_1: *"Motivated by love, Jim
and Della each sacrifice their proudest possession to buy the other a gift, leaving both the chain without a watch and
the combs without hair presently unusable."* It is built from the hair sale, the watch sale, the useless combs and the
chain, and the final Journey transition cites it as **analogy, supported**.

## 4. Explicit and inferred

**Unit tests:**
- A verbatim, on-topic quotation keeps "explicit" and stores the quotation.
- A quotation not in the text is downgraded.
- A quotation of a mere component fact (shared names only) is downgraded.
- A quotation from a passage not yet read is never found.

**Live run.** The model did not claim "explicit" once (0 of 17), so no downgrade occurred. By my reading, four
meanings state the text's own conclusion and *should* be explicit:

| Meaning | Echo of the stating sentence (≥ 0.5 passes) |
|---|---|
| Plato c07_2, "reluctance makes rulers best" | "the State in which the rulers are most reluctant to govern is always the best…": 0.45 for the full sentence; the clause alone passes |
| Plato c07_1, "compulsion not unjust" | "there will be no injustice in compelling our philosophers…": 0.5 |
| Plato c08_2 | "the only life which looks down upon the life of political ambition is that of true philosophy": 0.83 |
| Magi c05_2 | "Of all who give and receive gifts, such as they are wisest": 0.5 |

So verification would accept them if they were claimed.

**Inferred meanings** such as c05_1 (mutual sacrifice) and Plato c05_1 (education as turning) are correctly inferred.

**Weakness.** A short factual sentence that an inferred meaning happens to echo ('"I buy hair," said Madame': 0.67)
would also pass *if* the model offered it as the explicit quotation. The check confirms that the words exist and that
the meaning restates them. It cannot confirm that they state the meaning.

**Disclosure.** I first measured coverage against the meaning's words (40%). An offline check of the live outputs
showed that this rejects real explicit statements, because constructed meanings elaborate. I changed it to the
quotation's words before committing. That changed code validation, not prompts, and no rerun was needed: no
explicit claims were made.

## 5. Journey transition evidence

**Saved M5 explanations, re-validated** (candidate numbering verified identical to the saved prompts):
- **Plato B T3→4** (consequence, citing c06_1, whose relationship records cause and consequence): tentative →
  **supported**.
- **Plato A T3→4** (consequence, citing meanings whose relationships record contrast and extension): stays
  **tentative**, correctly.
- All other transitions citing meanings were already supported and remain so.

**Live run.**

| Book | Transitions citing a meaning | Kinds and meaning content |
|---|---|---|
| Magi | 3 of 4, all supported | consequence ← c02_1 (causal chain); consequence ← c03_1 (cause and consequence); analogy ← c05_1 (parallel and reciprocal) |
| Plato | 0 of 3 | all three transitions were reinterpretations backed by REFRAMES links and revisions. M5 had 2 per replicate, so this is likely sampling variation. |

**Stored meaning vs Journey synthesis.** The `beyond_evidence` self-report was again empty in every transition. The
distinction stays structural:
- cited evidence items are stored and marked as constructed meanings, with quotations;
- sentences are generated (blue in the UI).

## 6. Live run summary (one sample)

Upstream (perception, integration, propagation) is cache-identical to M4 and M5, and units, relations and revisions
are unchanged.

| | Magi | Plato |
|---|---|---|
| Construction calls | 4 | 6 |
| Meanings: established / pending | 6 / 0 | 11 / 0 |
| Consolidations (reinforcements with new units) | 1 (c02_1 at P4, +2 units) | 1 (c05_1 at P7, +2 units) |
| State consequences withheld; rejected | 0; 0 | 0; 0 |
| Explicit / downgraded | 0 / 0 | 0 / 0 |
| My ratings (S/P/T/U) | 3/3/0/0 | 5/4/2/0 |

**Totals.** S 8, P 7, T 2, U 0, out of 17, in line with M4 (9/7/1/0) and M5 (8/5/2/0, 7/4/3/0).

**Weakest.**
- Plato c04_2 gives a reason for the philosopher's unwillingness ("because return means painful blindness") that is not
  the text's stated reason (rated P).
- Single-passage restatements (Plato c03_1, c08_2) remain (T).

## 7. Remaining limitations

1. **The model never claims "explicit"** in M5 or M5.1. Verification is in place, but the classification is only as
   good as the model's willingness to make the claim.
2. **Structural checks are not semantic checks.** Pending resolution uses deterministic signals, and the quote check
   tests that words exist and are echoed, not that they state the meaning.
3. **Transition-kind cues** come from the model-written `relationship` text, which is a keyword heuristic.
4. **`beyond_evidence`** is never self-reported.
5. **Unchanged from M5:** triggering is not selective on Plato; overlap detection by wording is weak; single-passage
   restatements are accepted.

## 8. Cost

| | Calls | Cost |
|---|---|---|
| Live verification: construction (Magi 4, Plato 6) | 10 | $0.2017 |
| Journey and explain (2 books) | 4 | $0.1256 |
| **Total new spend** | 14 | **$0.3272** (limit $1) |

Everything else used saved outputs, at no cost.
