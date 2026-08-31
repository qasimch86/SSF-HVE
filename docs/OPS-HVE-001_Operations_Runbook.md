# OPS-HVE-001 — Operations Runbook

| | |
|---|---|
| **Document** | OPS-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Audience** | Anyone running this system: judge, auditor, or the owner |

> **Provenance.** Written after implementation, from the shipped CLI. See [`README.md`](README.md).
> Paths below use `<REPO>` for wherever you extracted or cloned the repository.

---

## 1. Install

Python **3.10 or newer**. No other runtime requirement.

```bash
cd <REPO>
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -e .
```

If virtual-environment creation is slow or unavailable, everything below works with
`PYTHONPATH=src` instead. `pip install -e .` also brings `pytest` for the test suite; the
runtime itself needs nothing.

**No API key is required.** Replay is the default and reads recorded responses from disk.

## 2. Verify before trusting anything

Run these four in order. If any fails, stop.

```bash
python -m ssf_hve verify-gold           # the active gold table hashes to its recorded value
python -m ssf_hve verify-provenance     # case set, policy, gold table, and what git cannot prove
python -m ssf_hve fixtures              # every fixture key re-derived from its stored prompt
python -m pytest -q                     # the full suite
```

`verify-provenance` prints **NOTE** lines that are disclosures, not failures — places where a
claim in the documents rests on a self-assertion. They are meant to be read.

## 3. Reproduce the published numbers

```bash
python -m ssf_hve evaluate --all --config baseline --samples 3 --replay
python -m ssf_hve evaluate --all --config iter-1          --replay
python -m ssf_hve evaluate --all --config iter-2          --replay
python -m ssf_hve evaluate --all --config iter-3          --replay
python -m ssf_hve evaluate --all --config iter-4          --replay
python -m ssf_hve evaluate --all --config rm-bound-ok     --replay
python -m ssf_hve evaluate --all --config rm-model-checks --replay
python -m ssf_hve evaluate --all --config final           --replay
python -m ssf_hve score
```

Under a minute in total, at zero provider cost.

> **`evaluate` and `run` return a non-zero exit code when any case ends `HOLD`, `MALFORMED` or
> `ERROR`.** That is intended behaviour, not a failure of the run. Do not wrap these in
> `set -e` and expect them to continue.

`score` rewrites `results/RESULTS.md` and `results/results.json`, both derived wholly from the
run records. Two consecutive runs differ only in the generation timestamp.

## 4. Single runs and the evidence

```bash
python -m ssf_hve baseline --case C01 --replay                   # the comparator
python -m ssf_hve run --case C10 --config final --replay         # fails closed, MALFORMED
python -m ssf_hve run --case C09 --config final --replay         # HOLD at the bound
python -m ssf_hve run --case C09 --config rm-bound-ok --replay   # ACCEPT — deliberately unsafe
python -m ssf_hve export-trajectory --run <RUN_ID>               # JSONL + Markdown
```

The last pair is the argument of the whole project: identical script, identical unresolved
finding, different terminal status, and the broken configuration scores better.

## 5. The judge interface

```bash
python -m ssf_hve ui                  # http://127.0.0.1:8765
```

Read-only, replay by default, bound to loopback and not configurable. It has **no gate-approval
control and no key-entry field** — both deliberate. Runs started from it land in a throwaway
session directory and never touch the published evaluation.

## 6. Human gates

Both gates need `SSF_HVE_GATE_SECRET` in the environment. **Never store it in the repository.**

```bash
export SSF_HVE_GATE_SECRET='<the owner secret>'

# H1 — approve one exact run
python -m ssf_hve gate-status --run <RUN_ID> --gate H1        # exit 4, with the reason
python -m ssf_hve approve --run <RUN_ID> --approver "Your Name"

# H2 — approve one exact package
python -m ssf_hve approve-submission --archive dist/<archive>.zip \
       --video <video>.mp4 --approver "Your Name" --show      # prints, approves nothing
```

`approve` requires an interactive terminal and the word `APPROVE` typed in full. Drop `--show`
to approve H2. If the secret is missing, approval refuses **before** prompting, so nobody types
`APPROVE` into something that cannot record it.

**Nothing here uploads, publishes or submits.** H2 records a decision; acting on it is manual.

## 7. Production and packaging

```bash
python -m ssf_hve render --run <RUN_ID>          # blocked with exit 4 until H1 is approved
python -m ssf_hve package --out dist/<name>.zip  # allowlist, then inspection, then write
```

`render` writes `samples/<RUN_ID>/` with narration timing, captions, citation frames, the
verbatim script and render instructions. If `ffmpeg` is present it also writes a **preview**
MP4 — a half-scale proof that the pipeline runs, labelled as such and not the production
render. If `ffmpeg` is missing the package is still complete.

`package` refuses to write if inspection finds a credential or a private filesystem path. A
refusal is a correct outcome, not a bug: read what it names.

## 8. After changing anything that can move a number

```bash
python -m ssf_hve bind-provenance     # re-freeze the binding manifest
python -m ssf_hve score               # regenerate the published tables
python -m pytest -q                   # the suite, including the documentation checks
```

Skipping the first makes `verify-provenance` fail — noisily, which is the intended direction.

## 9. Exit codes

| Code | Meaning | Usual cause |
|---|---|---|
| `0` | Success | — |
| `1` | Usage, configuration or IO error | Unknown case or configuration; a malformed run identifier; packaging refused |
| `2` | Terminated `HOLD` or `MALFORMED` | The bound was reached with findings open, or output failed its schema. **Expected on some cases.** |
| `3` | Replay incomplete — fixture missing | A prompt template changed, invalidating its fixtures |
| `4` | A human gate is not approved | H1 or H2 absent, unsigned, edited, expired, or no secret configured |

## 10. Failure modes and what to do

| Symptom | Cause | Action |
|---|---|---|
| `error: no fixture for this exact prompt` (exit 3) | A prompt template changed | Revert it, or recapture. Never regenerate the key. |
| `gold table: MISMATCH` | A frozen table was edited in place | Restore from git. Tables are never edited; new revisions get new dated files. |
| `verify-provenance` reports a MISMATCH | A bound input changed without re-binding | `bind-provenance` if the change was intended; investigate if not. |
| `H1: NOT APPROVED … no secret configured` | `SSF_HVE_GATE_SECRET` unset | Set it. Verification fails closed by design. |
| `H1: NOT APPROVED … signature does not verify` | The record was altered after signing, or signed with a different key | Do not "fix" the record. Re-approve. |
| `render` exits 4 | H1 not approved for this run | Approve it, or accept that production is blocked. That is the design. |
| `package` prints REFUSED | Inspection found a secret or a private path | Read the named file. Do not bypass. |
| Suite fails only in a working tree | Local scratch files | The scanner skips `.workspace/` and `dist/`; anything else is real. |
| `ffmpeg not found` | Not installed | Ignore, or install. Nothing depends on it. |

## 11. Environment variables

| Variable | Purpose | Notes |
|---|---|---|
| `SSF_HVE_GATE_SECRET` | Signs and verifies gate approvals | Never in the repository. Absent = not approved. |
| `SSF_HVE_API_KEY` | Live provider only | Only used with `--live`. Never logged or recorded. |
| `SSF_HVE_API_URL` | Non-default endpoint | Must be HTTPS **and** opted into |
| `SSF_HVE_ALLOW_CUSTOM_ENDPOINT` | Opt-in for the above | `1`, `true` or `yes`. Anything else refuses. |
| `SSF_HVE_RESULTS_DIR` | Redirect run, gate and trajectory output | Used by the tests and the UI session directory |

## 12. Backup and recovery

Everything is files in git, except three deliberate exclusions: `dist/` (built archives),
`.workspace/` (owner working notes) and any local `.venv`. The archive is rebuilt by one
command; the working notes are not part of the submission.

**Recovery from a bad change:** `git checkout -- <path>`, then `bind-provenance` and `score`.
Superseded gold tables and the pre-audit results are retained deliberately —
`results/archive/` and `evaluation/gold/` are history, not clutter, and nothing there should
be deleted to tidy up.
