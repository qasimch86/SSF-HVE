# ADR-0005 — Human-only gates; the absence of approval blocks

**Status:** Accepted · **Date:** 2026-08-29 · **Settled by measurement**

## Context

Something has to decide that a script is fit to produce. Every automated answer to that
question is a system marking its own homework.

## Options

1. **Terminal status gates production.** `ACCEPT` proceeds. Fully automatic.
2. **A confidence threshold gates production.**
3. **A person approves one exact version, and nothing else opens the gate.**

## Decision

Option 3, with the polarity chosen deliberately: **the absence of an approval blocks; the
presence of a status never permits.** `record_approval` requires an interactive terminal and
the word `APPROVE` typed in full. The runner has no code path to it.

## Consequences — measured

`rm-bound-ok` is a configuration identical to `final` in every field except one:
`allow_progress_at_bound: true`, so exhausting the correction limit terminates `ACCEPT`
instead of `HOLD`. It is option 1 in miniature.

| | `final` | `rm-bound-ok` |
|---|---|---|
| Final narration SHA-256 | `0d14b9c3…5db92ec1` | `0d14b9c3…5db92ec1` |
| Unresolved findings | `F01` MAJOR on `CL05` | `F01` MAJOR on `CL05` |
| Model calls / cycles | 7 / 2 | 7 / 2 |
| Clean-claim retention | 0.86 | 0.86 |
| **Terminal status** | **`HOLD`** | **`ACCEPT`** |
| **Unsafe output rate** | 0.20 | **0.10** |

The artifact is byte-identical. The finding is unresolved in both. **The deliberately broken
configuration wins on the primary metric**, purely by relabelling an unresolved run as
finished.

This is a control-safety counterexample, not a performance comparison. It cannot show the
bound rule improves the output, because the output is identical. It shows something narrower
and more useful: a metric keyed on asserted defects can be moved ten points, in the favourable
direction, by a one-field change that resolves nothing. `final` is retained **because it
scores worse** — `HOLD` is the true description of that run.

**Bad.** A person is now a hard dependency of production. That is the cost, and it is the
point.

**Not claimed.** Both runs sit at `BLOCKED_AWAITING_HUMAN` because nobody approved either one.
That is the default state in replay, not evidence the gate caught anything.
