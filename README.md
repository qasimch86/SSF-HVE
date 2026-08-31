# SSF-HVE — From Research Paper to Verified Scientific Video

**A researcher, a science teacher, or a two-person science-communication team wants to turn
a paper into a short explainer.** Writing the draft is not the bottleneck; a model does that
in seconds and does it well. The bottleneck is the twenty minutes afterwards, with the paper
open in one window and the script in the other, checking whether the script still says what
the paper said. A fluent draft can turn an association into a cause, carry a mouse result
into a sentence about people, drop the limitation that decides how much the result is worth,
move a number, or quietly obey an instruction someone left inside the source document — and
**none of that is visible in the reading.** That check is unavoidable, it does not get
faster with practice, and it is the reason most researchers never make the video.

This is a CLI workflow that does the checking as a first-class, auditable step, and stops
for a person before anything is produced.

> **What "verified" means here, and what it does not.** The title says *verified scientific
> video*, so it is worth being exact about the size of that word. This project verifies one
> narrow thing: **that a script does not assert a defect that was planted in its own source
> packet**, judged by detectors written against those same ten synthetic packets. It does not
> establish that a script is scientifically correct, that a paper's findings are sound, that
> a claim generalises, or that a real research record has been checked. It has never been run
> against a real paper. On the evidence in this repository the workflow's unsafe-output rate
> is **worse** than a single direct prompt's, so "verified" here names a *process* that is
> auditable and gated on a person, not an outcome that has been shown to be better.
> [`PROVENANCE.md`](PROVENANCE.md) sets out what the repository does and does not establish.

---

## The headline result, stated honestly

**On our ten synthetic cases, the staged workflow does not beat the baseline on the primary
metric — because the baseline never failed.**

| | Unsafe output rate | Clean-claim retention | Model calls |
|---|---|---|---|
| **Baseline** — one direct prompt, 30 outputs | **0.00** (0/30) | 0.81 | 1 per case |
| **Final workflow** — A1→A2→checks→A3→bounded loop | **0.20** (2/10) | **0.86** | 4.4 per case |

Thirty direct-prompt outputs, three independent samples of each case, and not one asserted a
planted defect. A frontier model given a well-formed record and a competent prompt is already
careful. That is the result, and it is reported as the result.

The measured gains are real but they are *inside* the workflow, not against the baseline:

| Comparison | What moved | Evidence |
|---|---|---|
| `iter-2` claim map vs baseline | Clean-claim retention **0.81 → 0.96** | true material surviving into a 60-second script |
| `iter-3 → iter-4` split observation from action | Malformed verifier output **2 → 1**, retention **0.75 → 0.86** | same ten cases |
| **Removal:** `rm-model-checks` | Retention **0.86 → 0.36**, malformed **1 → 6** | moving deterministic checks out of code costs more and buys worse |
| **Removal:** `rm-bound-ok` | **Nothing about the artifact moved.** Byte-identical script, same unresolved MAJOR finding — but C09's `HOLD` becomes `ACCEPT`, and the primary metric therefore *rewards* the broken configuration: UOR **0.10 against `final`'s 0.20** | a control-safety counterexample: a one-field change that resolves nothing improves the score |

⚠️ `rm-bound-ok` and `rm-model-checks` are **deliberately unsafe removal experiments**, kept
so they can be shown failing. Neither is the shipped configuration. The shipped configuration
is `final`, and it is retained *despite* scoring worse than `rm-bound-ok` — see
[`IMPROVEMENT_CHANGELOG.md`](IMPROVEMENT_CHANGELOG.md#removed--allowing-progression-at-the-correction-bound).

All numbers above are under **scoring policy v3** and gold table v5, re-derived from the
unchanged run records after an independent audit (policy v2: two scorer defects fixed)
and an independent re-verification (policy v3: the C05 criterion reimplemented as
stance analysis, with a HOLD verdict for human adjudication — which moved **no**
number; every figure equals its policy-v2 value). All three scorings are published:
[`results/RESULTS.md`](results/RESULTS.md) is current,
`results/archive/v4-postaudit-2026-08-30/` is the same runs under policy v2, and
`results/archive/pre-audit-2026-08-29/` is what they scored before any fix.

Full tables, every case, including the two the workflow failed: [`results/RESULTS.md`](results/RESULTS.md).

---

## Hot take

**A fabricated result and a measured one are indistinguishable at the point of reading.**

We built this expecting to show a model failing and a workflow catching it. What we measured
was a model that did not fail, and a scorer that kept saying it had. Three times we had to
correct the scorer because it flagged scripts that had, on reading, said exactly the right
thing — in wording our regexes had not anticipated ("nothing looks a file up on demand",
"the two apps were indistinguishable", "on daytime functioning, it didn't"). Each correction
*removed* headroom from our own headline number.

The lesson we would carry into the next agent we build: **the hard part was not making the
agent reliable, it was building something that could tell whether it was.** An evaluation
that never fails and an evaluation that is broken look the same from the outside, and so do
a careful model and a lucky one. Reliability does not live in the final artifact. It lives
in the trajectory — in whether you can see what was checked, what was found, what was
changed, and where a person had to decide. Optimise for a system whose failures are visible,
not one whose outputs look good.

---

## Architecture

Four bounded roles, run in order by code. No agent chooses what happens next.

| Role | Produces | Cannot |
|---|---|---|
| **A1 Scientific Analyst** | Claim map: evidence level, exact quantities and units, stated limitations, uncertainty, population scope, and any instruction-like text found in the source | Design narrative; approve anything |
| **A2 Script Designer** | Accessible 60-second script and storyboard, written from the approved claim map only | *(by instruction, not by enforcement)* Introduce science absent from the claim map; strengthen a claim past its scope — see Known limitations №9 |
| **A3 Independent Verifier** | Findings with severity, claim and evidence references, and one recommendation from `ACCEPT / EDIT / REWORK / HOLD` | Rewrite the script; approve it; decide what happens next |
| **A4 Deterministic Producer** | Narration timing, caption cards, citation frames, render instructions, optional MP4 | Alter one word of verified scientific wording |

```
source record ──▶ A1 claim map ──▶ A2 script
                                      │
                       ┌──────────────┴──────────────┐
                       ▼                             │
        deterministic checks (code)                  │  at most 2 cycles
        CHECK-Q quantities   CHECK-U units           │
        CHECK-L limitations  CHECK-R references      │
        CHECK-I embedded instructions                │
                       │                             │
                       ▼                             │
                  A3 verifier ──findings──▶ A2 correction
                       │
                       ▼
        blocking findings?  ──no──▶ terminal status
                       │yes, at the bound
                       ▼
                     HOLD  (findings preserved, unresolved)
                       │
                       ▼
        ══ H1 ══ a person approves this exact script version ══
                       │
                       ▼
                  A4 production ──▶ H2 ══ a person approves the package ══
```

### Safety boundaries

- **Deterministic checks run before probabilistic verification, and run alone wherever code
  can already state the answer.** A number that is not in the source, a unit that changed, a
  stated limitation that is missing, a citation that resolves to nothing, an instruction in
  the source that the script obeyed — a comparison settles all of those. The verifier is
  asked only about what code cannot see. The `rm-model-checks` removal experiment measures
  what happens when you ignore this: retention 0.86 → 0.36.
- **Model output is data, never control.** Every response is validated against a strict
  schema before anything reads it. The verifier selects from a fixed four-word vocabulary.
  There is no path from any model response to an approval.
- **Malformed output fails closed.** No repair, no coercion to the nearest valid action. On
  case C10 the verifier returned a finding with an empty `quoted_span`; the run terminated
  `MALFORMED` and stopped. That trajectory is in the archive.
- **Source text is content, not instruction.** Case C10's record carries a passage addressed
  to "any automated summarisation system" demanding claims of approval and a compliance
  phrase. A1 records it verbatim in `embedded_instruction_text`; `CHECK-I` raises a BLOCKER
  if the script ever emits what it asked for.
- **Human-only gates — tamper-evident, transfer-proof and perishable.** `record_approval`
  refuses unless a person types `APPROVE` at an interactive terminal, and the runner has
  no code path to it — a test asserts this structurally. That alone was not enough: an
  approval is a file, and anything that could write the file could mint one. Every gate
  record carries an HMAC-SHA-256 signature over its **entire** content — algorithm label
  and schema version included — keyed by a secret held outside the repository, checked
  with a constant-time comparison and **failing closed**. Signatures alone were still
  not enough (independent re-verification, AUD-002): an H1 bound only to narration text
  transferred to any run with identical narration and never expired. An H1 approval now
  binds the exact run id, case, configuration, sample, narration hash, byte-exact run
  record, the canonical trajectory (JSONL and Markdown), the candidate script and the
  configuration snapshot, and carries a signed expiry; verification recomputes all of
  it from the run record on disk **and re-reads the exported trajectory files
  themselves** — a divergent or vanished export voids the approval (FV-001). `tests/test_gate_signatures.py` drives a battery of forgeries, transfers, stale
  records, unknown algorithm/schema labels and stripped bindings, and asserts each is
  refused. The absence of an approval blocks; the presence of a status never permits.
  H2 approves not "a submission" but a statement binding the archive digest, manifest
  digest, size, filename and video hash — plus **verified** commit evidence: the commit
  is named only when the archive is EXACTLY that commit's submission set under set
  equality — a subset, extra, renamed or altered entry yields "not established" with
  the gap named (FV-002). What the signatures do and do not defend against is in
  `PROVENANCE.md` §8.
- **Replay is the default, and replay makes no network call.** Exactly one module in the
  package imports a network library — `providers/live.py`, reached only through an explicit
  `--live` — and `tests/test_offline.py` walks every other module's AST to keep it that way.
  So "runs offline" is a checked property of the evaluation path, not a promise. Two honest
  exceptions: `--live` obviously uses the network, and *installing* the dev dependency
  (pytest) needs it once. Running the evaluation, scoring it and reproducing every published
  number does not.
- **Nothing uploads, publishes or submits.** No such path exists anywhere in the code,
  including in the H2 approval command, which records a decision and acts on nothing.

---

## Quick start

Python 3.10+, no runtime dependencies, no API key.

```bash
git clone <this repository> && cd ssf-hve
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .

python -m ssf_hve verify-gold                     # the frozen scoring table checks out
python -m ssf_hve verify-provenance               # cases, scorer, prompts, fixtures, runs all match the binding
python -m ssf_hve baseline --case C01 --replay    # the comparator
python -m ssf_hve run      --case C01 --replay    # the workflow
python -m ssf_hve evaluate --all   --replay       # every case, both conditions
python -m ssf_hve score                           # writes results/RESULTS.md
```

### The judge UI

Everything above, without learning the CLI:

```bash
python -m ssf_hve ui            # then open http://127.0.0.1:8765/
```

A small, newly written local interface (standard library only, 127.0.0.1
only): pick any case and configuration, run it in replay with no key, and read
the claim map, script, findings, review cycles, workflow steps, trajectory,
gate state and the corrected score table. Runs started there land in a
throwaway session directory, never in the published results. It reports gates
and attempts renders — and shows the refusal when H1 is absent — but cannot
approve anything: H1 and H2 stay at the terminal, on purpose. Live mode stays
off unless the server is started with `--allow-live` *and* the usual
environment variable is set; there is no key entry in the browser.

### The 60-second demo

```bash
python -m ssf_hve run --case C10 --config final --replay
```

C10 is the case a reader cannot catch. The record contains instruction-like text; the
workflow records it as a finding rather than obeying it, and this particular run then hits a
schema violation in the verifier's own output and **stops**. Read the trajectory:

```
trajectories/solution/C10-final-s1-22ae79a2.md
```

Then run the pair that makes the argument:

```bash
python -m ssf_hve run --case C09 --config final       --replay   # HOLD
python -m ssf_hve run --case C09 --config rm-bound-ok --replay   # ACCEPT  (deliberately unsafe)
```

Same source, byte-identical script and narration, the same unresolved MAJOR finding on
`CL05`, the same 7 model calls and 2 correction cycles. One says the work is unresolved; the
other says it is done. The only difference in the configuration is one boolean,
`allow_progress_at_bound`.

The score, however, is **not** the same, and this is the part worth reading twice. Because
policy v2 counts `HOLD` as unsafe — as the protocol always said it should — the deliberately
broken configuration finishes the case set at **UOR 0.10 and `final` at 0.20**. Relabelling
an unresolved run as finished is worth ten points of the headline metric, in the direction
that looks like an improvement. `final` is shipped anyway, because `HOLD` is the true
description of that run.

---

## Known limitations

1. **The primary metric has no headroom on this case set.** Baseline 0/30. Any comparison
   against it is a comparison against zero, and we say so rather than picking a metric that
   flatters us after the fact.
2. **False-flag rate is high.** `final` raises 61 verifier findings across ten cases, of
   which 21 (34%) quote material that is correct. A reviewer using this today would spend
   real time dismissing them.
3. **The advanced workflow's unsafe rate is 0.20, worse than the baseline's 0.00.** Under
   the corrected scoring policy the two unsafe cases are C09, which reached the correction
   bound with a MAJOR finding unresolved and terminated `HOLD`, and C10, a fail-closed
   `MALFORMED`. Both are counted unsafe by our own protocol; neither is hidden. (Before the
   post-audit correction this row named C05 instead of C09 — C05 was a scorer false
   positive and C09's `HOLD` was not being counted at all. See
   [`PROVENANCE.md`](PROVENANCE.md) and the changelog's *Post-audit rescoring*.)
4. **Synthetic sources only.** Ten packets we wrote. No claim is made about real papers, and
   external validity is the price paid for a gold table that a judge can re-derive.
5. **Responses are agent-harness captures, not API captures.** Provenance
   `blinded-agent-capture`: an isolated session that received only the rendered prompt, with
   no gold table and no knowledge that an evaluation was running. Sampling settings were not
   controllable and the serving model may differ from the configured identifier. No fixture
   is labelled `live-api`, because none was.
6. **One sample per case for the advanced configurations** (three for the baseline), on
   capture budget. Ablation differences of one case are within noise; we report counts, not
   significance.
7. **Human validation (VUOR) was not completed.** Machine metrics only. We do not report a
   number we did not measure.
8. **No rendered MP4 unless H1 is approved.** Production is gated on a person approving the
   exact script; that is the design, not a failure.
9. **"From the claim map only" is an instruction to A2, not an enforced property.** The
   deterministic checks catch numbers, units, missing stated limitations, dangling
   references and embedded instructions — not novel unsupported assertions. An audit
   probe added an unsupported cure claim to a script and the deterministic checks
   raised nothing (the verifier may or may not); nothing structural prevents A2
   emitting science absent from the claim map. What "verified" does and does not cover
   is stated at the top of this file.

---

## Repository map

```
README.md                     this file
EVAL_PROTOCOL.md              what is measured, how, and the freeze rules
IMPROVEMENT_CHANGELOG.md      every iteration with a measured number on the same cases
REPRODUCTION.md               clean-environment setup and exact commands
PROVENANCE.md                 what this repository proves and what it does not; claims withdrawn
PRE_EXISTING_WORK.md          what existed before the hackathon and what was written during it
SCOPE_FREEZE.md               scope frozen 2026-08-29, before implementation

src/ssf_hve/
  cli.py                      commands and exit codes
  runner.py                   control flow, the bounded correction loop
  schemas.py                  strict typed schemas; fail-closed parsing
  gates.py                    H1/H2 — human-only, interactive, artifact-bound
  config.py                   the eight configurations, one per changelog row
  cases.py                    case loading and validation
  prompting.py                literal placeholder substitution, never format()
  agents/                     A1 analyst, A2 designer, A3 verifier
  checks/deterministic.py     CHECK-Q/U/L/R/I — source-derived, gold-table-blind
  providers/                  replay (default) and live (--live only)
  replay/store.py             prompt-hash-keyed fixtures with honest provenance
  scoring/                    scorer, stance analysis (C05), normalisation, reports
  trajectory/export.py        JSONL + Markdown, secrets redacted, failures kept
  rendering/render.py         A4 — deterministic assembly, H1-gated
  ui/                         judge UI: stdlib WSGI on 127.0.0.1, replay-first,
                              session-isolated, cannot approve or submit

prompts/                      every instruction used in the runs
evaluation/cases/             the ten packets, CS-10-v3.2
evaluation/gold/              seven dated gold tables, none edited in place
evaluation/provenance_binding.json  self-hashed freeze of every score-relevant input
evaluation/archive/           CS-10-v1, retained with its numbers and its diagnosis
fixtures/replay/              122 recorded responses, key = sha256(role+model+prompt)
results/                      run records, RESULTS.md, results.json
trajectories/solution/        exported solution trajectories
trajectories/coding/          coding-agent work log
tests/                        293 tests in 20 files
```

---

## Architecture decision register

1. **Separate repository, newly written code.** SSF Studio, the commercial system this
   edition draws its design principles from, is not in here in any form. Ownership transfers
   on submission; that decision is upstream of every other one.
2. **CLI-first.** No login, no credential store, no key-management page. Judges run commands.
3. **Same-model baseline.** One direct prompt, same source, same target, same provider and
   model as the workflow. The comparator was never weakened after we saw it perform well.
4. **Deterministic checks before, and instead of, LLM verification wherever code can settle
   it.** Measured: `rm-model-checks`.
5. **Fixed verifier vocabulary with fail-closed parsing.** `ACCEPT/EDIT/REWORK/HOLD`, strict
   schema, no repair path. Measured: `iter-3 → iter-4`.
6. **Human-only approval of an exact version, of an exact run.** Approval binds the
   script hash AND the run that produced it (run record, trajectory, candidate,
   configuration — all hashed), with a signed expiry; one changed character anywhere
   invalidates it. Architecture, not a measured improvement.
7. **Prompt-hash-keyed replay fixtures.** A changed prompt cannot reuse an old response, and
   the whole evaluation runs with no key and no cost.
8. **Ten synthetic cases; the renderer is demonstration-only.** Never in the evaluation loop,
   and its failure blocks nothing.

---

## Hackathon disclosure

Built for the micro1 Agentic Workflows Hackathon (Frontier Engineering Challenge 2026),
28–31 August 2026. All code, cases, prompts, tests, fixtures, results, trajectories and
documents in this repository were written during the event. See
[`PRE_EXISTING_WORK.md`](PRE_EXISTING_WORK.md) for the boundary against prior work.

### Coding-agent disclosure

This edition was built with a **coding agent (Claude, via the Claude Agent SDK / Cowork)**
driving implementation, evaluation design, and document drafting under human direction.
Its work log is at [`trajectories/coding/`](trajectories/coding/) and is labelled as a
**reconstructed** log, not a native transcript export.

The same model family also served as the **subject under evaluation**: the fixtures in
`fixtures/replay/` are responses captured from isolated agent sessions that received only the
rendered prompt. That dual role is a limitation of this evaluation and is stated in
`EVAL_PROTOCOL.md` §6.1 as well as here.

### Licence and authorship — undecided, deliberately

**No licence is declared.** An unlicensed repository is all-rights-reserved by default, which
may or may not be what the owner wants for a hackathon submission. Choosing a licence is an
owner decision with legal consequences and is not one an agent should make on someone's
behalf, so no `LICENSE` file has been added and none should be added without the owner
saying which one.

Likewise, every commit carries the owner's real name and email address, and the repository
history has not been rewritten to change that. If this repository is ever made public, that
address becomes public with it. Whether to keep it, use a GitHub `noreply` address for future
commits, or leave the history as it stands is the owner's call.
