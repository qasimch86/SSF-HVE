# SSF-HVE — engineering documentation

**These are as-built documents. Read this paragraph before the rest.**

A business requirements document, a software requirements specification and an architecture
design document normally *precede* the code they govern. These did not. They were written on
**2026-08-30**, after the system was finished, reconstructed from the code, the tests, the
evaluation protocol and the scope freeze. Presenting them as though they had driven the build
would be a false provenance claim, and this project has already withdrawn several of those —
see [`../PROVENANCE.md`](../PROVENANCE.md). Every document in this directory carries the same
statement on its own front page.

**What genuinely preceded the implementation**, and can be checked in git:

| Artifact | Committed | What it fixed in advance |
|---|---|---|
| [`../SCOPE_FREEZE.md`](../SCOPE_FREEZE.md) | 2026-08-29 18:58 UTC | What is in and out of scope; the commercial boundary |
| [`../EVAL_PROTOCOL.md`](../EVAL_PROTOCOL.md) | 2026-08-29 19:06 UTC | What is measured, how, the metric, and the success conditions |

Everything else here is a description of what was built, not a specification it was built to.
The value of writing it down anyway is that it makes the system reviewable as a whole: a
reader can now check a requirement against a design element, against code, against a named
test, and find any of them missing.

---

## The document set

| ID | Document | What it answers |
|---|---|---|
| **BRD-HVE-001** | [Business Requirements](BRD-HVE-001_Business_Requirements.md) | Who is this for, what problem does it solve, what does success mean, what is explicitly not attempted |
| **SRD-HVE-001** | [Software Requirements](SRD-HVE-001_Software_Requirements.md) | 26 functional, 7 non-functional, 8 security requirements and 4 constraints — each numbered and testable |
| **HLD-HVE-001** | [High-Level Design](HLD-HVE-001_High_Level_Design.md) | The four bounded roles, the control flow, the two gates, the evaluation harness, the trust boundaries |
| **ADD-HVE-001** | [Architecture & Detailed Design](ADD-HVE-001_Architecture_Design.md) | Module-by-module design, data flow, schemas, failure modes, extension points |
| **ADR-0001…0010** | [Decision records](adr/) | Ten decisions, each with the alternatives, the decision, the consequences and the evidence |
| **RTM-HVE-001** | [Traceability Matrix](RTM-HVE-001_Requirements_Traceability_Matrix.md) | Every requirement → design element → module → named test |
| **TSP-HVE-001** | [Test Strategy & Plan](TSP-HVE-001_Test_Strategy_and_Plan.md) | What is tested, how, what is deliberately not tested, and what the suite cannot prove |
| **OPS-HVE-001** | [Operations Runbook](OPS-HVE-001_Operations_Runbook.md) | Install, run, score, gate, package; every exit code and every failure mode |
| **DD-HVE-001** | [Data Dictionary](DD-HVE-001_Data_Dictionary.md) | Field-level definitions for the case, gold table, run record, fixture, gate record and binding schemas |

## Reading order

- **A judge with fifteen minutes:** [`../README.md`](../README.md), then RTM-HVE-001, then
  [`../results/RESULTS.md`](../results/RESULTS.md).
- **An auditor:** [`../PROVENANCE.md`](../PROVENANCE.md), then TSP-HVE-001 §6 (*what the suite
  cannot prove*), then the RTM, then ADR-0004 and ADR-0009.
- **An engineer picking this up:** BRD → HLD → ADD → OPS.
- **Someone deciding whether to trust a number:** run
  `python -m ssf_hve verify-provenance` and read `../PROVENANCE.md`.

## The rule these documents follow

No requirement in this set describes behaviour that does not exist. Where the system is
weaker than a reader might assume, the requirement says so rather than being written to the
ambition. Three examples, so the pattern is visible:

- **FR-005** records that A2 is confined to the claim map *by instruction, not by
  enforcement*. Nothing in code stops it inventing science.
- **NFR-004** claims clean-room reproducibility of the published numbers, and nothing about
  real papers, because the case set is synthetic.
- **SEC-003** claims approvals are *tamper-evident*, not *unforgeable* — anyone holding the
  owner secret can mint one, and there is no revocation path.

`tests/test_rtm.py` fails the build if this directory cites a module or a test that does not
exist, so the set cannot quietly rot as the code moves.
