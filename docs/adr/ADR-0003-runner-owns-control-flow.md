# ADR-0003 — The runner owns control flow; agents advise

**Status:** Accepted · **Date:** 2026-08-29

## Context

The common agentic pattern lets an agent decide what to do next — often the same agent that
produced the work being judged. The verifier in this system returns a recommendation from
`ACCEPT / EDIT / REWORK / HOLD`, which looks exactly like a control instruction.

## Options

1. **The verifier's recommendation is the decision.** Simple, and it is what the vocabulary
   invites.
2. **A planning agent reads the recommendation and decides.** Moves the problem.
3. **The recommendation is advisory data; code decides.**

## Decision

Option 3. `runner.execute` reads the findings, applies fixed rules — are there blocking
findings, is the correction bound reached, did anything fail to parse — and sets the terminal
status. The recommendation is recorded, and never executed.

## Consequences

**Good.** No agent can declare its own work finished. The decision procedure is a few dozen
lines anyone can read, rather than an emergent property of a prompt.
`test_verifier_cannot_approve_while_reporting_a_blocker` and
`test_runner_cannot_reach_record_approval` pin it structurally.

**Bad.** The verifier's judgement is discarded in cases where it might be better than the
rule. The rules are crude by comparison — presence of a blocking finding, a counter — and
deliberately so, because a crude rule you can read beats a subtle one you cannot.

**Consequence that matters most.** This is what makes `HOLD` possible. A system where the
agent decides has no natural way to say *I did not finish*, because nothing wants to say it.
