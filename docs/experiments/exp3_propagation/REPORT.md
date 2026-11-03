# Experiment 3: selective reconstructive reactivation

**Question.** When a representation changes, can MORe find the representations that depend on it and reinterpret
them in a way that is evidence-grounded and selective?

**Short answer.**
- **The state-versus-meaning distinction worked.** All three changes over time in the story stopped being
  contradictions, and no unit is wrongly "contested" any more.
- **Propagation was precise but did almost nothing.**
  - Across 2 texts it reconsidered 21 candidates and made 2 revisions, both correct state updates.
  - It made no false revisions, and it kept a symbol's meaning when the thing it depicts was destroyed.
  - It produced **no reinterpretations**.
- **The key improvement came from integration.** The chain being useless once the watch is sold was
  captured, but by integration under the new revision kinds, not by propagation.
- **Jim's earlier reaction was not reconsidered.** It lies two links from anything that changed, and
  propagation is limited to one link.

## What was built

| Change | Where |
|---|---|
| `CHANGES_STATE` relation; CONTRADICTS narrowed to conflicting accounts | `schema.py`, integration prompt |
| Revision `kind` is `state` or `interpretive`; state updates go to `unit.state` and leave the reading alone | `schema.py`, `integrate.record_revision` |
| Coexisting readings (`other_readings`, revision `mode: coexists`) | same |
| Revisions record `source`, `trigger_unit` and `evidence_units` | `schema.py`, `store.py` (additive migration) |
| Propagation, described below | `propagate.py`, called from `pipeline.py`; `MOTIF_PROPAGATE=0` disables it |
| Journey digest lists states and coexisting readings; explain treats a state update as consequence evidence, not reinterpretation | `journey.py`, `explain.py` (no interface change) |
| The Weave can draw `CHANGES_STATE` | `frontend/src/vocab.ts`, `types.ts` |

**Propagation rules:**
- **Triggers.** A trigger is any integration revision of an earlier unit, or any CHANGES_STATE, CONTRADICTS or REFRAMES link from
  the current passage to one.
- **Candidates.** Candidates are the changed unit's direct graph neighbours from earlier passages: at most 4 per change and
  8 in total, strongest links first.
- **Judgement.** One model call per passage judges the candidates as unchanged (the default), state update or reinterpretation, with an optional
  coexisting reading.
- **Evidence.** Code requires evidence from the triggering change and checks every cited id.
- **One level.** Revisions made by propagation are never triggers.

**Tests.** Backend: 54 pass (44 existing + 10 new). Frontend: 17 pass. `tests/test_propagate.py` is the
generic synthetic test, a lighthouse with a scripted model. It covers:
- candidates limited to direct neighbours;
- no units from later passages;
- selective application;
- coexisting readings that keep the symbolic one;
- rejection without trigger evidence;
- one level only;
- the caps;
- no call when nothing changed.

## Runs

| Run | What | New calls | Cost | Model time | Wall |
|---|---|---|---|---|---|
| A | Magi, new integration prompt, propagation **off** | 6 integration | $0.1273 | 130 s | 130 s |
| C | Magi, new integration prompt, propagation **on** | 4 propagation (integration all cache hits) | $0.0494 | 49 s | 50 s |
| C | Journey and explain on run C | 2 | $0.0572 | 57 s | — |
| S | Synthetic "Harlow Footbridge" (new text, 3 passages), propagation on | 3 perception, 3 integration, 1 propagation | $0.1042 | 114 s | 114 s |
| **Total** | | 19 | **$0.3381** | | |

- **Database total.** $0.971 of $2.00. This includes $0.633 from before.
- **Isolation.** Every run used a copy of the database (`data/motif.exp3.db`).
- **Baselines.** The baseline files are byte-identical to the hashes recorded in `baseline_hashes.sha256`. The main database gained the new columns
  when tests opened it, but its content still equals the Day 2 exports.

**Cost of propagation on the Magi:** +$0.0494 (+23% of the Day 2 pipeline cost of $0.2156) and +49 s (+21%).

**Runs A and C produced identical representations.** Propagation revised nothing, so every later integration call was a cache hit.
Every difference from the Day 2 baseline therefore comes from the new integration prompt and schema, plus sampling
variation. That variation cannot be separated out with one run each.

## The four evaluation questions (Gift of the Magi)

| | Question | Result | How |
|---|---|---|---|
| E1 | Does the watch sale make the chain reconsidered? | **Yes, by integration, not propagation** | At P6 integration revised the chain: *"now also an unusable gift, kept without a watch to hold, mirroring the combs without hair, while still signifying love"* (interpretive). On Day 2 the chain was in memory and was not revised. |
| E2 | Is Jim's earlier reaction reconsidered? | **No (as predicted)** | The stare is revised at P5 only, as "stunned incomprehension". At P6 it was not a candidate: it is two links from the watch and the possessions, and propagation stops at one. |
| E3 | Are the couple's sacrifices better represented? | **Yes, mostly by integration** | New cross-passage link: watch sale RELATES_TO hair sale, *"both partners sold their proudest possession for a gift"*. "Both useless gifts mirror each other" (inside P6). "Couple's Two Proud Possessions" gets a state update, *"neither proud possession remains intact"*. The Journey's last stage now says *"just as her chain has no watch to hold"*, backed by the stored revision. On Day 2 the Journey composed this itself. |
| E4 | Do false revisions or connections increase? | **Fewer misleading ones, some new noise** | CONTRADICTS 3 → 0, contested units 2 → 0. But 2 of the 6 CHANGES_STATE links are trivial succession ("back home" changes the state of "rushes to street"; Jim's arrival ends "anxious wait"). These triggered 2 of the 4 propagation calls. |
| E5 | Incrementality | **Held** | No candidate or evidence came from a later passage. Code guarantees this, and the logs confirm it. |

**Lost compared with Day 2.**
- REFRAMES fell from 1 to 0.
- Interpretive revisions fell from 6 to 2.
- The baseline's "magi remark reframes the poverty" and "the package was the combs bought with watch money" are absent.

With one run each, I cannot tell whether the revision-kind choice pushes the model toward "state" or whether this
is sampling variation. Watch for it.

### Propagation verdicts (Magi): 17 candidates, 17 "unchanged"

| Passage | Changes | Candidates | Assessment |
|---|---|---|---|
| P3 | hair gone, possessions, savings, "rushes to street" | watch, household, desire for gift, weeping | All correctly unchanged |
| P4 | curls change the hair | possessions, hair sale | Correctly unchanged |
| P5 | stare reinterpreted, wait ended | curls, chain, Jim, desire | Correctly unchanged |
| P6 | watch sold, possessions gone, chain unusable | Jim, hair, **hair sale**, household, savings, chain-like-Jim, wait | 6 correctly unchanged. **"Della sells her hair" arguably should have gained a coexisting reading** (one half of a mutual sacrifice). |

The rationales show why. Most candidates have **no interpretive reading**, only factual content. So "does the
current reading still hold?" becomes "is the fact still true?", which is always yes. For example: *"does not undo that the sale
happened and paid for the chain"*.

## Synthetic text: "The Harlow Footbridge"

Written and pre-registered before running; see `expectations.md`. It describes no real place.

| Expectation | Result |
|---|---|
| Flood → bridge is a state change, not a contradiction | ✓ CHANGES_STATE, plus a state revision: "no longer joins the banks" |
| Engineers' report CONTRADICTS the 2021 survey; survey contested | ✓ Two CONTRADICTS links; survey contested and reinterpreted as "discredited". It is the only contested unit. |
| Practical dependents updated | ✓ Doctor's surgery: state update (propagation). ✓ Post: state update (propagation). ✓ Festival: state update (integration). |
| Seal and poem: symbolic reading kept | ✓ Seal judged **unchanged**: *"the physical loss does not erase [its union meaning]"*. The poem was not a candidate. |
| Railings: unchanged | Not testable: perception never extracted the railings. |
| Trout and library: not candidates | ✓ Not extracted, not candidates |
| Market income, school walk, cold-store loan, wheelchair clinic | **✗ Never reconsidered.** P1's integration formed **no relations at all**, so these had no link to the bridge. The wheelchair clinic is two links away, through the doctor. |

Precision 3/3. Recall: 3 of 7 practical dependents reconsidered (4 of 7 counting the festival, which integration
handled).

## New interpretive relationships vs. factual state updates

| | Interpretive (meaning changed) | State (facts changed) |
|---|---|---|
| Magi, integration | chain becomes an unusable gift that mirrors the combs; stare as stunned incomprehension; *link:* both partners sold their proudest possession | hair gone; possessions (twice); savings; wait ended; watch sold |
| Magi, propagation | none | none |
| Synthetic, integration | 2021 survey discredited | bridge gone; festival cannot cross |
| Synthetic, propagation | none | doctor unreachable from the east bank; post cannot be carried |

## Errors

- **Propagation, false revisions:** 0.
- **Propagation, missed reinterpretations:** 1 arguable (hair sale at P6). The doctor's "state update" could also be read
  as a reinterpretation, because the purpose of the location is defeated. The model said the purpose was unchanged.
- **Retrieval misses:** the stare (two links away); the market, school, cold store and wheelchair clinic (no links
  in the graph).
- **Integration noise:** 2 trivial CHANGES_STATE links, and 2 trivial state revisions (savings, wait).
- **Explain overclaim.** It presents the *state* update of "Two Proud Possessions" as *"now meaning pride in mutual
  sacrifice rather than ownership"*, turning a factual update into a change of meaning.
- **Display.** The Weave's inspector lists state updates under "How its reading changed". The Journey interface was
  left unchanged, as asked.

## The most important limitation

**Propagation asks whether a reading still holds, but most units have no reading, only facts.** Facts from
earlier passages never stop being true, so the model answers "unchanged". That answer is correct about the fact
and misses the change in significance, for example "Della sells her hair" becoming one half of a mutual sacrifice.

This explains why propagation was safe, with no false revisions, and also inert. The question it asks cannot
produce an added meaning unless the unit already has one.

Second, retrieval depends on a sparse graph. Units that integration never linked, like the footbridge's dependents
in P1, cannot be reached at any depth. Units two links away, like Jim's stare, are excluded by the one-level bound.

Nothing was changed after seeing these results. Both points are left for a decision.
