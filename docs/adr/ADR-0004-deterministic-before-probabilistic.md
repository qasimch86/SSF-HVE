# ADR-0004 — Deterministic checks before, and instead of, model verification

**Status:** Accepted · **Date:** 2026-08-29 · **Settled by measurement**

## Context

Some of what needs checking is not a judgement call: does this number appear in the source, is
this unit the source's unit, does this citation resolve, does the script emit the exact phrase
an embedded instruction demanded. Some of it is: has the meaning been strengthened, has scope
been overextended, has a limitation been dropped in substance rather than in words.

## Options

1. **One verifier does everything.** Simplest architecture; one prompt.
2. **Deterministic checks in code first; the model asked only about what code cannot see.**
3. **Deterministic checks as advisory input to the model, which makes the final call.**

## Decision

Option 2. `CHECK-Q/U/L/R/I` run in code, before any model call, and their findings are
authoritative. A3 is asked only about what code cannot settle.

## Consequences — measured

`rm-model-checks` is option 1, run as a real experiment: the deterministic checks are removed
and A3 is instructed to perform them itself.

| | `final` | `rm-model-checks` |
|---|---|---|
| Unsafe output rate | 0.20 | **0.60** |
| Clean-claim retention | 0.86 | **0.36** |
| Malformed runs | 1 of 10 | **6 of 10** |
| Missed defect classes | 1 | **6** |
| Model calls | 44 | 40 |

It used *fewer* model calls, because six of its ten runs terminated early on malformed output.
Asking a model to do arithmetic and citation-checking costs more and buys worse.

**Bad.** Deterministic checks produce false positives, and a false positive from code is more
expensive than one from a model because code findings are treated as authoritative. `iter-1`
measured the cost: retention fell from 0.81 to 0.71 when a check fired wrongly and the
correction cycle deleted a true sentence. Text normalisation is tested in its own right
because of it.

**Constraint this creates.** The checks must never see the gold table, or they would be
scoring rather than checking. `test_checks_never_read_the_gold_table` walks the module's AST.
