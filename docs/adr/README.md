# Architecture Decision Records

Ten decisions, each with the alternatives that were available, the decision taken, its
consequences, and — where one exists — the measurement that settled it.

> **Provenance.** Written 2026-08-30, after implementation. These record decisions that were
> genuinely taken during the build; they are not minutes written at the time. Where a decision
> was settled by a measurement, the measurement is real and reproducible. Where it was settled
> by judgement, the record says so instead of implying evidence that does not exist.

| ADR | Decision | Settled by |
|---|---|---|
| [0001](ADR-0001-separate-repository.md) | Separate repository, newly written code | Ownership and licensing constraint |
| [0002](ADR-0002-fail-closed-schemas.md) | Fail-closed schema validation, no repair path | Judgement, then `iter-3 → iter-4` |
| [0003](ADR-0003-runner-owns-control-flow.md) | The runner owns control flow; agents advise | Judgement — the premise of the system |
| [0004](ADR-0004-deterministic-before-probabilistic.md) | Deterministic checks before, and instead of, model verification | **Measured:** `rm-model-checks` |
| [0005](ADR-0005-human-only-gates.md) | Human-only gates; absence blocks, status never permits | **Measured:** `rm-bound-ok` |
| [0006](ADR-0006-replay-by-default.md) | Prompt-hash-keyed replay fixtures, replay by default | Reproducibility and cost |
| [0007](ADR-0007-signed-approvals.md) | Cryptographically signed, fail-closed gate records | Audit finding |
| [0008](ADR-0008-no-dependencies-no-database.md) | Zero runtime dependencies; JSON files, no database | Judgement — inspectability |
| [0009](ADR-0009-stance-over-phrase-matching.md) | Stance classification instead of an accepted-phrase list | Audit finding |
| [0010](ADR-0010-provenance-binding.md) | A self-hashed binding over every input that can change a number | Re-audit finding |
