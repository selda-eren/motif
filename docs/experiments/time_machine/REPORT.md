# The Time Machine: full-book MORe experiment

**Result: one complete, reproducible run.** H. G. Wells's *The Time Machine* (Project Gutenberg #35) was processed end to end with
Muse Spark 1.3 Standard and the unchanged production pipeline (perceive, activate, integrate, propagate, construct, then Journey
synthesis and transition explanation). Everything needed to reproduce the results, screenshots and recordings is stored, and the replay was
verified with the model API disabled. Indicative, one-rater findings, not validated research conclusions.

## 1. Size and outcome

| | |
|---|---|
| Words processed | **32,310** (Project Gutenberg header, footer, title block, contents and chapter-heading lines excluded) |
| Chapters | **17** (XVI numbered chapters + Epilogue); 11 of 86 passages straddle a chapter boundary |
| Passages | **86** (default segmentation: ~300-word target, paragraph-aligned; 305 to 613 words, median 358) |
| Completed | **Yes, all 86 passages**, then Journey and explanation, no validation warnings |

## 2. Calls, tokens, time and cost

| | Calls | Cost |
|---|---|---|
| Perception | 86 | $1.551 |
| Integration | 86 | $2.058 |
| Propagation | 68 | $1.096 |
| Construction | 69 | $1.481 |
| Journey synthesis | 1 (80,023 tokens in) | $0.118 |
| Transition explanation | 1 | $0.033 |
| **Total** | **311 paid calls** | **$6.335** (limit $50) |

Tokens: 1,008,188 prompt, 1,205,912 completion (of which 1,016,235 reasoning). Model time 4,379 s (73 min); the 86 passages took about 1.2 h of wall-clock.
Preflight estimate: $8.66 (ceiling $20.2 if every call hit its output cap), 303 calls, 93 min; actual was 27 % cheaper and 311 calls (propagation fired on 68 instead of 60 passages).
Other billing exposure: **one deliberate timeout** (resume test, passage 5, 0.4 s client timeout) is recorded in `logs/uncertain_calls.jsonl` with a worst-case $0.053 that
the provider may or may not have billed; it is counted against the local limit but not in the $6.335. Two further calls were served from the cache during the resume test.

## 3. Resumability (verified before the full run, and again after)

Findings and evidence in `logs/preflight_*.log`, `logs/audit_*.json`, `backend/tests/test_long_run.py` (5 new tests; 92 backend tests pass).

* **A real defect in the stock persistence was found and worked around, not patched in the core.** In `Store`, both `cache_put` and `log_usage` call `commit()` on the connection that also
  holds the half-applied representation of the passage being processed. A timeout in propagation or construction (after integration has added units) is logged, the log write commits the
  half-applied passage, and a resume then processes the passage again on top of its leftovers, **duplicating its units under new ids**. (Characterised by a test.) The harness
  (`backend/motif/experimental/long_run.py`) keeps the cache and usage log in a separate SQLite file, so representation changes commit only when a whole passage finishes while every response and usage row is durable immediately. No cognitive module is changed.
* Kill test with real calls: the process was killed (exit 137) the instant the integration call for passage 4 completed. After the kill: passages 1-3 intact, no passage-4 units, both completed calls in the cache. Resume: those two calls were cache hits ($0), passage 4 was
  processed exactly once, and the audit found **no (task, key) paid twice and no cache key paid twice**.
* Real timeout test: the failed call is stored separately with its billing class; the run stopped cleanly; nothing partial was committed.
* **Cache-only rebuild:** all 86 passages rebuilt from the cached responses with the API pointed at a dead address matched the stored checkpoints **bit for bit** (86/86, 0 API requests): the cognitive pipeline is deterministic given the cached responses.

## 4. What is stored (nothing depends only on SQLite or the API cache)

`passages/pNNN.json.gz`: exact passage text, every request and response (with cache key), usage, notes, errors. `checkpoints/state_after_pNNN.json.gz`: the full representation after each passage and
nothing from later passages (read-only files, hashes in `progress.json`). `exports/`: representation, API snapshots, Journey with explanations, every relation detail, constructed meanings with
quotations, revision history, statistics, every model call (`model_calls.jsonl.gz`), usage CSV, a self-contained SQLite. `MANIFEST.json`: checksums of every file, source and processing-text hashes, model settings, prompt hashes (SHA-256 of each system prompt), code hash, counts, artifact locations.
`source/`: the original download (SHA-256 `source/SOURCE.json`), chapter map and passage map with offsets and passage-to-chapter mapping.

## 5. The representation

| | |
|---|---|
| Units | **463** (3 merges; 0 ungrounded quotes rejected: every quotation is verbatim) |
| Relations | **668** (REFINES 198, SUPPORTS 191, CAUSES 99, CHANGES_STATE 72, RELATES_TO 52, CONTRADICTS 38, REFRAMES 18) |
| Revisions | **175** (81 interpretive, 94 state changes) |
| Constructed meanings | **92** (91 established, 1 pending; 3 further proposals rejected: "restates a stored reading", and two as speculative; all 92 are *inferred*, none *explicit*) |
| Long-distance structure | 26 % of relations link units at least 10 passages apart (median 2); **104 relations**, **47 revisions** and **18 constructed meanings** reach at least 20 passages; **29 constructed meanings** draw on quotations from three or more chapters |

## 6. Interpretive quality (against `reference_evaluation.md`, written and hashed before any output was inspected)

| Question | Verdict |
|---|---|
| Q1 successive theories (Golden Age → decay → class → inversion → cosmic) | **Strong.** The Eloi/architecture readings are revised at passages 46, 54, 59 and 74; meanings c38_1, c43_1, c45_1, c46_1, c53_2, c58_1, c73_1 |
| Q3 the sphinx (landmark → hiding-place → bait) | **Strong.** c33_2 (Ch. IV/V/VII) and c75_1 (Ch. X/XIII) |
| Q4 the machine | Good: c14_1, c19_2, c47_1, c75_1, c76_1 (levers) |
| Q7 social allegory | Strong: c45_1, c46_1, c46_2, c74_1 |
| Q9 reliability of the tale | Strong: c82_1 (Ch. III vs XVI) |
| Q5 fire, light, darkness | Good within chapters (c65_1, c67_1, c68_1, c70_1); weaker as a thread across chapters |
| Q6 Weena and the flowers | **Partial.** A relation links the Epilogue's flowers to the earlier ones (u85_5 REFRAMES u55_1, 0.85) but no constructed meaning does; a proposed flowers-and-Weena meaning was **rejected by the speculation guard** |
| Q2 early pessimism (Ch. I) vs the Epilogue's hope | **Missed.** No unit or meaning ties Ch. I's view of "the Advancement of Mankind" to the Epilogue |
| Q8 the repeated pattern of decline up to cosmic scale | **Missed** as a single meaning; the pieces exist (c74_1, c78_1, c80_1) but are not joined |

**Unsupported or misleading.** None of 10 randomly sampled meanings (seed 7) lacked textual support. Weaknesses seen: (a) some meanings are local plot summaries (c63_2 "snapping a lever into a mace turns quiet hand-holding into armed guardianship",
c09_2) rather than interpretation; (b) a few present the Traveller's *theory* as fact in the statement (c46_2 "not neutral life-support but a rent-extraction apparatus"), although the limits field says the theory is his inference (c74_1 does say so);
(c) no meaning is ever *explicit*; (d) the Journey's only tentative transition (IV→V) is correctly flagged by the system itself. Not a reliability study: one rater, one sample.

**Incremental vs. Journey-only.** Constructed meanings, revisions and relations are built during reading, seeing only earlier passages. The Journey (stage titles and summaries, transition kinds, "what changes") is a final synthesis over that stored representation. Of the three selected discoveries, the Eloi
reinterpretation (c73_1) and the sphinx chain (c33_2, c75_1) are *not* cited by the Journey and have no landmark; the red-sun meaning (c76_2) is, but the Journey text itself says nothing of its specific insight. Details and exact quotations: `docs/experiments/time_machine/findings/DISCOVERIES.md`.

## 7. Scalability observations

**Memory and retrieval scale well.** Working memory is capped, so cost and latency stayed flat: mean prompt tokens 7.2k (passages 1-10), 10.4k, 11.4k, 11.5k (61-86); cost per passage $0.059 to $0.077; wall time per passage 38 to 54 s. Recall averaged 22.4 units per passage (maximum 24). Lexical recall still
reached far back (the trace for passage 77 recalls a unit from passage 1 and "Frail Future People" from passage 20), but because it is lexical, ideas that are re-expressed with different words (the flowers) are not recalled, and this is the likely cause of Q2/Q6/Q8. Single-passage restatements remain accepted (10 of 92).
**The Journey call coped** with an ~80k-token representation digest in one call (14.5 s).

**The visualisation shows strain (no redesign attempted; nothing removed).**
1. **Stage synthesis**: 86 passages become only 5 stages; early stages cover 7-9 passages and render four-line titles in narrow columns. The Journey draws only the **10 constructed meanings it cites (of 91)**, so the strongest ones (c73_1, c33_2, c75_1) have no landmark.
2. **SVG layout / vocabulary**: passage numbers use a Roman-numeral helper with no L or C, giving "XXXXXXXXVI"; at the right the landmark captions collide ("passages XXXXXIV, XXXXXXI…").
3. **Panels**: the stage-IV return panel lists 30 revised readings and 8 reframing links (a 5,700 px page). It is complete and readable but needs scrolling to a cluster.
4. **The Weave**: 463 units and 668 relations make a ~9,600 × 8,400 px figure with 86 columns; only a local cluster is readable at a time (a hash link or the Journey's "open in The Weave" selects, but does not centre, the item).

## 8. Offline replay verification: **passed**

A fresh backend with `MODEL_API_KEY` empty and `MOTIF_API_BASE=http://127.0.0.1:9` reading a copy of the exported database served the Journey (5 stages with explanations), The Weave (all 463 units and 668 relation loops), all 92 constructed meanings with verbatim evidence and
the evidence for every unit; each response equals the exported JSON, all 668 relation-detail endpoints match, a missing book returns 404 (nothing is generated), and the browser contacted nothing but the local app (`logs/offline_app_verification.log`, 23 checks, 0 failures).

## 9. Is The Time Machine a better demo than The Gift of the Magi?

**For the central claim, yes.** "Meaning emerges across distant chapters" is only demonstrable at this length: a reading formed at passage 20 is reinterpreted at passages 46, 54, 59 and 74, and a meaning joins a day-night flicker (Chapter IV) to a motionless red sun (Chapters XIII/XIV),
with verbatim evidence at each end. The Magi has six passages and cannot show a 50-passage return. **For clarity, no.** The Magi Journey is clean at a glance; this one is dense, has the numeral and caption problems above, and its best discoveries are not landmarks.
**Recommendation:** use the Time Machine for the Plato-to-fiction section only with focused footage (clips B and C, plus the model-trace clip E), after fixing the passage-numeral rendering, otherwise keep the Magi for the clean overview and show the Time Machine's long return as the "scale" proof. The existing video was not changed.

## 10. Locations

Experiment: `docs/experiments/time_machine/` (this report, `PREFLIGHT.json`, `reference_evaluation.md`, `MANIFEST.json`, `source/`, `passages/`, `checkpoints/`, `exports/`, `logs/`, `scripts/`).
Databases (gitignored): `data/motif.the_time_machine.db`, `data/motif.the_time_machine.calls.db`; backup of the pre-experiment project: `~/Motif-backups/pre-time-machine-2026-11-01/`.
Findings: `docs/experiments/time_machine/findings/` (`DISCOVERIES.md`, `ELOI_VERIFICATION.md`). The video captures and clips are not in the public repository.
