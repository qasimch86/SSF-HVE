# ADR-0010 — A self-hashed binding over every input that can change a number

**Status:** Accepted · **Date:** 2026-08-30 · **Origin:** re-audit finding

## Context

`verify-provenance` originally proved that gold tables hash to their recorded values and that
published results carry the right case-set and policy stamps. A re-audit found the hole: the
**active case files** carry the detectors, an edit to one changes every score, and
`verify-provenance` still exited 0.

Verifying the snapshot while leaving the live input unbound is verification of the wrong thing.

## Options

1. **Bind the case files too.** Closes the specific hole, leaves the next one open.
2. **Sign the whole repository.** Everything drifts constantly; the signature would be noise.
3. **Bind exactly the set of files that can change a published number**, and hash the binding
   itself.

## Decision

Option 3. `evaluation/provenance_binding.json` freezes the SHA-256 of: active cases and
detectors, the recorded adjudications, every prompt template, the harness version, case
parsing, configuration, schemas, deterministic checks, scorer, normaliser, report generator,
fixture semantics, all 122 fixtures, and the content hash of the published results. The
manifest carries its own hash, so editing the manifest fails its self-check.

## Consequences

**Good.** The audit's own probe now fails as it should: editing an active case file, the
scorer, the normaliser, a prompt template or the published results all break verification, and
each has a test named for the thing it catches. An unbound extra fixture fails too, so the
inventory cannot be padded.

**Bad.** Legitimate change now requires `python -m ssf_hve bind-provenance` and a new commit.
Forgetting it makes verification fail — noisily, which is the right direction, but it is a step
someone will forget.

**Bad.** The binding proves *integrity since it was written*. It says nothing about whether the
bound content was correct when it was bound. An auditor still has to read the case files; this
only guarantees they are reading the ones that produced the numbers.

**Scope note.** The binding covers inputs to a *score*. It does not cover the documents, the
video or the archive — those are covered by the H2 statement (ADR-0007) instead.
