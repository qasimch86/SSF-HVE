# ADR-0002 — Fail-closed schema validation, no repair path

**Status:** Accepted · **Date:** 2026-08-29

## Context

Language models return text. The system needs typed objects. Every framework in this space
offers some form of recovery: retry with a stricter prompt, coerce the nearest valid shape, or
ask the model to fix its own output.

## Options

1. **Repair.** Coerce or retry until something parses. Highest apparent success rate.
2. **Retry with feedback.** Return the validation error to the model and try again.
3. **Fail closed.** Raise, terminate the run, record the rejected output, count it unsafe.

## Decision

Option 3. `parse_or_fail_closed` raises `MalformedModelOutput`. There is no repair, no
coercion and no retry. The rejected response is preserved in full in the run record.

## Consequences

**Good.** A malformed run is *visible*. One of the ten cases in the shipped configuration
terminates `MALFORMED` and is counted unsafe by our own protocol — a number that a repair path
would have converted into a success, silently. The rejected output is the most informative
artifact in a failing run.

**Bad.** The headline metric is worse than it would otherwise be. `final` reports 0.20 unsafe,
and half of that is a fail-closed run. This was accepted on the reasoning that a metric which
improves when you hide failures is not measuring quality.

**Related evidence.** `iter-3 → iter-4` shows the neighbouring effect: separating what the
verifier *observed* from what it *recommends* halved malformed output (2 → 1) and lifted
retention (0.75 → 0.86). Better structure reduces malformed output; hiding it does not.

**Also decided here.** A verifier result recommending `ACCEPT` while carrying a BLOCKER or
MAJOR finding is rejected as malformed. An internally inconsistent result is not a result.
