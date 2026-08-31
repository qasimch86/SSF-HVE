# ADR-0006 — Prompt-hash-keyed replay fixtures; replay is the default

**Status:** Accepted · **Date:** 2026-08-29

## Context

An evaluation a judge cannot run is a claim, not evidence. Live model calls need a key, cost
money, and are not reproducible. But a cache keyed loosely enough to be convenient is a way to
serve a stale response to a changed prompt — which would make every number meaningless.

## Options

1. **Live only.** Honest, unreproducible, and useless to a judge without a key.
2. **Record and replay keyed by case and role.** Convenient. A prompt edit silently reuses the
   old response.
3. **Replay keyed by the exact rendered prompt**, live behind an explicit flag.

## Decision

Option 3. The key is
`sha256("ssf-hve/v1\n" + role + "\n" + model + "\n" + rendered_prompt)`. Change one character
of a prompt template and every fixture for that role stops resolving — loudly, with a distinct
exit code, never by silently regenerating.

Sampling enters through the *role* (`role#sN`), never the prompt, so three baseline samples
share a byte-identical prompt and remain comparable.

## Consequences

**Good.** The full evaluation runs offline, with no key, at zero cost, in under 30 seconds.
Every published number is reproducible from the archive by a third party.
`test_edited_prompt_invalidates_the_fixture` pins the property.

**Bad.** Editing a prompt invalidates its fixtures, which means recapture. During development
that is friction. It is the correct friction: the alternative is a silently wrong evaluation.

**Honest limitation.** All 122 fixtures are `blinded-agent-capture`, not `live-api`. They came
from isolated agent sessions that received only the rendered prompt. Sampling settings were not
controllable and the serving model may differ from the configured identifier. That the capture
session saw only the prompt is **procedural**: no test can verify it after the fact, and
`PROVENANCE.md` says so rather than implying otherwise.

**Defect found and fixed.** Run records once stored a hash of the *base* role while fixtures
were keyed on the sample-scoped role, so 0 of 122 resolved from the record. `ModelResponse`
now carries the `fixture_key` actually used.
