# Experiment 3: expectations, recorded before any model output

Written 2026-10-27, after the mechanism and its unit tests were written and **before any live call**.

## Mechanism under test (summary)

- **State changes become their own type.** A new relation type, `CHANGES_STATE`, is defined, and CONTRADICTS is
  narrowed to conflicting accounts or claims. Every revision is either `state` (what is now the case) or
  `interpretive` (what it signifies). A state update writes `state` and leaves the reading alone.
  Interpretive readings may *coexist* (`other_readings`) instead of replacing one another.
- **Propagation.** After integrating a passage, every change to an earlier unit reactivates that unit's direct
  graph neighbours from earlier passages:
  - The changes that count are an integration revision, or a CHANGES_STATE, CONTRADICTS or REFRAMES link.
  - At most 4 neighbours per change and 8 in total.
  - One model call judges them: unchanged, state update or reinterpretation.
  - Code requires evidence from the triggering change.
  - Revisions made by propagation never trigger further propagation.

## Runs

| Run | Integration prompt | Propagation | Purpose |
|---|---|---|---|
| Baseline | Day 2 (unchanged) | none | `data/results/gift_of_the_magi.muse-spark-1.3.json` |
| A | new (state vs. contradiction, revision kinds) | off | separates the effect of the prompt and schema change |
| C | new | on | the mechanism |

All runs use muse-spark-1.3 at medium reasoning effort, and a separate database (`data/motif.exp3.db`) copied from the main one.
Perception requests are byte-identical to Day 2, so they come from the cache and the units are identical. Only
integration and later steps can differ. Model sampling is not deterministic, so A and C differ by more than
propagation alone after their first divergent call.

## Gift of the Magi: what would count as success

- **E1. Does the watch sale make the chain reconsidered?**
  - **Hit:** at P6, the P3 chain unit receives a propagation revision citing the watch sale, and the
    reinterpretation says the gift can no longer serve its purpose, or now means something else.
  - **Partial:** a state update only.
  - **Requires:** the chain to be one hop from a changed unit, which held in the baseline graph (chain SUPPORTS watch).
- **E2. Is Jim's earlier reaction reconsidered?**
  - **Hit:** the P4 stare or P5 confusion unit is revised at P6, citing the combs or the watch sale.
  - **Prediction: likely miss.** In the baseline graph the stare is two hops from the watch and the package,
    and propagation is limited to one level. If it misses for that reason, it is a limit of the bound, not of the model judgement.
- **E3. Are the couple's sacrifices better represented?**
  - **Hit:** any of the following gains an interpretive (ideally coexisting) reading about mutual sacrifice: "Couple's Two Proud
    Possessions", the hair, the watch, or the hair sale.
  - **Also counts:** a link or reading tying both sacrifices together.
- **E4. Do errors increase?**
  - Count propagation revisions rated *unsupported* or *misleading*.
  - Count CONTRADICTS links used for change over time; the baseline had 3.
  - Count units marked contested; the baseline had 2, the hair and the watch.
  - **Failure:** more unsupported revisions than supported ones, or a symbolic reading replaced by a practical one.
- **E5. Incrementality.** No revision at passage *p* cites a unit introduced after *p*. Code guarantees this; it is checked anyway.

## Synthetic text: "The Harlow Footbridge" (3 passages)

| Passage | Content |
|---|---|
| P1 | The footbridge as the only crossing, built jointly by rival guilds; growers' market income; the town seal (bridge = union of the banks); railings repainted green; 2021 survey: inspected yearly and sound; school walk; growers' cold store and loan |
| P2 | Doctor's surgery chosen for being near the bridge; centenary festival and poem "two banks, one step"; trout and library; the post carried over the bridge |
| P3 | The flood carries the bridge away; engineers find it was **not inspected since 1998**; no new crossing for 3 years |

Expected:
- **Integration at P3.**
  - The flood is linked to the footbridge as CHANGES_STATE, or as a state revision. It should **not** be CONTRADICTS.
  - The engineers' report CONTRADICTS the 2021 survey. This is a genuine contradiction, so the survey is contested.
- **Propagation at P3.** Expected verdicts for dependents that are graph neighbours of the bridge, or of the survey:
  - Growers' market income, school walk, doctor's surgery, festival, post: **state update or reinterpretation**.
    Practical significance changes.
  - Town seal and poem: **unchanged or coexisting**. The symbolic reading must **not** be replaced.
  - Green railings: **unchanged**. This is association alone.
  - Trout and library: should not be candidates. If they are, **unchanged**.
- Because of the cap of 8 candidates, not every dependent will be reconsidered. Which ones are is part of the result.

## Costs

The budget is cumulative in the experiment database, starting from $0.6328 of $2.00. Expected additional cost:
- Run A: about $0.15, all integration.
- Run C: about $0.10 to $0.20, for integration after the first divergence plus up to 6 propagation calls.
- Journey and explain for run C: about $0.05.
- Synthetic run: about $0.08.
