# TSP-HVE-001 — Test Strategy and Plan

| | |
|---|---|
| **Document** | TSP-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Traces to** | SRD-HVE-001, RTM-HVE-001 |

> **Provenance.** Written after the suite existed, describing it. See [`README.md`](README.md).

---

## 1. What this suite is for

Not coverage. The suite exists to make specific claims in the documentation **false-if-broken**.
Every judge-facing claim of the form *"the system cannot X"* has a test that attempts X and
asserts refusal, because a prohibition nobody tries is a hope.

The test that best expresses the strategy is `test_no_commercial_source_markers`: the boundary
against the commercial codebase is not a promise in a README, it is a scan that fails the build.

## 2. Scale and levels

**293 tests across 20 files**, all passing in the repository and in a fresh extraction of the
submitted archive. The distribution is deliberately lopsided: the largest files are the
adversarial ones, because that is where the claims are.



| Level | What it covers | Where |
|---|---|---|
| **Unit** | Normalisation, schemas, detectors, stance classification, path validation, endpoint resolution | `test_normalise`, `test_schemas`, `test_scoring`, `test_input_safety` |
| **Component** | Runner control flow, the bounded loop, replay keying, trajectory export, rendering spec | `test_runner_boundaries`, `test_replay`, `test_trajectory`, `test_render_spec` |
| **Contract** | The scorer against the protocol prose, via an oracle written from the prose rather than from the code | `test_scoring_policy` |
| **Adversarial** | Forged approvals, tampered bindings, traversal, endpoint redirection, CSRF | `test_gate_signatures`, `test_provenance_binding`, `test_input_safety`, `test_ui` |
| **Structural** | AST scans proving a module *cannot* reach something | `test_checks`, `test_offline`, `test_gates`, `test_ui` |
| **Documentation** | Every count and every published table in a shipped document matches the repository | `test_documented_counts` |
| **End-to-end** | CLI exit codes; the published results regenerate deterministically | `test_cli`, `test_scoring` |

## 3. Techniques that carry unusual weight here

**Oracle tests.** `tests/test_scoring_policy.py` contains a table of expected verdicts written
from `EVAL_PROTOCOL.md`'s prose, not by calling the scorer. It is the only test that could have
caught the defect it now guards: the scorer disagreeing with its own declared policy. A test
written from the implementation would have agreed with the bug.

**Structural (AST) tests.** Some properties cannot be tested by calling a function, because
they are about what a module *can reach*. `test_checks_never_read_the_gold_table`,
`test_agents_never_read_the_planted_defects_or_detectors`,
`test_only_the_live_provider_can_reach_the_network`,
`test_runner_cannot_reach_record_approval` and `test_the_ui_imports_only_stdlib_and_ssf_hve`
walk module ASTs and fail on a forbidden reference. These convert architectural intentions
into build failures.

**Adversarial construction.** `tests/test_gate_signatures.py` does not check that signing works;
it writes the files an attacker would write — unsigned, edited, re-signed with another key,
copied to another run, given an unknown algorithm, expired, stripped of binding data — and
asserts each reads as *not approved*.

**Pinned exceptions.** Where a rule has a legitimate exception, the exception is asserted, not
waived. C10's packet must contain one of its own detector phrases or the embedded-instruction
case is untestable; `test_only_C10_has_a_detector_phrase_that_appears_in_its_own_packet`
asserts that C10 is the **only** such case, so a real leak elsewhere still fails.

**Documentation as a test target.** Counts drift silently and cost a reader's trust in the
numbers that matter. `test_every_count_claim_in_every_shipped_document_is_true` scans every
Markdown file in the archive for count claims and checks each against the filesystem.

## 4. Isolation

`SSF_HVE_RESULTS_DIR` redirects run records, gate records and trajectories into a temporary
directory created by `tests/conftest.py`. A test process cannot write into the published
evaluation. This was itself a defect once — `GATES_DIR` was pinned to the repository, so a
failing test could leave a gate approval in the shipped tree.

Every secret in the suite is generated inside the test process. The owner secret appears in no
test, no fixture and no file.

## 5. Entry and exit criteria

**Entry.** The tree is clean, the provenance binding verifies, and the archive builds without
refusal.

**Exit, for a release:**

1. Full suite passes in the repository.
2. Full suite passes in a **fresh extraction of the built archive**, with no `.git`, no
   network and no API key.
3. `python -m ssf_hve verify-gold` reports MATCH.
4. `python -m ssf_hve verify-provenance` reports all relationships hold.
5. `python -m ssf_hve score` reproduces the published table to the decimal.
6. `python -m ssf_hve fixtures` verifies every key against its stored prompt.

Criterion 2 is the one that matters. Passing in the repository proves the code works where it
was written; passing in the extraction proves the *submission* works.

## 6. What this suite cannot prove

Read this section before trusting the one above.

1. **That the fixtures are honest captures.** Provenance is a declared value. That the capture
   session saw only the rendered prompt is procedural, and no test can verify it afterwards.
2. **That the detectors are right.** They encode one author's reading of ten packets. Three
   scorer corrections before the audit and two findings from it are the evidence that this
   class of error recurs. `test_every_shipped_c05_output_matches_its_recorded_adjudication`
   pins agreement with a *recorded human reading* — which is stronger than nothing and weaker
   than correctness.
3. **That A2 does not invent science.** There is no test, because there is no enforcement.
   SRD FR-006 records this as the system's largest unenforced boundary.
4. **That approvals are unforgeable.** They are tamper-evident. Key compromise is unmitigated.
5. **That the system works on real papers.** Never attempted. Ten synthetic packets.
6. **That the workflow improves output quality.** The suite verifies the *measurement* is
   sound. The measurement says the workflow's unsafe rate is worse than the baseline's.
7. **Human validation.** VUOR was declared in the protocol and never measured. No number is
   reported for it.

## 7. Regression policy

- A defect found in the field gets a test **before** a fix, named for the failure, not the
  function. `test_the_audit_probe_editing_active_c05_now_fails_verification` is named for the
  probe that found it.
- A scorer change that moves a published number requires a new dated gold table; existing
  tables are never edited in place, and `verify-provenance` checks all of them.
- Both scorings are kept when a policy changes, so the effect can be compared directly.
- A claim removed from the documentation stays in `PROVENANCE.md` as a withdrawn claim.
