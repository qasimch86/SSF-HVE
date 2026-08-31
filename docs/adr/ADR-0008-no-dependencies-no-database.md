# ADR-0008 — Zero runtime dependencies; JSON files, not a database

**Status:** Accepted · **Date:** 2026-08-29

## Context

The system needs schema validation, a CLI, persistence, a web view and hashing. Every one of
those has an obvious library, and using them would have been faster.

The constraint that overrides speed: a judge with limited time must be able to run this, and a
reviewer must be able to read the evidence without running anything at all.

## Options

1. **Standard stack** — pydantic, click, SQLite or Postgres, FastAPI. Fastest to write.
2. **Light dependencies** — pydantic only.
3. **Standard library only**, JSON files on disk.

## Decision

Option 3. `argparse`, hand-written validators, JSON files, `wsgiref`, `hashlib`, `hmac`.
`pytest` is a development dependency, pinned. `ffmpeg` is optional and its absence blocks
nothing.

## Consequences

**Good.** `python -m ssf_hve score` works after `pip install -e .` with nothing to resolve, on
any machine with Python 3.10+. Every artifact is a file a reviewer can open: run records,
fixtures, gold tables and gate records are all readable with `cat`. A database would have put
the evidence somewhere a reader has to query.

The validators being hand-written turned out to matter more than expected: fail-closed
behaviour (ADR-0002) is a property of *these* validators. A permissive library validator would
have quietly accepted several of the malformed outputs this system reports.

**Bad.** More code, and it is our code. The schema module is longer than the equivalent
declarations, and every validator needed its own test — `tests/test_schemas.py` exists because
of this decision.

**Bad.** No indexing, no queries, no concurrent access. Scoring globs a directory. At 100 run
records that is instant; at 100,000 it would not be. Accepted: this is a single-user CLI, and
designing for a scale that does not exist would be documentation theatre.
