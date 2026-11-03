# Milestone 5.1: expectations for the single live verification run (recorded before the call)

Everything below was already verified on saved outputs, without API calls:
- The M5 replicate-B mutual-sacrifice proposal is kept as pending, not discarded (replay test).
- It was the only state-consequence label in any saved M4/M5 run.
- With the corrected evidence logic, one saved Plato transition goes from tentative to supported (B T3>4) and one
  correctly stays tentative (A T3>4). Candidate numbering is identical to the saved prompts.

The live run (one replicate, both books; upstream cached; budget guard +$1.00) checks only what the new prompt changes:
- **Explicit appears again**, but only with a verified quotation. Expect some explicit Plato meanings (Socrates states
  several conclusions) and few or none in the Magi, where only "wisest" is stated.
- **Every downgrade** from explicit to inferred is recorded with the rejected quotation.
- **No constructed meaning rated unsupported**; pending meanings appear only if a state-consequence label is ambiguous.
- **Journey transitions citing meanings** are marked tentative only when the meaning's content does not show the
  transition's kind.

These are one-sample observations, not evidence of stable rates.
