# PRE_EXISTING_WORK.md

Ground rule 02 of the challenge: *make it clear what existed before the competition and what
you added.* This file draws that line as sharply as we can draw it.

---

## 1. The short version

| | |
|---|---|
| **Everything in this repository** — code, prompts, ten cases, gold tables, fixtures, tests, results, trajectories, documents | **Written during the event**, 29–31 August 2026 |
| **The design principles behind it** | **Pre-existing.** They come from SSF Studio, a commercial system the author has been building since before the hackathon |
| **Any SSF Studio source code, blueprint, prompt-library entry, enterprise document, database, artifact or customer data** | **Not present in this repository, in any form** |

Nothing was copied and renamed. Nothing was paraphrased from a commercial prompt. The
implementation was written from scratch against a scope frozen on the first evening
(`SCOPE_FREEZE.md`), and the test suite enforces the boundary mechanically —
`tests/test_secrets.py::test_no_commercial_source_markers` fails the build if a marker of the
commercial tree appears anywhere outside the four files that discuss the boundary in prose.

---

## 2. What existed before the hackathon

**SSF Studio** is a commercial research-to-video platform the author has been developing
independently of this competition. What pre-dates the event is the *thinking*, and it is
worth being specific about which ideas are not new here:

| Pre-existing idea | Where it shows up in this edition |
|---|---|
| A reviewer that recommends and never decides | A3's fixed four-word vocabulary and the runner owning control flow |
| Deterministic checks running before, and instead of, model review | `src/ssf_hve/checks/deterministic.py`, and the `rm-model-checks` removal experiment |
| Human approval bound to an exact artifact version | `src/ssf_hve/gates.py`, H1 and H2 |
| Reliability living in the trajectory rather than the final artifact | `src/ssf_hve/trajectory/export.py` and the README hot take |
| Separating scientific analysis from narrative design | The A1 / A2 boundary |
| Treating source text as content and never as instruction | The A1 prompt, `CHECK-I`, and case C10 |

An **observed failure mode** from that prior work motivated the whole submission: a stage in
the commercial system once reported a count that was not present in the file it claimed to
have read, and certified its own result from it — twice. That incident is the origin of this
project's hot take. It is described here in prose because the argument needs it; **the
artifacts, logs, database records and code from that incident are not included**, and no
number from them is cited anywhere in this repository.

The commercial system's blueprint library, prompt library, BRD/SRD/ADD/RTM document set,
recorded corpus and runtime database were all **deliberately excluded** at scope-freeze time.
None of them would have improved a rubric score enough to justify disclosing them.

## 3. What was consulted while building this edition

Read for scope and requirements; none of it is redistributed here:

- The micro1 Agentic Workflows Hackathon problem statement (10 pp.) and the HackerEarth
  challenge page — rubric, ground rules, deliverables, timeline, participation terms.
- `SSFHVE002_Suitability_Assessment_v1.0.docx`, an internal assessment written before
  implementation began, which set the scope this edition was built to.
- The author's own SSF Studio design materials, as background only, for the ideas listed in
  §2.

## 4. What was created during the event

All of it. Nothing in this list existed on 29 August 2026:

- `src/ssf_hve/` — every module: CLI, runner, schemas, gates, config, cases, prompting,
  the three agent adapters, the five deterministic checks, both providers, the replay store,
  the scorer, stance analysis and normaliser, report generation, trajectory export, the A4
  producer, and the judge UI (`ui/` — newly written during the post-audit remediation,
  standard library only, no code from any other application).
- `prompts/` — six newly written prompt files (five role instructions plus one appended
  observation note). Short, task-specific, written for this edition. No commercial prompt
  text.
- `evaluation/cases/` — ten synthetic research packets, written for this project, plus their
  planted defects, clean claims, deterministic detectors and human-readable rationale.
- `evaluation/gold/` — seven dated gold tables, none edited in place. What their dates do and
  do not establish is set out in [`PROVENANCE.md`](PROVENANCE.md); the phrase "frozen before
  the runs it governs" is withdrawn.
- `evaluation/archive/cs-10-v1/` — the superseded first case set, retained with its numbers.
- `fixtures/replay/` — 122 captured responses.
- `results/` — 100 run records, `RESULTS.md`, `results.json`, and the pre-audit archive.
- `trajectories/` — eight solution trajectories and the coding-agent work log.
- `tests/` — 293 tests across 20 files.
- `README.md`, `EVAL_PROTOCOL.md`, `IMPROVEMENT_CHANGELOG.md`, `REPRODUCTION.md`,
  `SCOPE_FREEZE.md`, and this file.

## 5. The boundary, and what we can and cannot prove about it

The honest position: **we cannot anchor this boundary to a commercial-repository commit,
because the working copy supplied to this edition is not a git repository.** An earlier
internal document referenced commit `1456228`; we checked, and there is no `.git` directory in
the supplied tree, so that reference could not be verified. Rather than assert a tag we have
not confirmed, we state the limitation.

What *can* be verified, from this repository alone:

- Its git history begins on **2026-08-29** with an empty scaffold and contains every step of
  the build. `git log --reverse --format='%ad %s' --date=iso` shows the whole event.
- The first commit contains no source code at all — only ignore rules.
- The secret and boundary scanner runs as part of the test suite, over every tracked file.
- Every prompt used in every run is committed, and every fixture contains the full rendered
  prompt it was captured against.

## 6. Sanitized pre-existing evidence

**None is included.** No artifact, log, metric, database extract or screenshot from the
pre-existing commercial system appears in this repository or in the submission archive. A
disclosure candidate was prepared and *not* used; the owner's approval was neither given nor
assumed. Every number in this submission was measured by the code in this repository, on the
cases in this repository, during the event.

## 7. Naming

The project is submitted under the neutral name **SSF-HVE**. It is not branded with, and does
not represent, the commercial product or its vendor.
