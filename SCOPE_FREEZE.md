# SSF-HVE — Scope Freeze

**Frozen:** 2026-08-29 19:05 UTC (15:05 EDT)
**Authority:** SSF-HVE-002 §5 (controlling), micro1 Agentic Workflows Hackathon brief (pp. 1–7).
**Deadline:** 2026-08-31 18:00 UTC — verified against the official HackerEarth challenge page on 2026-08-29.

Nothing is added to this list after Sunday 2026-08-30 16:00 UTC (12:00 EDT).

## In scope
1. Ten synthetic research packets (C01–C10) with planted, enumerated defects.
2. A pre-declared, dated gold table and a deterministic scorer.
3. A replay provider adapter keyed by prompt hash; full evaluation runs with no API key.
4. A direct-prompt baseline runner over identical inputs.
5. A staged advanced runner: A1 analyst, A2 script designer, A3 independent verifier, A4 deterministic producer.
6. Deterministic pre-checks that run before any model verification.
7. A bounded correction loop, at most two cycles, with an explicit rule at the bound.
8. Two human-only gates: H1 (exact script version), H2 (submission package).
9. Ablation configurations per changelog row, plus two removal experiments.
10. Trajectory export (JSONL + Markdown) for the solution agents and the coding agent.
11. One demonstration production package; rendered MP4 only if it costs no critical-path time.
12. Five judge-facing documents.

## Out of scope
- The SSF Studio commercial platform in full: tenancy, billing, ledgers, payments, administration, public site.
- The SSF-00–13 blueprint library and the commercial prompt library.
- Enterprise BRD / SRD / ADD / ADR / RTM documentation.
- A generative video-producer agent.
- Public-paper sourcing and licence clearance.
- Any live publication, upload or submission path.
- Any login system, credential store or API-key management UI.

## Boundary
SSF-HVE is a new repository containing newly written code. No file, prompt, schema or
document from the SSF Studio commercial tree is copied into it. The commercial tree is
read-only evidence of prior work and is disclosed in `PRE_EXISTING_WORK.md`.

---

## Amendment 1 — 2026-08-30, owner-authorised

**Recorded, not edited.** The list above stands exactly as it was frozen. This amendment says
what changed, when, on whose instruction, and what did not change.

**Instruction.** The owner asked for the engineering documentation a real project carries —
business requirements, software requirements, high-level and architecture design, decision
records, traceability, test strategy, operations and a data dictionary.

**What this changes.** The out-of-scope line *"Enterprise BRD / SRD / ADD / ADR / RTM
documentation"* excluded importing or reproducing the **commercial SSF Studio** documentation
set. That exclusion is unchanged and absolute: no commercial requirement, design, decision or
traceability material is copied, adapted or paraphrased here, and
`tests/test_secrets.py::test_no_commercial_source_markers` fails the build if any commercial
identifier appears in a shipped file. What is added is a **newly written, original** document
set describing *this* repository and nothing else, in `docs/`.

**What it does not change.** No requirement in the added documents introduces a capability.
Every one describes behaviour that already exists and is already tested; the documents were
written *from* the code, not the other way round, and each says so on its own front page. The
evaluation design, the case set, the scoring policy, the gold table and the published numbers
are untouched by this amendment.

**Two disclosures the owner should read before submitting.**

1. **This amendment is past this document's own deadline.** The freeze says *"Nothing is added
   to this list after Sunday 2026-08-30 16:00 UTC."* The instruction arrived after that, and
   the documents were written after it. The deadline was self-imposed and the owner is
   entitled to move it; the fact is recorded here rather than left for an auditor to notice.
2. **The documents are retrospective.** They are as-built specifications reconstructed from a
   finished system. They are not evidence that the system was built to a specification, and
   `docs/README.md` says so in its first paragraph. What genuinely preceded the code is this
   file and `EVAL_PROTOCOL.md`, both committed before the first run.
