# CS-10-v1 — superseded case set, retained as evidence

These are the ten packets exactly as frozen on 2026-08-29 at 19:30 UTC, together
with the baseline results measured on them. They are kept because the reason
they were replaced is itself a result.

**What went wrong.** The packets announced their own defects. Limitations were
prefixed `MATERIAL:`, C09 carried a block headed *TERMINOLOGY NOTE FOR ANY SPOKEN
OR WRITTEN SUMMARY*, C08 stated *THE ANALOGY BREAKS DOWN HERE*, and C10's
limitations list said in as many words that the data-availability field contained
instruction-like text. A capable model reading such a record does not have to
detect anything: the answer is in the prompt.

Measured baseline on CS-10-v1: **unsafe output rate 0.20 (2/10)**, and on
inspection both of those two were scorer false positives — the scripts did state
the limitation, in wording the detector did not anticipate ("not allocated at
random", "the second main outcome came up empty"). The true baseline unsafe rate
on this case set is **0/10**. A case set on which a plain single prompt scores
zero cannot measure an improvement over a plain single prompt.

**What replaced it.** CS-10-v2 keeps the same ten defect classes and the same
scoring machinery. Every packet retains all of the *evidence* a careful reader
needs and loses all of the *coaching*: no MATERIAL labels, no terminology notes
addressed to a summariser, no limitations list that states the trap in plain
words. The defect must now be found in the record rather than read off it.

The absent-mode detectors were also rewritten to tolerate paraphrase, which is a
scorer-fidelity fix, not a change of goalposts.

Both case sets are reported. See `IMPROVEMENT_CHANGELOG.md` and `EVAL_PROTOCOL.md`
section 9.
