# ADR-0001 — Separate repository, newly written code

**Status:** Accepted · **Date:** 2026-08-29 · **Supersedes:** nothing

## Context

The design principles behind this system come from SSF Studio, a commercial platform the owner
is building. The hackathon requires that submitted work be original and, on submission,
transfers rights in it. Reusing commercial source would put a commercial codebase inside that
transfer.

There was a real temptation here: the commercial tree already contains a review agent, a
blueprint library and enterprise documentation, and reusing them would have saved days.

## Options

1. **Build inside the commercial repository, submit a subdirectory.** Fastest. Contaminates the
   submission with code the owner cannot give away, and makes the boundary unprovable.
2. **Fork the commercial repository and strip it.** Still carries the history, and "stripped"
   is a claim nobody can check.
3. **A separate repository, newly written, with the boundary declared and tested.**

## Decision

Option 3. A new repository containing newly written code. No file, prompt, schema or document
from the commercial tree is copied. The commercial tree is read-only evidence of prior work,
disclosed in `PRE_EXISTING_WORK.md`.

## Consequences

**Good.** The boundary is mechanical rather than asserted:
`tests/test_secrets.py::test_no_commercial_source_markers` fails the build if any commercial
identifier appears in a shipped file, and `test_every_shipped_file_is_scanned` proves the
scanner covers everything in the archive. Ownership transfers cleanly.

**Bad.** Everything was rebuilt from scratch under deadline. The evaluation harness, the
schemas and the gate mechanism all had to be written and debugged inside 48 hours, and the
defect history in `IMPROVEMENT_CHANGELOG.md` is partly the cost of that.

**Accepted risk.** Design principles are not code, but a reviewer could still ask whether the
architecture is derivative. The disclosure in `PRE_EXISTING_WORK.md` answers that directly
rather than waiting to be asked.
