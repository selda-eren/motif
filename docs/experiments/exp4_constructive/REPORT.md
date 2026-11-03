# Experiment 4: constructive meaning emergence

**Question.** Can new meaning emerge when existing representations become active together, without those
representations changing?

**Short answer, on a small sample.** Yes. Given the same frozen inputs:
- The revision question produced **0 interpretations** (23 verdicts; 2 state updates).
- The constructive question produced **11 proposals**:

| Rating | Count |
|---|---|
| Supported and meaningful (S) | 4 |
| Plausible but weakly supported (P) | 3 |
| Trivial or redundant (T) | 3 |
| Unsupported (U) | 1 |

It also returned "no new meaning" on the negative control. It found mutual sacrifice, the reciprocal uselessness of
the gifts, and the footbridge's preventable loss, and it modified nothing. The single unsupported proposal is the
risk we predicted: a symbolic leap about the town seal.

This is one run per case, rated by one rater (me). It is evidence, not validation.

## Setup (controlled comparison)

- **Frozen input.** Each case is the *exact user message* that one of Experiment 3's propagation calls sent: Magi P3–P6
  and footbridge P3, read from `docs/experiments/exp3_propagation/*.raw.json`. A sixth case, **control_library_p2**,
  is a negative control: an opening-hour change whose linked units are merely associated. It is built with Experiment
  3's own functions. Recall, traversal, depth and candidate selection are therefore identical by construction.
- **A, revision-oriented.** Experiment 3's request, byte for byte. All five real cases came back as **cache hits** with
  the recorded verdicts. Only the control needed a new A call.
- **B, constructive.** The same user message, with a new system prompt and output schema. Each proposal has:
  - a statement;
  - at least 2 contributing units, with what each contributes;
  - the relationship among them;
  - `emergent_meaning` or `state_consequence`;
  - supplements, challenges or new, plus which existing reading it concerns;
  - a justification, limitations, and confidence.
- **Validation by code.** Contributing ids must be among the units shown, and at least 2 must remain; 0 proposals were
  rejected. Evidence is the stored, verbatim quotations of the contributing units, limited to passages already read.
- **Same settings.** muse-spark-1.3, reasoning effort medium, 12k output cap.
- **Non-mutation.** The representation fingerprint of `data/motif.exp4.db` is identical before and after. Nothing was
  written except the model cache and the usage log.
- **Code.** `backend/motif/experimental/` (not called by the pipeline or the API). 4 new tests cover:
  - identical input to both objectives;
  - contributors restricted to the frozen set;
  - quotations from passages already read only;
  - non-mutation;
  - an empty answer.

  All 58 tests pass.

## 1. Side by side

| Case | A: revision-oriented | B: constructive (rating) |
|---|---|---|
| magi_p3 | 4 × unchanged | **S** Della sacrifices her proud possession to adorn his · **P** poverty + desire make the hair sale the only route ("only" overclaims) |
| magi_p4 | 2 × unchanged | **T** same as p3's first proposal, again · **P** loss of beauty → fear she is no longer pretty, unresolved by the stare |
| magi_p5 | 4 × unchanged | **T** restates the stare's stored reading · **P** both now have gifts: a mutual exchange (no leakage of the ending) |
| magi_p6 | 7 × unchanged | **S** reciprocal pair of unusable gifts · **S** mutual sacrifice reframed from foolish loss to wisest giving |
| bridge_p3 | doctor: state update · post: state update · seal: unchanged | **S** neglect, not the flood alone, caused the loss · **T** doctor and post cut off (correctly labelled `state_consequence`) · **U** seal and festival become "reminders of division" |
| control | 2 × unchanged | *no new meaning*: "shares only general library topic" |
| **Totals** | 23 verdicts, 2 state updates, 0 interpretations | 11 proposals: **4 S, 3 P, 3 T, 1 U**; control correct |

## 2. The supported meanings, with evidence

**magi_p6 · reciprocal unusable gifts** (S; chain, useless combs, hair sale, watch sale; passages 3 and 6)
> "Della's fob chain and Jim's combs form a reciprocal pair of unusable gifts whose matching uselessness turns
> material failure into evidence of mutual love."

Evidence:
- "Twenty-one dollars they took from her for it…" (P3)
- "And now, they were hers, but the tresses that should have adorned the coveted adornments were gone" (P6)
- "Twenty dollars," said Madame… (P3)
- "I sold the watch to get the money to buy your combs" (P6)

It *supplements* the chain's stored reading, which already said "mirroring the combs". What it adds is the cross-causal
structure: each sacrifice disables the *other's* gift.

**magi_p6 · mutual sacrifice, foolish → wisest** (S; two proud possessions, hair sale, watch sale, wisest givers;
passages 2, 3 and 6)
> "The deliberate sacrifice of both mighty prides — hair and heirloom watch — is reframed from foolish loss into wisest giving."

Evidence:
- "two possessions … in which they both took a mighty pride" (P2)
- the two sales (P3, P6)
- "of all who give gifts these two were the wisest" (P6)

Before this, the representation held only a RELATES_TO link and a SUPPORTS link.

**magi_p3 · Della turns her treasure into an adornment for his** (S; possessions, watch, hair sale, chain, chain-like-Jim;
passages 2 and 3). The stored representation had only pairwise links.

**bridge_p3 · preventable loss** (S; survey, no inspection, rot, "a sound bridge would probably have survived";
passages 1 and 3). It *supplements* the "discredited survey" reading: the town's division follows from neglect,
not from the flood alone.

## 3. Successes, failures, false associations, missed meanings

| Expected (pre-registered) | Result |
|---|---|
| M1 hair sale as one half of mutual sacrifice | ✓ magi_p6 #2 |
| M2 watch sale changes the chain's practical significance | ✓ magi_p6 #1, but already in the chain's stored reading (from integration in Exp 3) |
| M3 practical uselessness vs. symbolic value | ✓ magi_p6 #1 ("material failure into evidence of love") and #2 |
| M4 mirrored gifts | ✓ magi_p6 #1 |
| M6 Della adorns his treasure with hers | ✓ magi_p3 #1 |
| S1 practical consequences labelled as state, not meaning | ✓ correctly labelled; redundant with A |
| S2 seal's symbolic reading preserved | **Partial.** Not challenged, but an unsupported "reminder of division" reading was added |
| S3 preventable loss | ✓ |
| Control: no meaning | ✓ |
| P5: no leakage of the ending | ✓ |
| P4: little or nothing new | ✗ over-generation: 2 proposals, one a duplicate |

- **False association.** One: bridge #3, the symbolic leap. Its model confidence was the lowest of the run (0.68),
  but confidence did not separate S from T or P elsewhere. For example, the redundant T proposals scored 0.85–0.9.
- **Redundancy.** 3 proposals were trivial or redundant:
  - a re-proposal of an earlier case's meaning (the harness has no memory of earlier constructions);
  - a restatement of a stored reading;
  - a duplicate of A's state updates.
- **Existing interpretations preserved.** B marked nothing as "challenges", and the fingerprint shows no change.

## 4. Activation failures vs. meaning-construction failures

| Miss | Type | Why |
|---|---|---|
| Jim's stare explained by his own sacrifice (M5) | **Activation** | The stare, his confusion and the package are not in the P6 frozen set (two links away) |
| Footbridge market income, school walk, cold-store loan, wheelchair clinic (S4) | **Activation** | Not in the frozen set (no links in the graph); B correctly made no claims about them |
| Seal and festival as "reminders of division" | **Construction** | Unsupported symbolic inference from available units |
| Duplicate and restated proposals (p4 #1, p5 #1, bridge #2) | **Construction** | No dedup against earlier constructions or stored readings |

No expected meaning whose evidence *was* in the frozen set was missed.

## 5. Cost and runtime

| | Calls | Input | Output | Reasoning | Cost | Model time |
|---|---|---|---|---|---|---|
| A, Exp 3 originals (5 cases) | 5 | 14,091 | 10,038 | 8,212 | $0.0603 | 58 s |
| A, control (new) | 1 | 1,132 | 981 | 836 | $0.0056 | 5 s |
| **B, constructive (6 cases)** | 6 | 16,459 | 19,561 | 15,060 | **$0.1037** | **100 s** |

- **New spend.** This run cost $0.1093, wall clock 105 s. The experiment database total is $1.08 of the $2.00 guard.
- **Cost relative to A.** B costs about 1.6× A per case, and about 1.8× the output tokens.

## 6. Recommendation

**Constructive interpretation deserves its own operation, and probably its own representation type**, separate from
revisions. The type would be a higher-level interpretation that references at least 2 units and leaves them unchanged.

- **The question decides the outcome.** On identical inputs it produced the meanings the revision question could not
  (4 S, against 0), and it stayed quiet on the control.
- **The meaning is genuinely joint.** Every proposal spanned at least 2 passages, and the best ones combined units that
  had only pairwise links before.

Before integrating it, three issues need deciding:
1. **Memory of constructions.** Without it, the same meaning is re-proposed at later passages (p4 #1). New
   interpretations should be checked against existing ones and stored readings.
2. **A guard on symbolic leaps.** For example, require that a symbolic claim be backed by a contributing unit that
   is itself about meaning or symbol, not only by facts. Rate this on a held-out text.
3. **When to run it.** P4 and P5 produced mostly P and T. Running only where integration made an interpretive change
   would cut cost and noise, but that is untested.

Activation still bounds what can emerge: Jim's stare and four footbridge dependents were never available. That is a
recall and graph problem, separate from this operation.

Not done (by design): no integration into the pipeline or UI, no change to recall or depth, a single sample per case.
