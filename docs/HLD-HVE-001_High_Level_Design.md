# HLD-HVE-001 — High-Level Design

| | |
|---|---|
| **Document** | HLD-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Traces to** | SRD-HVE-001 |
| **Detail in** | ADD-HVE-001, ADR-0001…0010 |

> **Provenance.** Written after implementation, from the code. See [`README.md`](README.md).

---

## 1. Design premise

One sentence governs every structural decision:

> **A fabricated result and a measured one are indistinguishable at the point of reading.**

If that is true, then no amount of inspecting the *output* establishes trust, and the system
must instead make the *process* inspectable. Three consequences follow, and they explain the
whole shape of the system:

1. **Control flow belongs to code, not to a model.** An agent that decides when it is finished
   is a system with no verification step, only a confident one. Agents advise; the runner
   decides. (ADR-0003)
2. **Anything code can settle, code settles first.** Arithmetic, unit conversion, citation
   integrity and literal-phrase detection are not judgement calls. Spending a model call on
   them costs more and buys less. (ADR-0004)
3. **The record is the product.** A run that fails and preserves its failure is worth more
   than a run that succeeds and preserves nothing.

## 2. System context

```
        ┌──────────────────────────────────────────────────────────┐
        │                    SSF-HVE (this system)                 │
        │                                                          │
 owner  │   CLI ──┬─▶ workflow runner ──▶ run records              │
 ──────▶│         │        │                    │                  │
        │         │        ▼                    ▼                  │
        │         ├─▶ provider  ◀── fixtures   scorer ──▶ results  │
        │         │   (replay | live)             │                │
        │         │                               ▼                │
        │         ├─▶ gates H1/H2  ◀── owner   RESULTS.md          │
        │         │                                                │
 judge  │         ├─▶ local UI (127.0.0.1, read-only)              │
 ──────▶│         └─▶ packaging ──▶ submission archive             │
        │                                                          │
        └──────────────────────────────────────────────────────────┘
                              │
                              ╳  no upload, publish or submit path exists
```

The only external actor able to change state is the owner, at a terminal, at a gate. The judge
is a reader. There is no network egress on the default path.

## 3. The four bounded roles

Each role has a stated output and a stated prohibition. The prohibitions are the design.

| Role | Produces | Cannot | Enforcement |
|---|---|---|---|
| **A1 Scientific Analyst** | Claim map: evidence level, exact quantities and units, stated limitations, uncertainty, population scope, and any instruction-like text found in the source | Design narrative; approve anything | Structural — A1's output schema has no narrative field |
| **A2 Script Designer** | 60-second script and storyboard, written from the claim map | Receive the raw source packet | Structural for the source; **by instruction only** for inventing science (SRD FR-006) |
| **A3 Independent Verifier** | Findings with severity, references, quoted span, observation and recommended correction; one recommendation from `ACCEPT / EDIT / REWORK / HOLD` | Rewrite, approve, or decide what happens next | Structural — the vocabulary is closed and the runner ignores it as an instruction |
| **A4 Deterministic Producer** | Narration timing, caption cards, citation frames, render instructions, optional preview MP4 | Alter scientific wording; run before H1 | Gate-enforced; A4 is outside the evaluation loop entirely |

## 4. Control flow

```
source record
     │
     ▼
  A1 claim map ─────────────────────────────┐
     │                                      │ (embedded instruction
     ▼                                      │  recorded as data)
  A2 script                                 │
     │                                      │
     ├──────────────────────────────────────┘
     ▼
  DETERMINISTIC CHECKS  (code, before any model verification)
    CHECK-Q quantities      CHECK-U units
    CHECK-L limitations     CHECK-R references
    CHECK-I embedded instructions
     │
     ▼
  A3 verifier  ── findings ──▶ A2 correction ──┐
     │                                          │  at most 2 cycles
     │◀─────────────────────────────────────────┘
     ▼
  blocking findings remaining?
     │
     ├── no ──▶ terminal status ACCEPT / EDIT
     │
     └── yes, at the bound ──▶ HOLD
                                 findings preserved, unresolved
                                 counted UNSAFE by the scorer
     │
     ▼
  ══════ H1 ══════  a person approves this exact run
     │
     ▼
  A4 production
     │
     ▼
  ══════ H2 ══════  a person approves this exact package
     │
     ╳  nothing proceeds automatically. There is no next step in code.
```

**The single most important edge in this diagram is the one that goes to `HOLD`.** It is the
only place the system is allowed to say *I did not finish*, and the removal experiment
`rm-bound-ok` exists to demonstrate what happens when you delete it: the artifact is
byte-identical, and the score improves.

## 5. Evaluation harness

The harness is deliberately separate from the workflow, in both directions.

```
 evaluation/cases/*.json  ──┐
                            ├──▶ runner ──▶ results/runs/*.json ──┐
 fixtures/replay/*.json  ───┘                                     │
                                                                  ▼
 evaluation/gold/gold_table_*.json ──────────────────────────▶ scorer
                                                                  │
                                                                  ▼
                                             results/RESULTS.md + results.json
```

- The **scorer reads only** the gold table and the run records. It never sees the workflow.
- The **workflow never sees** the gold table, the detectors or the scorer (SRD FR-008, FR-009).
- The **detectors live in the case files**; the gold table is a dated, self-hashed snapshot of
  them, so a superseded table cannot be edited in place without detection.

Eight configurations are runnable, each one a row of the changelog:

| | Configuration | Purpose |
|---|---|---|
| 1 | `baseline` | One direct prompt. The comparator, never weakened. |
| 2 | `iter-1` | Deterministic checks alone |
| 3 | `iter-2` | Staged claim map |
| 4 | `iter-3` | Independent verifier, bounded loop |
| 5 | `iter-4` | Observation split from recommended action |
| 6 | `rm-bound-ok` | **Deliberately unsafe.** Bound counts as success |
| 7 | `rm-model-checks` | **Deliberately unsafe.** Deterministic checks routed through the model |
| 8 | `final` | The retained combination (= `iter-4`) |

## 6. Trust boundaries

| # | Boundary | Crossed by | Control |
|---|---|---|---|
| 1 | Source packet → agents | Rendered prose | Answer key excluded; one pinned exception (C10) |
| 2 | Model output → system | JSON response | Strict schema, fail closed, no repair path |
| 3 | Agents → gold material | *(must not be crossed)* | AST tests on the checks and on all three agents |
| 4 | Workflow → gate records | *(must not be crossed)* | Runner has no path to `record_approval`; AST test |
| 5 | Filesystem ← run identifier | CLI argument | Strict pattern; refused, never sanitised |
| 6 | Process → network | `--live` only | AST scan: one module may import a network library |
| 7 | Owner secret → disk | *(must not be crossed)* | Signatures only; test asserts the secret never serialises |
| 8 | Repository → outside world | Archive | Allowlist, then content inspection, then refusal |

## 7. Human gates

Gates are the one place a human is structurally required, so they are designed to fail in the
safe direction under every condition.

**H1 — one exact run.** Blocks production. Requires an interactive terminal and the word
`APPROVE` typed in full. Binds the run record, both canonical trajectory exports, the
narration, the candidate script and the configuration — each recomputed from the run record at
check time and compared for strict equality. Carries a signed expiry (30 days by default, the
window itself signed). The exported trajectory files are additionally re-read **from disk**, so
an export that diverges after approval invalidates it.

**H2 — one exact package.** Binds archive filename, size, SHA-256, manifest digest, git commit,
tree state and the video hash. A zip can be rebuilt between reading it and uploading it, so
approving "a submission" would be worthless; what is approved is a statement naming all of it
at once.

**Both.** HMAC-SHA-256 over canonical content, constant-time comparison, and **fail closed**:
no secret, no signature, an edited field, an unknown algorithm, an unknown schema version or an
expired record all read as *not approved*. There is no flag that turns verification off.

The absence of an approval blocks. The presence of a *status* never permits. That asymmetry is
the entire point (ADR-0005).

## 8. Local judge interface

A read-only local UI exists so a judge can see the evidence without a terminal. It is
constrained rather than trusted: stdlib WSGI only, bound to `127.0.0.1` and not configurable,
replay unless the server was started with an explicit flag, CSRF token on every POST, runs
written only to a throwaway session directory, no key-entry field, and **no control that
approves a gate**. Approval is a terminal-only act by design; adding a button would have
undone ADR-0005.

## 9. What this design does not do

- It does not make the output better. Measured: the workflow's unsafe rate is worse than the
  baseline's.
- It does not stop a determined operator. It makes what happened legible afterwards.
- It does not generalise to real papers. Ten synthetic packets, one author.
- It does not survive key compromise. Tamper-evident is not unforgeable.
