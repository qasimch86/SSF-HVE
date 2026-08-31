# PROVENANCE.md — what this repository proves, and what it does not

This document exists because an independent audit found that several provenance
claims in this submission were stronger than the evidence behind them. Rather than
soften the wording and move on, the claims are withdrawn here, in one place, with the
evidence that replaces them.

Everything below is checkable. Run:

```bash
python -m ssf_hve verify-provenance
```

It reads the repository, not this document, and prints the same relationships.

---

## 1. The claims that are withdrawn

| Withdrawn claim | Where it appeared | Why it does not hold |
|---|---|---|
| "The gold table was frozen before evaluation." | README, review pack, submission form draft | The v3-family gold tables and the baseline replay fixtures arrive in **the same commit** (`c788282`). Git cannot separate them, so it cannot support the ordering. |
| "Frozen before any run on CS-10-v3." | `GOLD_TABLE_FREEZE.txt` | Same commit. It is a statement of intent, not a record of one. |
| `"declared_before_any_run_on_this_case_set": true` | Gold tables v2, v3, v3.1, v3.2 | A self-assertion written into the file by its own author. Nothing verifies it. |
| "CS-10-v3.2 was declared final before the configurations were run. Nothing has changed since." | `IMPROVEMENT_CHANGELOG.md` | The first sentence is unsupported (above). The second is now false: gold table v4 exists. |
| "The correction lowers the measured baseline unsafe output rate from 2/30 to 0/30." | `GOLD_TABLE_FREEZE.txt`, revision 3.1 | Wrong attribution. 2/30 was really observed — but at `c788282` the *active* table was already v3.2, and what took 2/30 to 0/30 was the `5ecaa1b` normaliser correction, not revision 3.1. See section 4. |
| "Baseline unsafe output rate falls from 1/30 to 0/30 as a result." | `GOLD_TABLE_FREEZE.txt`, revision 3.2 | The 1/30 figure matches no observed state: exact extraction gives 2/30 before the normaliser correction and 0/30 after. See section 4. |
| "UOR 2/30 → 1/30 → **0/30**" across v3 → v3.1 → v3.2 | `IMPROVEMENT_CHANGELOG.md` | Wrong as a *sequence attribution*. Both endpoints are real (2/30 observed at `c788282`, 0/30 from `5ecaa1b`), but the per-revision ladder matches neither the historical track nor the current-code counterfactual. See section 4. |
| "Four dated gold tables, each frozen before the runs it governs." — withdrawn | `PRE_EXISTING_WORK.md` | There are now seven, two of them explicitly retrospective, and "frozen before" is withdrawn for all of them. |

None of these withdrawals changes a published metric. They change what the repository
is entitled to claim about *when* things happened.

---

## 2. The chronology git actually records

Commit times are recorded by git. Commit *messages* are written by their author and
prove nothing beyond the fact that the author wrote them.

| Commit | Time (UTC) | What entered the repository |
|---|---|---|
| `eea0ba9` | 18:57:55 | Repository initialised |
| `483f547` | 19:04:48 | Ten synthetic packets, CS-10-v1 |
| `49c4161` | 19:05:16 | Gold table v1 |
| `1e635bf` | 19:06:12 | `EVAL_PROTOCOL.md` |
| `0529ca3` | 19:17:47 | Runner, checks, scorer, gates, CLI |
| `5988d6d` | 19:28:52 | CS-10-v2 packets and gold table v2 |
| **`c788282`** | **19:41:30** | **CS-10-v3 packets, gold tables v3 / v3.1 / v3.2, *and* the 30 baseline replay fixtures — all in one commit** |
| `5ecaa1b` | 19:42:20 | `cannot`/`can't` normalisation; results refreshed |
| `1fd425f` | 19:54:23 | Replay fixtures for the final advanced configuration |
| `905d526` | 20:11:09 | Replay fixtures for all eight configurations |
| `cc14e04` | 22:51:02 | Fixture-key and rejected-response fixes (pre-audit checkpoint) |

**What this supports.** The gold tables for the v3 family were in the repository
before the *advanced-configuration* captures at 19:54 and 20:11. That ordering is
real and is the one that matters most for the ablation comparisons, because the
advanced runs are the ones the design claims are about.

**What this does not support.** Any claim that the gold table was fixed before the
**baseline** was measured. The gold tables and the baseline fixtures share a commit,
and the commit message itself announces a baseline result — so the baseline had
already been scored when that commit was written. The gold table was then revised
three times in response to what scoring the baseline revealed. That is a legitimate
and disclosed activity, but it is the opposite of a preregistration.

---

## 3. The declared timestamps are labels, not clock readings

Every gold table carries a `created_utc` field. In five of six tables that value is
**later than the commit that introduced the file**, which is impossible for a real
clock reading:

| Gold table | Declared `created_utc` | Commit that added it |
|---|---|---|
| v1 | 2026-08-29T19:30:00Z | 19:05:16 |
| v2 | 2026-08-29T21:10:00Z | 19:28:52 |
| v3 | 2026-08-29T22:00:00Z | 19:41:30 |
| v3.1 | 2026-08-29T23:05:00Z | 19:41:30 |
| v3.2 | 2026-08-29T23:25:00Z | 19:41:30 |
| **v4 (post-audit)** | **2026-08-30T01:37:33Z** | 2026-08-30 02:15:37 — a real clock reading, *earlier* than its commit, as a real one must be |

The v1–v3.2 values are round numbers on five-minute boundaries. They were written as
labels, and they should be read as labels. `verify-provenance` prints this comparison
as a **NOTE** on every run so that nobody has to take this section's word for it.

The historical tables are **not** edited to fix this. Editing a frozen artifact to
make it look better is the failure mode this whole document is about. They stay as
they are, and this file says what they are worth.

---

## 4. The corrected baseline ladder — two tracks, both stated

The freeze record contained two mutually inconsistent causal claims: revision 3.1
said the baseline went "from 2/30 to 0/30", and revision 3.2 said it went "from 1/30
to 0/30". An earlier version of this section then over-corrected in the opposite
direction, declaring the historical figures "not supported by anything now in the
repository". The independent re-verification showed that is false, and it reproduces:

**Track 1 — historically observed, reproduced by exact extraction.** Extract the
commits themselves (`git archive <commit>`), run each commit's own `score` over its
own committed 30 baseline run records:

| Commit | State | Baseline unsafe | Cases |
|---|---|---|---|
| `c788282` | v3.2 active, pre-normaliser-correction code | **2/30** | C01 sample 2, C01 sample 3 |
| `5ecaa1b` | contraction normalisation corrected | **0/30** | — |

So 2/30 was a real observation — made when v3.2 was already the active table — and
what moved it to 0/30 was the **normaliser correction** at `5ecaa1b`, not a gold-table
revision. Neither freeze-record claim survives: 3.1's attribution is wrong, and 3.2's
"1/30" matches no state at all.

**Track 2 — the later-code counterfactual.** The same 30 shipped baseline records,
rescored under each table's own frozen detectors **by the current scorer and
normaliser** (`python -m ssf_hve verify-provenance`, section 6 — which now labels
itself as exactly this):

| Case set | Baseline unsafe | Unsafe outputs |
|---|---|---|
| CS-10-v3 | **1/30** | C05 sample 2 |
| CS-10-v3.1 | **0/30** | — |
| CS-10-v3.2 | **0/30** | — |
| CS-10-v4-postaudit | **0/30** | — |
| CS-10-v5-stance | **0/30** | — |

The two tracks differ because the current normaliser is not the `c788282` normaliser.
Neither is "the" number without its label; this repository now prints Track 2 with its
label, and states Track 1 here with the commits that reproduce it.

**What this changes.** The per-revision prose ladder (2/30 → 1/30 → 0/30 credited to
v3 → v3.1 → v3.2) is withdrawn as a sequence attribution, and the earlier claim that
2/30 "is not supported by anything now in the repository" is withdrawn as an
over-claim in the other direction — exact historical extraction supports it.

**What this does not change.** The direction of every correction. Historically the
observed number went 2/30 → 0/30; counterfactually 1/30 → 0/30 → 0/30. Every scorer
correction *lowered* our own headline number, removing headroom from the metric we
most wanted to show an improvement on. The baseline is 0/30 under every current
scoring, and the primary metric has no headroom. Nothing here rescues that.
---

## 5. What the fixtures are, exactly

All 122 replay fixtures carry provenance `blinded-agent-capture`. They are recorded
model responses produced by an agent session that was shown the rendered prompt and
nothing else. Verify the inventory with `python -m ssf_hve fixtures`, which also
re-derives every fixture key from its stored prompt.

**What is enforced by a test, and what is procedural.** Be precise about this, because
the difference matters:

| Guarantee | How it is held |
|---|---|
| The deterministic checks never reach the gold table | **Test.** `tests/test_checks.py::test_checks_never_read_the_gold_table` walks the module AST. |
| A1, A2 and A3 never read planted defects, detectors or clean claims | **Test.** `tests/test_checks.py::test_agents_never_read_the_planted_defects_or_detectors` walks all three agent module ASTs. Needed because a `Case` object carries the answer key and nothing in the type system withholds it. |
| The rendered packet an agent sees carries no defect description, rationale, unsafe criteria or reviewer note | **Test.** `tests/test_checks.py::test_the_rendered_source_packet_excludes_the_answer_key`. |
| C10 is the only packet containing one of its own detector phrases (it must, or the embedded-instruction case is untestable) | **Test.** `tests/test_checks.py::test_only_C10_has_a_detector_phrase_that_appears_in_its_own_packet`. |
| The capture session itself saw only the rendered prompt | **Procedural.** This is a statement about how the fixtures were produced. No test can verify it after the fact, and this document does not pretend otherwise. |

They are **not** live API calls, and this repository does not claim they are. `live-api`
and `handcrafted` exist as provenance values in the schema; no fixture uses them.

---

## 6. Gold tables v4 and v5 are retrospective and say so; the binding holds the rest

`evaluation/gold/gold_table_2026-08-30_v4-postaudit.json` and
`evaluation/gold/gold_table_2026-08-30_v5-stance.json` were created **after** the runs
they score — v4 in response to the audit, v5 in response to the independent
re-verification of the post-audit remediation. Each carries
`declared_before_any_run_on_this_case_set: false`, `retrospective: true`, and a
`provenance_statement` recording both facts. Neither is a preregistration and neither
is presented as one.

The v4 changes are documented in `IMPROVEMENT_CHANGELOG.md` under *Post-audit
rescoring*; the v5 change (the stance-based C05 criterion and scoring policy v3, which
moved **no** published number) under *Post-re-verification rescoring*. Every earlier
scoring is preserved unmodified — pre-audit at `results/archive/pre-audit-2026-08-29/`,
v4 at `results/archive/v4-postaudit-2026-08-30/` — so all three scorings can be
compared directly.

**What `verify-provenance` now proves, and what it proved before.** The re-verification
demonstrated that the earlier verifier certified gold-table self-hashes and result
stamps while an *active case file* could be edited — changing scores — without
failing verification. Since the binding (`evaluation/provenance_binding.json`,
self-hashed) the verifier's first section recomputes the SHA-256 of every active case
definition, the active gold table, every prompt template, the scorer, normaliser and
report source, case parsing, configuration, the deterministic checks, the fixture
semantics, the complete fixture inventory, the complete run-record inventory, and the
content of `results.json`. Any drift — including files present but unbound — is a
**MISMATCH** and a non-zero exit. `tests/test_provenance_binding.py` replays the
re-verification's own probe (editing an active C05 detector in a temporary copy) and
asserts verification fails naming the file. Regenerating the binding is a deliberate,
git-visible act (`python -m ssf_hve bind-provenance`).

---

## 7. Summary for a reviewer in a hurry

- The **numbers** are reproducible from the shipped artifacts. `python -m ssf_hve score`
  regenerates every published table from the run records.
- The **ordering claims** were overstated. Gold tables preceded the advanced-configuration
  captures; they did not precede the baseline measurement, and the tables were revised in
  response to it. The evaluation is best described as **retrospectively refined and
  rescored, unblinded to observed outputs, with every historical artifact preserved** —
  not as preregistered or frozen before baseline.
- The **timestamps inside the gold tables are labels**, not measurements, for every table
  before v4; v4 and v5 carry real clock readings.
- The **primary metric has no headroom** on this case set: baseline 0/30. That was the
  finding before the audit and it survives the audit unchanged.

---

## 8. What the gate signatures do and do not defend against

The H1/H2 records are HMAC-SHA-256 signatures over the record's complete
canonical content (every field, including the algorithm label, the schema
version, the expiry and the full binding), keyed by a secret held only in the
owner's environment. Since the post-audit rework, an H1 record additionally
binds the exact run id, case, configuration, sample, narration hash,
byte-exact run-record hash, canonical trajectory hash, candidate-script hash
and configuration hash, and it expires (default 30 days, chosen and signed at
approval time). Verification recomputes every one of those from the run
record on disk at check time.

**Defended against** — an adversary who can write files but cannot read the
owner's environment or change the code:

- minting an approval by writing a plausible file (no valid signature);
- editing any field of a real approval, the binding included;
- moving a valid approval to a different artifact, gate, purpose, or — for
  H1 — a different run, even one with byte-identical narration;
- modifying, or removing after a verified binding, the exported trajectory
  files a judge actually reads: verification re-reads `trajectories/…​.jsonl`
  and `.md` from disk and requires byte-identity with the canonical texts
  derived from the run record (final-verification finding FV-001);
- replaying a stale approval past its signed expiry;
- announcing an unknown signature algorithm or schema version (fails closed
  before any cryptography);
- for H2, swapping the archive or video underneath an approval, and claiming
  a build commit the archive does not match by **set equality**: the commit is
  named only when the archive's entries are exactly the commit's submission
  set and every entry is byte-identical — a subset, superset, renamed or
  altered archive is refused with the gap named (finding FV-002).

**Not defended against**, stated plainly rather than implied away:

- a process that runs with the owner's environment: it can read
  `SSF_HVE_GATE_SECRET` and sign anything. The gate constrains the workflow
  and file-writing attackers, not the owner's own shell.
- an adversary who can modify `gates.py` or the verifier that calls it.
  Signature checking is only as trustworthy as the code performing it.
- key compromise after the fact. There is no key rotation and no revocation
  list; the only mitigations are the signed expiry window and deleting the
  record. A leaked secret means every record it ever signed verifies for
  whoever holds it, until expiry.
- weak secrets. No minimum key strength is enforced; the owner is trusted to
  choose a long random value.

This is the honest boundary of an environment-keyed HMAC. Anything stronger —
hardware keys, asymmetric signatures with revocation, an external timestamping
authority — was judged out of scope for a hackathon submission and is listed
so that the absence is a documented decision, not an oversight.
