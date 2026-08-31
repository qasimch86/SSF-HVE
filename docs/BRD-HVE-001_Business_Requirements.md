# BRD-HVE-001 — Business Requirements Document

| | |
|---|---|
| **Document** | BRD-HVE-001 |
| **System** | SSF-HVE — Hackathon Video Edition |
| **Version** | 1.0 |
| **Date** | 2026-08-30 |
| **Status** | As-built. Reconstructed from the delivered system; see [`README.md`](README.md). |
| **Owner** | Dr Qasim Ali |
| **Supersedes** | Nothing. This is the first requirements document for this repository. |

> **Provenance.** This document was written on 2026-08-30, after the system was complete. It
> did not govern the build. What did: [`../SCOPE_FREEZE.md`](../SCOPE_FREEZE.md) (committed
> 2026-08-29 18:58 UTC) and [`../EVAL_PROTOCOL.md`](../EVAL_PROTOCOL.md) (19:06 UTC).

---

## 1. Context

A researcher, a science teacher, or a small science-communication team wants to turn a paper
into a short explainer video. Drafting the script is no longer the bottleneck — a competent
language model does that in seconds, and does it well.

The bottleneck is the twenty minutes afterwards: paper open in one window, script in the
other, checking whether the script still says what the paper said. That check is unavoidable,
it does not get faster with practice, and it is where the work stops. A fluent draft can turn
an association into a cause, carry a mouse result into a sentence about people, drop the
limitation that decides how much a finding is worth, move a number between units, or obey an
instruction someone embedded in the source document — and **none of that is visible in the
reading**. The draft looks right either way.

That last property is the whole problem. A fabricated result and a measured one are
indistinguishable at the point of reading. Any system that produces science communication
must therefore be judged on whether its *checking* is inspectable, not on whether its output
looks good.

## 2. Problem statement

**Verification of generated science communication is expensive, manual, unrecorded, and
invisible in the artifact.** There is no trail showing what was checked, by whom, against
what, or what was left unresolved.

## 3. Stakeholders

| Stakeholder | Interest | How this system serves it |
|---|---|---|
| **Researcher / science communicator** | A script they can defend line by line | Every claim traced to source evidence; unresolved findings are preserved, not dismissed |
| **Reviewer / supervisor** | To approve a *specific* version, not "the output" | H1 binds an approval to one exact run and its exact artifacts |
| **Institution / publisher** | Auditability if a claim is later challenged | Full trajectory export: every prompt, every response, every finding, including rejected model output |
| **Hackathon judge** | To verify claims independently, quickly, with no API key | Replay-mode evaluation reproduces every published number offline in under 30 seconds |
| **Independent auditor** | To find where the evidence is weaker than the claim | `verify-provenance`, `PROVENANCE.md`, and a published list of withdrawn claims |

## 4. Business objectives

| ID | Objective | Measure of success | Outcome |
|---|---|---|---|
| **BO-1** | Make verification a first-class, recorded step rather than an invisible manual one | Every run produces a machine-readable record of what was checked and what remained open | **Met.** 100 run records; findings preserved verbatim including at HOLD |
| **BO-2** | Prevent an agent from declaring its own work finished | No agent status can open a gate or terminate a run as successful on its own authority | **Met.** Verifier vocabulary is advisory; the runner owns control flow; gates are human-only |
| **BO-3** | Make the evaluation independently reproducible at zero cost | A third party reproduces every published number with no API key | **Met.** Replay-by-default; clean-room extraction verified |
| **BO-4** | Report the result honestly, including when it is unflattering | Negative results published at the same prominence as positive ones | **Met, and load-bearing.** See §6 |
| **BO-5** | Keep the commercial system entirely separate | No commercial code, prompt, schema or document present | **Met.** Enforced by test, not by intention |

## 5. Scope

**In scope** — as frozen 2026-08-29 and amended once, on the record:

1. Ten synthetic research packets with planted, enumerated defects.
2. A dated gold table and a deterministic scorer.
3. A prompt-hash-keyed replay provider; full evaluation with no API key.
4. A direct-prompt baseline over identical inputs, as the comparator.
5. A staged workflow of four bounded roles: analyst, designer, verifier, producer.
6. Deterministic checks that run in code before any model verification.
7. A bounded correction loop with an explicit, declared rule at the bound.
8. Two human-only gates: H1 (an exact run), H2 (an exact package).
9. Ablation configurations, including two deliberately unsafe removal experiments.
10. Trajectory export for both the solution agents and the coding agent.
11. A local, read-only judge interface.
12. Judge-facing documentation, and this engineering set.

**Out of scope** — unchanged from the freeze: the commercial platform in any form; tenancy,
billing or administration; a generative video producer; real-paper sourcing and licence
clearance; any login, credential store or key-management interface; **any publication, upload
or submission path whatsoever.**

## 6. The headline business outcome, stated as it happened

**The workflow does not beat the baseline on the primary metric, because the baseline never
failed.** Thirty direct-prompt outputs — three independent samples of each of ten cases — and
not one asserted a planted defect. A frontier model given a well-formed record and a
competent prompt is already careful.

This is reported as the result rather than replaced with a metric that flatters the system.
Three consequences follow, and each is a business finding in its own right:

1. **The primary metric has no headroom on this case set.** Every comparison against the
   baseline is a comparison against zero. BO-4 is the objective that made this publishable.
2. **The measured gains are internal to the workflow**, not against the baseline: the staged
   claim map lifts clean-claim retention from 0.81 to 0.96; separating what a verifier
   *observed* from what it *recommends* halves malformed output.
3. **The strongest evidence in the project is a control that beat the shipped system.**
   `rm-bound-ok` — a configuration deliberately broken so that exhausting the correction limit
   counts as success — produces a byte-identical script carrying the same unresolved MAJOR
   finding, and scores **better** on the primary metric (0.10 against 0.20) purely by
   relabelling `HOLD` as `ACCEPT`. Removing the safety rule does not improve the work; it
   improves the score. The configuration that scores worse is the one that ships.

That third finding is the business case for the whole design: **a quality metric keyed on
output can be moved by a change that resolves nothing.** Verification has to be recorded, not
scored.

## 7. Constraints

| ID | Constraint | Origin |
|---|---|---|
| **BC-1** | No live publication, upload or submission path may exist in the code | Owner instruction; scope freeze |
| **BC-2** | No commercial source, prompt, blueprint or enterprise document may enter the repository | Owner instruction; enforced by `test_no_commercial_source_markers` |
| **BC-3** | No login system, credential database or key-management interface | Scope freeze |
| **BC-4** | Replay must be the default; live access requires an explicit flag and an environment key | Cost, reproducibility and judge access |
| **BC-5** | Deadline 2026-08-31 18:00 UTC | Hackathon rules |
| **BC-6** | Zero third-party runtime dependencies | Judges must be able to run it without a package resolution problem |

## 8. Assumptions

| ID | Assumption | If false |
|---|---|---|
| **BA-1** | Judges can run Python 3.10+ locally | The archive is still readable; every number is in `results/` |
| **BA-2** | Synthetic packets are a fair proxy for the *defect classes*, though not for real papers | External validity claims would need withdrawing — they are not made; see BRD §9 |
| **BA-3** | The captured model responses are representative of the model's behaviour on this task | Ablation comparisons hold internally; absolute rates would move |

## 9. Explicitly not claimed

Stated here because a business document that only lists benefits is not usable for a decision:

- **No claim about real papers.** The system has never been run against one.
- **No claim that the workflow improves output quality.** On the evidence, its unsafe rate is
  worse than a single direct prompt's.
- **No claim of scientific correctness.** "Verified" here means one narrow thing: a script
  does not assert a defect planted in its own source packet. It does not mean the science is
  sound, the finding generalises, or the paper is right.
- **No human validation.** The secondary human metric (VUOR) declared in the protocol was
  never measured, and no number is reported for it.
- **No statistical significance.** One sample per case for advanced configurations, three for
  the baseline. Differences of one case are within noise; counts are reported, not p-values.

## 10. Acceptance

The delivery is acceptable when a third party can, from the submitted archive alone and
without an API key: reproduce every published number; read the full trajectory of any run,
including its failures; confirm that no agent can approve its own work; and find the project's
own statement of what it does not prove. All four are demonstrated in
[`../REPRODUCTION.md`](../REPRODUCTION.md) and pinned by the test suite.

**Acceptance is a human decision and has not been taken.** Gates H1 and H2 are both
unapproved as of this document's date.
