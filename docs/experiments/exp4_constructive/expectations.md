# Experiment 4: expectations and activation check, recorded before any model call

Written 2026-10-27. The frozen inputs are listed in `activation_check.txt`. They are the exact user messages of
Experiment 3's propagation calls, plus one constructed negative control built with the same functions.

- **Objective A (revision-oriented)** is Experiment 3's request, unchanged. It should come from the cache with the
  recorded verdicts.
- **Objective B (constructive)** uses the same user message with a new system prompt and schema. Both use
  muse-spark-1.3 at medium effort with a 12k output cap.

## Rating scale (applied by me, a single rater, independently of the model's confidence)

| Rating | Meaning |
|---|---|
| **S** | Supported and meaningful: needs at least two units, is backed by their quotations, and is not already in the representation. |
| **P** | Plausible but weakly supported. |
| **T** | Trivial or redundant: restates one unit, or a reading or revision already stored. |
| **U** | Unsupported: not backed by the shown units, uses knowledge of later passages, or is a mere association. |

The rating must also say whether a state consequence was labelled as meaning, or the reverse.

## Expected meanings, and whether the frozen input can support them

| ID | Case | Expected meaning | Units needed | In frozen set? |
|---|---|---|---|---|
| M1 | magi_p6 | **Mutual sacrifice**: each sold their treasure for the other | hair sale u02_1, watch sale u05_4 (+ possessions u01_2) | **yes** |
| M2 | magi_p6 | Watch sale changes the **practical significance of the chain** | chain u02_3, watch sale u05_4 | **yes**, but the chain already has this reading from integration (Exp 3). A restatement rates **T** unless it adds something. |
| M3 | magi_p6 | **Practically useless, symbolically valuable** gifts | useless combs u05_2, chain u02_3, wisest u05_5 | **yes** (the P5 magi remark u04_3 is not shown) |
| M4 | magi_p6 | **Mirrored gifts**: combs for hair that is gone, chain for a watch that is gone | u05_1/u05_2, u01_4, u02_3, u01_3 | **yes** |
| M5 | magi_p6 | Jim's earlier stare explained by his own sacrifice | stare u03_4, confusion u04_1, package u04_4 | **no: activation limitation** (none of the three shown) |
| M6 | magi_p3 | Della turns her own treasure into an ornament for his (optional) | u02_1, u02_3, u01_3, u01_2, u00_5 | **yes** |
| S1 | bridge_p3 | Practical consequences (doctor, post, festival cut off), labelled **state_consequence** | u01_1, u01_5, u01_3, u00_1, u02_6 | **yes** |
| S2 | bridge_p3 | Seal's symbolic reading **preserved** (no challenge; "now commemorates loss" would be U) | u00_3 | **yes** |
| S3 | bridge_p3 | **Neglect, not the flood alone, caused the town's division** (false survey + no inspection + rot + a sound bridge would have survived) | u00_6, u02_3, u02_4, u02_5, u02_1 | **yes** |
| S4 | bridge_p3 | Market income, school walk, cold-store loan, wheelchair clinic | not shown | **no: activation limitation**. Any interpretation about them rates U. |

## Negative and low-expectation cases

| Case | Expectation |
|---|---|
| **control_library_p2** (constructed) | A change in opening hour, and linked units that are merely associated (maps, fishing rods, a new carpet). **No new meaning.** Any proposal rates U or T. |
| **magi_p4** | Mostly nothing new. Hair loss, curls and the prayer are already linked. A link between Della's fear and the cost of her sacrifice would be P at most. |
| **magi_p5** | Nothing new, or redundant (the stare is already reread as stunned confusion). **Leakage check:** anything implying Jim also sacrificed something, or that his gift concerns her hair, uses knowledge of P6 and rates U. |

## Success criteria (informal, small sample, single run each)

- **B is useful** if it finds M1, plus at least one of M3/M4 and S3, with at most one U across all cases, and
  proposes nothing (or only T) on the library control.
- **B is harmful** if it challenges the seal, leaks the ending at P5, or rates U more often than S.
- **Non-mutation:** the representation fingerprint of the experiment database must be identical before and after.
