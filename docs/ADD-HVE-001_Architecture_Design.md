# ADD-HVE-001 — Architecture and Detailed Design

| | |
|---|---|
| **Document** | ADD-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Traces to** | HLD-HVE-001, SRD-HVE-001 |

> **Provenance.** Written after implementation, from the code. See [`README.md`](README.md).

---

## 1. Technology decisions

| Choice | Decision | Rationale |
|---|---|---|
| Language | Python 3.10+ | Available on every judge's machine; `match`-free so 3.10 suffices |
| Runtime dependencies | **None** | A judge must never hit a dependency resolution problem (ADR-0008) |
| Dev dependency | `pytest==8.2.2`, pinned | One tool, one version |
| Persistence | JSON files on disk | Inspectable with `cat`. A database would hide the evidence (ADR-0008) |
| Web layer | `wsgiref` from the standard library | The UI is a viewer, not a product |
| Media | `ffmpeg` if present, optional | Its absence blocks nothing |
| Schema validation | Hand-written, fail-closed | A permissive validator is worse than none (ADR-0002) |

## 2. Module structure

```
src/ssf_hve/
  __init__.py              version, CASE_SET_ID
  __main__.py              python -m ssf_hve
  cli.py                   argument parsing, command dispatch, exit codes
  config.py                the eight configurations, as frozen dataclasses
  paths.py                 every path in one place; run-identifier validation
  cases.py                 case loading, validation, prose rendering
  schemas.py               strict schemas; MalformedModelOutput; GateRecord
  prompting.py             template rendering
  runner.py                control flow, the bounded loop, run records
  gates.py                 H1/H2, signing, verification, expiry
  submission.py            H2 binding statement over one exact package
  packaging.py             allowlist, inspection, archive, manifest digest
  provenance.py            provenance verification and the binding manifest
  agents/
    a1_analyst.py          claim map
    a2_designer.py         script and correction
    a3_verifier.py         findings and one recommendation
  checks/
    deterministic.py       CHECK-Q/U/L/R/I — gold-table-blind
  providers/
    base.py                Provider, ModelResponse
    replay.py              prompt-hash-keyed fixtures (default)
    live.py                the only module that may touch the network
  replay/store.py          fixture keying, integrity, provenance
  scoring/
    scorer.py              policy version, detectors, per-case scoring
    stance.py              sentence-level stance classification
    normalise.py           number words, units, contractions
    report.py              RESULTS.md and results.json
  trajectory/export.py     JSONL + Markdown, redacted
  rendering/render.py      A4; production spec and preview, one source of truth
  ui/                      local read-only judge interface (stdlib WSGI)
```

**The dependency rule.** `scoring/` may not be imported by `agents/`, `checks/` or `runner.py`.
`checks/deterministic.py` may not import `cases`' gold material. Both are enforced by AST
tests rather than by convention, because a convention is not a control.

## 3. Data flow

```
evaluation/cases/C0N.json
        │  cases.load_case()  → Case (frozen dataclass)
        ▼
   Case.source_text()  ──▶ prose packet (answer key excluded)
        │
        ▼
 prompting.render(template, vars) ──▶ rendered prompt
        │
        ▼
 provider.complete(role, prompt)
        │   replay: key = sha256("ssf-hve/v1\n"+role+"\n"+model+"\n"+prompt)
        │   live:   HTTPS, explicit flag, key from environment
        ▼
 schemas.parse_or_fail_closed()  ──▶ typed object  |  MalformedModelOutput
        │
        ▼
 runner.execute()  ──▶ RunRecord ──▶ results/runs/<run_id>.json
        │
        ├──▶ trajectory/export.py  ──▶ trajectories/solution/<run_id>.{jsonl,md}
        │
        ▼
 scoring/scorer.py  (gold table + run records only)
        │
        ▼
 scoring/report.py  ──▶ results/RESULTS.md, results/results.json
```

## 4. Key design elements

### 4.1 The run identifier is a typed thing, not a string

A run identifier reaches the filesystem twice — selecting a record to read, and naming the
trajectory files to write. `paths.validate_run_id` accepts only
`C<NN>-<config>-s<N>-<8 hex>` and **refuses rather than sanitises**, because silently repairing
a malformed identifier would read a different run and hide the attempt. `run_record_path` and
`trajectory_path` are the only two places the conversion happens, and each re-checks
containment after resolution.

### 4.2 Sampling enters the fixture key, the prompt does not

Three baseline samples per case need three different responses to the *same* prompt.
`SampledProvider` scopes the role to `role#sN` so the key differs while the prompt stays
byte-identical. The alternative — perturbing the prompt — would have made the samples
incomparable.

### 4.3 Rejected model output is preserved

When schema validation raises, the response has not yet been recorded by the normal path.
`SampledProvider.last_call` retains it and `_record_rejected_call` writes it into the run
record. Without this, the most interesting artifact in a failing run — the output that broke
the contract — would be the one thing missing. This is why the archive holds more model calls
than fixtures.

### 4.4 Scoring policy is versioned, and the version travels with the number

`SCORING_POLICY_VERSION` is stamped into every `ConfigScore` and into `results.json`. A number
without its policy version is not interpretable; the project has already had one policy change
that moved published figures in both directions, and the archived pre-audit results exist so
both scorings can be compared directly.

### 4.5 Stance classification, not phrase matching

Detecting whether a script honestly reported a null result was originally a list of accepted
phrases — which is tuning a detector to the outputs it scores. `scoring/stance.py` replaces
that with sentence-level classification: negation scope, p-values, confidence intervals that
span zero, conclusory language, and questions distinguished from assertions. The criterion is
about what a sentence *does*, not which words it happens to use (ADR-0009).

### 4.6 The provenance binding

Verifying that gold tables self-hash proved nothing about the *active* case files, which carry
the detectors and can change every score. `evaluation/provenance_binding.json` freezes the
SHA-256 of every input that can change a published number — cases, adjudications, prompts,
scorer, normaliser, report generator, case parsing, configuration, deterministic checks,
fixture semantics, all 122 fixtures, and the published results — and hashes itself.
Verification fails on any drift, including drift in the manifest (ADR-0010).

### 4.7 The render spec has one source of truth

The production spec and the ffmpeg preview once carried independent literals and drifted:
the instructions declared 1920×1080 while the preview rendered 1280×720, so the package
described a render nobody had performed. Both now derive from one constant, the preview is
labelled as a pipeline proof rather than the deliverable, and a test fails if they can
diverge again.

## 5. Error and failure model

| Condition | Handling | Exit |
|---|---|---|
| Malformed model output | `MalformedModelOutput`; run terminates; response preserved | 2 |
| Verifier `ACCEPT` with a blocking finding | Rejected as malformed — an inconsistent result is not a result | 2 |
| Correction bound reached, findings open | Terminal `HOLD`; findings preserved; counted unsafe | 2 |
| Fixture missing for an exact prompt | Distinct exit; never silently regenerated | 3 |
| H1 or H2 not approved | Blocked with a stated reason | 4 |
| Gate secret absent | Fails **closed** — treated as not approved | 4 |
| Unknown case, config or identifier | Diagnostic naming the valid values | 1 |
| `ffmpeg` absent or failing | Package complete without the MP4; nothing blocked | 0 |
| Archive inspection finds a secret or private path | Archive **not written** | 1 |

The pattern throughout: **the absence of a positive signal blocks; the presence of a status
never permits.**

## 6. Concurrency, scale and state

There is none, deliberately. Single process, single user, files on disk, no locks, no server
state beyond a throwaway session directory. `SSF_HVE_RESULTS_DIR` redirects all run and gate
output so a test process can never write into the published tree — a defect that existed
until an audit found it.

## 7. Extension points

| To add | Touch | Do not touch |
|---|---|---|
| A new case | `evaluation/cases/`, a new dated gold table | Any existing gold table |
| A new configuration | `config.py`, `ABLATION_ORDER` | `runner.py` control flow |
| A new deterministic check | `checks/deterministic.py` | Anything importing `scoring/` |
| A new provider | `providers/`, subclass `Provider` | The replay key derivation |
| A new agent role | `agents/`, `prompts/`, `schemas.py` | The verifier's closed vocabulary |

**Adding a new input that can change a score requires re-running `bind-provenance`**, and the
verification will tell you if you forgot.

## 8. Known architectural weaknesses

Recorded here rather than left for a reviewer to find:

1. **A2's confinement is prompt instruction only.** Nothing in code prevents it introducing
   science absent from the claim map. The strongest unenforced boundary in the system.
2. **Detectors are regular expressions over prose.** Stance classification narrows the gap but
   does not close it; a sufficiently creative paraphrase can still evade a detector, and three
   scorer corrections plus two audit findings are the evidence that this is real.
3. **Gate signing has no key rotation or revocation.** A leaked secret validates every past and
   future approval, permanently.
4. **The case set is ten packets by one author**, and the same model family both authored the
   evaluation and was the subject under evaluation. That dual role is a limitation of the
   whole result, not just of this design.
5. **The gold table in force is retrospective.** It was written after the runs it scores, in
   response to an audit, and says so in its own payload.
