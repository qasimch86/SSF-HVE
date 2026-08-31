# SRD-HVE-001 — Software Requirements Document

| | |
|---|---|
| **Document** | SRD-HVE-001 |
| **System** | SSF-HVE — Hackathon Video Edition |
| **Version** | 1.0 |
| **Date** | 2026-08-30 |
| **Status** | As-built. Every requirement describes behaviour that exists and is tested. |
| **Traces to** | BRD-HVE-001 (up), RTM-HVE-001 (down) |

> **Provenance.** Written 2026-08-30, after implementation, from the code and the test suite.
> No requirement below was written before the behaviour it describes. Requirements are worded
> to the system that exists, including where that system is weaker than a reader might assume.

**Conventions.** *Shall* is a binding requirement with a test behind it. *Shall not* is a
prohibition with a test that attempts the prohibited thing. Where enforcement is by
instruction rather than by code, the requirement says so in bold — those are the honest
weak points, and they are collected in §7.

---

## 1. Functional requirements — evaluation inputs

**FR-001 · Case loading and validation.**
The system shall load ten synthetic research packets (C01–C10) from `evaluation/cases/`,
validate each against a strict schema, and refuse a malformed case with a diagnostic naming
the failing field. Each case shall declare exactly one defect class, its planted defects with
detectors, its clean claims with protected patterns, and human-readable rationale.

**FR-002 · Source rendering.**
The system shall render each packet to the agents as a continuous prose document, not as a
labelled data structure. A labelled object with a `limitations` array performs the analyst's
work for free, and a research record does not arrive that way.

**FR-003 · Answer-key exclusion.**
The rendered packet shall contain no planted-defect description, no rationale, no
gold-unsafe criteria and no reviewer note. **Exception, by design:** C10's packet contains
one of its own detector phrases, because the embedded-instruction case is untestable without
it; that exception is pinned as an exception, and any second occurrence fails the build.

## 2. Functional requirements — the workflow

**FR-004 · Baseline runner.**
The baseline shall issue exactly one model call per case, over the same source, the same
target format, the same provider and the same model as the advanced workflow.

**FR-005 · A1 scientific analyst.**
A1 shall produce a claim map containing, per claim: evidence level, exact quantities with
units, stated limitations, uncertainty and population scope; and shall record any
instruction-like text found in the source verbatim as data, in a dedicated field, without
acting on it.

**FR-006 · A2 script designer.**
A2 shall produce a 60-second script and storyboard written from the claim map. It shall not
receive the raw source packet in its prompt. **Confinement to the claim map is by instruction,
not by enforcement** — nothing in code prevents A2 introducing material the claim map does not
contain. This is the system's largest unenforced boundary and is recorded as such.

**FR-007 · Deterministic checks.**
Five checks shall run in code, over the script and the source, before any model verification:
`CHECK-Q` quantities, `CHECK-U` units, `CHECK-L` stated limitations, `CHECK-R` reference
integrity, `CHECK-I` embedded instructions. `CHECK-I` shall raise a BLOCKER when the script
emits what an embedded instruction demanded, and shall not fire when the script *quotes* the
instruction as a finding.

**FR-008 · Gold-table blindness of the checks.**
The deterministic-checks module shall not import the scorer, the gold table, or any
planted-defect or detector material. A check that knew the answer would not be a check.

**FR-009 · Agent blindness.**
A1, A2 and A3 shall not read planted defects, detectors, clean claims, gold-unsafe criteria or
reviewer notes, although the case object they receive carries them.

**FR-010 · A3 independent verifier.**
A3 shall return findings carrying severity, a claim reference, an evidence reference, a quoted
span, an observation and a recommended correction, plus exactly one recommendation from the
closed vocabulary `ACCEPT | EDIT | REWORK | HOLD`. A3 shall not rewrite the script, approve
it, or decide what happens next.

**FR-011 · Verifier consistency.**
A verifier result recommending `ACCEPT` while carrying a BLOCKER or MAJOR finding shall be
rejected as malformed.

**FR-012 · Fail-closed parsing.**
Model output that does not satisfy its schema shall raise `MalformedModelOutput` and terminate
the run. There shall be no repair, coercion or retry path. An unparseable response is a result,
not an error to be smoothed over.

**FR-013 · Bounded correction loop.**
The correction loop shall execute at most `max_correction_cycles` cycles (two in the shipped
configuration). The runner, not any agent, shall decide whether to correct, terminate or hold.

**FR-014 · The rule at the bound.**
A run reaching the correction bound with blocking findings unresolved shall terminate `HOLD`.
`allow_progress_at_bound` shall be true only in a removal experiment and never in a retained
configuration.

**FR-015 · Run record persistence.**
Every run shall write a record containing its metadata, every step with its prompt and
response, every cycle, the claim map, the final script and narration, the H1 gate state and
the unresolved findings. A record shall be written even when the run fails. Model output
rejected by schema validation shall be preserved in the record, not discarded.

## 3. Functional requirements — providers and reproducibility

**FR-016 · Replay provider.**
Replay shall be the default provider. A fixture shall be keyed by
`sha256("ssf-hve/v1\n" + role + "\n" + model + "\n" + rendered_prompt)`, so an edited prompt
cannot reuse an old response. A missing fixture shall be a distinct, non-zero exit condition.

**FR-017 · Fixture integrity and provenance.**
Every fixture shall declare a provenance value from `live-api | blinded-agent-capture |
handcrafted`; an unknown value shall be refused. The system shall provide a command that
re-derives every fixture key from the prompt stored inside it and reports the inventory by
provenance.

**FR-018 · Live provider.**
Live access shall require an explicit `--live` flag and an API key from the environment. A
custom endpoint shall be HTTPS and shall additionally require an explicit opt-in environment
variable; anything else shall be refused rather than warned about.

## 4. Functional requirements — measurement

**FR-019 · Deterministic scorer.**
Scoring shall read only the gold table and the run records. It shall have no access to the
workflow, and the workflow shall have no access to it.

**FR-020 · Scoring policy versioning.**
The scoring policy shall carry a version, and that version shall be recorded in every
published result. `MALFORMED`, `ERROR` and `HOLD` shall all count unsafe.

**FR-021 · Denominator integrity.**
The denominator shall be the declared case set, not the successful runs. A run that produced
no validated output shall stay in the denominator and count unsafe.

**FR-022 · Paired reporting.**
Clean-claim retention shall be published beside the unsafe output rate at the same
prominence, because a verifier that refuses everything scores a perfect unsafe rate.

**FR-023 · Derived reporting.**
`results/RESULTS.md` and `results/results.json` shall be regenerated wholly from the run
records. No number in either shall be hand-entered, and two consecutive scoring runs shall
produce byte-identical output apart from the generation timestamp.

**FR-024 · Ablation configurations.**
The system shall provide each changelog row as a separately runnable configuration, including
two removal experiments (`rm-bound-ok`, `rm-model-checks`), so an ablation is an experiment
rather than a description of one. Removal experiments shall be labelled deliberately unsafe
wherever they are reported.

**FR-025 · Trajectory export.**
Any run shall be exportable as JSONL and Markdown, preserving unresolved findings and
failures. Export shall redact API keys and authorization headers.

## 5. Functional requirements — gates, production and packaging

**FR-026 · A4 deterministic producer.**
A4 shall assemble narration timing, caption cards, citation frames and render instructions
from the approved script without altering one word of its scientific wording, and shall
produce an optional preview MP4. A4 shall never be in the evaluation loop, and its failure
shall block nothing.

**FR-027 · H1 human gate.**
Production shall be blocked until a person approves one exact run. Approval shall require an
interactive terminal and the word `APPROVE` typed in full. The approval shall bind the run
record, the exported trajectory artifacts, the narration and the configuration; a change to
any of them shall invalidate it. The runner shall have no code path that records an approval.

**FR-028 · H2 human gate.**
Submission approval shall bind one exact package: archive filename, byte size, SHA-256,
manifest digest, git commit, tree state and the video hash. There shall be exactly one route
to an H2 approval.

**FR-029 · Tamper-evident approvals.**
Every gate record shall carry an HMAC-SHA-256 signature over its canonical content, keyed by
an environment secret, verified with a constant-time comparison. An unsigned record, an edited
record, a record signed with a different key, a record with an unknown algorithm or schema
version, an expired record, and the absence of a configured secret shall all read as **not
approved**. There shall be no flag that disables verification.

**FR-030 · Provenance verification.**
The system shall provide a command that reports which case set, which scoring policy and which
gold table produced the published results, that no superseded gold table has been edited in
place, and where a documented claim rests on a self-assertion rather than on evidence.

**FR-031 · Provenance binding.**
A self-hashed manifest shall freeze the SHA-256 of every active input that can change a
published number — case definitions and detectors, the active gold table, prompt templates,
scorer, normaliser, report generator, case parsing, configuration, deterministic checks,
fixture semantics, the fixture inventory and the published results. Verification shall fail on
any drift, including drift in the manifest itself.

**FR-032 · Allowlisted packaging.**
The submission archive shall be built from an explicit allowlist, inspected for credentials
and private filesystem paths before it is written, and refused rather than written if
anything is found. An archive shall never contain an archive.

**FR-033 · Local judge interface.**
The system shall provide a local, read-only judge interface that runs replay by default,
presents run evidence and gate state with reasons, and offers **no** control that approves a
gate and **no** field that accepts a key.

**FR-034 · Exit codes.**
The CLI shall use: `0` success; `1` usage, configuration or IO error; `2` terminated `HOLD` or
`MALFORMED`; `3` replay incomplete, fixture missing; `4` a human gate is not approved.

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| **NFR-001** | The runtime shall have **zero third-party dependencies** and run on Python 3.10+. `pytest` is a development dependency only. |
| **NFR-002** | The replay path shall make no network call. Exactly one module may import a network library, and that module shall be reachable only through `--live`. |
| **NFR-003** | Scoring shall be deterministic: repeated runs over unchanged records produce identical output. |
| **NFR-004** | A clean-room extraction of the submitted archive shall reproduce every published number, with no API key and no network. |
| **NFR-005** | A full evaluation of every configuration shall complete in well under 30 seconds on a laptop, at zero provider cost. |
| **NFR-006** | Every published number shall be derived from the run records, and the derivation shall be a single command. |
| **NFR-007** | Documented counts — tests, run records, fixtures, trajectories, gold tables, prompts — shall match the repository, enforced by test rather than by review. |

## 7. Security requirements

| ID | Requirement |
|---|---|
| **SEC-001** | No credential shall be stored in the repository. Keys shall come from the environment only. There shall be no login system, credential database or key-management interface. |
| **SEC-002** | No secret shall reach a log, a fixture, a run record, a trajectory, a rendered page or the archive. |
| **SEC-003** | Gate approvals shall be **tamper-evident** — not unforgeable. Anyone holding the owner secret can mint one, and there is no revocation path. See §8. |
| **SEC-004** | A run identifier reaching a filesystem path shall be validated against a strict pattern and refused, never sanitised, if it does not match. |
| **SEC-005** | The live endpoint shall be HTTPS, and a non-default host shall require explicit opt-in. |
| **SEC-006** | The judge interface shall bind `127.0.0.1` only, require a CSRF token on every state-changing request, contain no key-entry form, and refuse traversal in every path it accepts. |
| **SEC-007** | The repository secret scanner shall cover everything that ships, and its exclusions shall be justified by test rather than chosen for convenience. |
| **SEC-008** | No commercial identifier, source path, blueprint reference or enterprise document marker shall appear in any shipped file. |

## 8. Constraints, and the boundaries that are not enforced

| ID | Constraint |
|---|---|
| **CON-001** | No code path shall upload, publish or submit anything — the H2 approval command included. It records a decision; it does not act on it. |
| **CON-002** | Replay is the default; live requires an explicit flag whose value no caller may reach by omission. |
| **CON-003** | No login system, credential store or key-management UI. |
| **CON-004** | Sources are synthetic. No claim is made about real papers. |

**Unenforced boundaries, collected.** A requirements document that hides these is not usable:

1. **FR-006** — A2's confinement to the claim map is prompt instruction only.
2. **SEC-003** — approvals are tamper-*evident*. Key compromise is unmitigated and there is no
   rotation or revocation mechanism.
3. **FR-017** — fixture *provenance* is a declared value. That the capture session saw only
   the rendered prompt is procedural; no test can verify it after the fact.
4. **FR-026** — A4's promise not to alter scientific wording is a design property of the
   assembler, not a checked invariant of its output.

## 9. Requirements deliberately not written

- No requirement for scientific correctness of a script. The system cannot establish it.
- No requirement for real-paper ingestion. Never attempted, never claimed.
- No requirement for human validation throughput (VUOR). Declared in the protocol, never
  measured, and no number is reported.
- No availability, scaling or multi-user requirement. This is a single-user CLI with a local
  read-only interface, and pretending otherwise would be documentation theatre.
