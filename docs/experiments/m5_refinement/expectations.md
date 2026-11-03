# Milestone 5: expectations, recorded before any model call

Written 2026-10-27, after implementation and tests and before any live run. Rules and thresholds are as in
`backend/motif/construct.py` at this point (hash in `expectations.sha256`). They are not tuned after results.

## Offline trigger check (free, on Milestone 4's stored representations)

See `offline_trigger_check.txt`.
- **Magi.** The refined rules still fire at P3–P6.
- **Plato.** They fire at P4–P9; P3 drops out.
- **Estimate.** 10 of 15 passages, against 11 in Milestone 4.

Removing the long-range rule changes little, because Plato reinterprets established units at every passage from P4
(R1). R4 depends on which meanings exist, so live numbers may differ. I chose **not** to tighten R1 further: that
would tune the rules to these two books. Remaining selectivity must come from the model returning "no new meaning".

## Design

- **Databases.** `data/motif.m5.db` (replicate A) and `data/motif.m5b.db` (replicate B). Both are copies of the
  Milestone 4 database.
- **Identical upstream.** Perception, integration and propagation are cache hits, identical to Milestone 4, so only
  construction, Journey and explain are new.
- **Sampling replicate.** B repeats A with the same code and inputs. Its construction calls are not in its cache, so
  they are sampled afresh. Differences between A and B estimate sampling variation. Milestone 4 has a single run, so
  its own variation is unknown.

## Expectations

| | Expectation |
|---|---|
| Frequency | 9–10 construction calls per replicate (M4: 11) |
| Meanings | Fewer new meanings than M4's 17, with some reinforcements or repeats recorded instead of new entries |
| Magi | Mutual sacrifice (G1–G3) still found at P6. Her treasure adorns his (G4) found at P3. |
| Plato | L2, L3 and L5 still found. L1 cannot be (perception). L4 likely still missed. |
| Basis | "Explicit" only where the text states the meaning itself. Plato: Socrates' conclusions, so some explicit is right. Magi: at most "wisest" is explicit. |
| Journey | At least one transition per book cites a stored meaning, with `beyond_evidence` stated where the explanation adds synthesis |

## Failure criteria

- A valid alternative interpretation consolidated into a different meaning: "incorrectly combined".
- An expected meaning found in M4 and lost in both replicates.
- More unsupported meanings than M4's 0.
- Any change to units, relations or revisions. Checked against the Milestone 4 exports.

Ratings use the same scale (S/P/T/U), one rater, independent of model confidence.
