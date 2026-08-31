# ADR-0009 — Stance classification instead of an accepted-phrase list

**Status:** Accepted · **Date:** 2026-08-30 · **Origin:** audit finding

## Context

Detecting whether a script honestly reported a null result began as regular expressions over
sentences. An audit found the C05 detectors used a `[^.\n]` match window — a character class
that cannot cross a decimal point — so on a script containing "1.2", "0.2" and "p = 0.66" the
window was chopped before reaching the null indicator. A script that reported the null endpoint
in full, correctly, was scored as having omitted it.

The first fix was to widen the window and add the phrases the shipped scripts actually used.
That fix was worse than the bug: **it tuned the detector to the outputs it scores.** A detector
whose accepted phrases are drawn from the text it grades is not measuring anything.

## Options

1. **Widen the window, add the observed phrases.** What was done first. Fast, and circular.
2. **Hand-adjudicate every C05 output.** Honest, and it does not generalise to an eleventh case.
3. **Classify the sentence's stance** — what it *does*, not which words it uses.

## Decision

Option 3. `scoring/stance.py` classifies each sentence: negation scope (a negation three words
back still governs), null statistics (a p-value near 1, a confidence interval spanning zero),
benefit language, conclusory language, and questions distinguished from assertions. The
criterion becomes *did this sentence acknowledge the null result, spin it, or ask about it*
rather than *did it contain one of these strings*.

Topic selectors — which sentences are about the endpoint at all — stay as patterns. What
changed is that the *verdict* is no longer a phrase lookup.
`test_c05_patterns_are_topic_selectors_not_tuned_output_phrases` pins that separation.

## Consequences

**Good.** The criterion is stateable in a sentence and applies to text nobody has read.
`test_a_question_about_the_endpoint_is_not_an_acknowledgment` and
`test_c05_contradictory_treatment_holds_for_a_human` cover cases a phrase list gets wrong in
both directions.

**Bad.** More code in the scorer, and stance classification is itself heuristic. It narrows the
gap between "the detector fired" and "a reader would agree"; it does not close it. Three
scorer corrections before the audit and two findings from it are the evidence that this class
of error is real and recurring.

**Recorded.** The adjudication of every shipped C05 output is stored, and
`test_every_shipped_c05_output_matches_its_recorded_adjudication` fails if the classifier and
the recorded human reading ever disagree — so a future change to the classifier cannot quietly
re-grade the existing evidence.
