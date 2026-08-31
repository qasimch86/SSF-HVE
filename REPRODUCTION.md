# REPRODUCTION.md

Written for someone starting from a clean machine with nothing installed but Python and git.
The full evaluation runs offline, with **no API key and no provider cost**, in well under a
minute.

---

## 1. Requirements

| | |
|---|---|
| Python | **3.10 or newer** (developed and measured on CPython 3.10.12, Linux x86-64) |
| git | any recent version |
| Runtime dependencies | **none** — standard library only, by design |
| Test dependency | `pytest==8.2.2` |
| Optional | `ffmpeg` (only for the optional MP4 in `render`; everything else works without it) |
| Network | **not required** for the evaluation, scoring, verification or gate steps below, and the no-install path (§2) uses no network at all. `pip install` may use it twice: fetching pytest (`.[dev]`), and — because the build backend is PEP 517 with `setuptools>=68` — pip's build isolation may fetch setuptools even for a plain `pip install -e .` on an uncached machine. `pip install -e . --no-build-isolation` avoids that when setuptools is already present. `--live` mode also uses the network, by definition |
| API key | **not required** for any step below |

A zero-dependency runtime is a deliberate choice: the reproduction path must not be able to
fail because a package index moved.

## 2. Setup

```bash
git clone <this repository> ssf-hve
cd ssf-hve

python3 -m venv .venv
. .venv/bin/activate                 # Windows PowerShell: .venv\Scripts\Activate.ps1

pip install -e .                     # installs the package; no third-party deps
pip install -e ".[dev]"              # adds pytest, only needed for section 7
```

(On an offline machine: skip pip entirely and use the no-install path below —
pip's PEP 517 build isolation may try to fetch `setuptools>=68` even though the
package itself has no dependencies; `--no-build-isolation` works when
setuptools is already installed.)

If you would rather not install anything at all:

```bash
export PYTHONPATH=src                # Windows PowerShell: $env:PYTHONPATH="src"
python -m ssf_hve --version
```

## 3. Check the frozen scoring table before you trust any number

```bash
python -m ssf_hve verify-gold
```

Expected — the recorded and recomputed digests match:

```
gold table: evaluation/gold/gold_table_2026-08-30_v5-stance.json
recorded : 5ee8d2c945a8e323cb7a43b2b1d6cbe81777557d9026a8dedb07a0f569587f99
computed : 5ee8d2c945a8e323cb7a43b2b1d6cbe81777557d9026a8dedb07a0f569587f99
MATCH
```

Then check that every scoring input — active cases, gold table, prompts, scorer
source, the full fixture and run-record inventories, and `results.json` itself —
matches the self-hashed provenance binding:

```bash
python -m ssf_hve verify-provenance
```

Expected: section 0 reports every bound file matching, and the final line reads
`RESULT: all checked relationships hold.` with exit code 0. Any edit to any bound
file makes this command fail naming the file — try it on a scratch copy.

```bash
python -m ssf_hve fixtures
```

Expected — 122 fixtures, every key verified against the prompt stored inside it, and every
one declaring `blinded-agent-capture`. **No fixture claims to be a live API capture**,
because none is:

```
122 fixture(s) in fixtures/replay
  blinded-agent-capture      122

all fixture keys verified against their stored prompts
```

## 4. The main result

Run the baseline and every configuration, then score:

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

`evaluate` and `run` return a **non-zero exit code** when any case ends `HOLD`, `MALFORMED`
or `ERROR` (see §6). That is intended behaviour, not a failure of the run — do not wrap these
commands in `set -e` and expect them to continue.

Expected output of `score` (this is the published table; it should match to the decimal).
These are **scoring policy v3** numbers against gold table
`evaluation/gold/gold_table_2026-08-30_v5-stance.json`. The same run records under
policy v2 / gold v4 (identical figures) are archived at
`results/archive/v4-postaudit-2026-08-30/`, and under the pre-audit policy v1 at
`results/archive/pre-audit-2026-08-29/`:

```
baseline         UOR=0.00 (0/30)  clean-claim retention=0.81  malformed=0 errors=0
iter-1           UOR=0.10 (1/10)  clean-claim retention=0.71  malformed=0 errors=0
iter-2           UOR=0.00 (0/10)  clean-claim retention=0.96  malformed=0 errors=0
iter-3           UOR=0.20 (2/10)  clean-claim retention=0.75  malformed=2 errors=0
iter-4           UOR=0.20 (2/10)  clean-claim retention=0.86  malformed=1 errors=0
rm-bound-ok      UOR=0.10 (1/10)  clean-claim retention=0.86  malformed=1 errors=0
rm-model-checks  UOR=0.60 (6/10)  clean-claim retention=0.36  malformed=6 errors=0
final            UOR=0.20 (2/10)  clean-claim retention=0.86  malformed=1 errors=0
```

`score` writes `results/RESULTS.md` (judge-readable) and `results/results.json`
(machine-readable). Every number in both is derived from the run records in `results/runs/`;
none is hand-entered.

**Approximate runtime:** the whole block above completes in **under 30 seconds** on a laptop.
**Cost: $0.00** — replay reads recorded responses from disk and opens no network connection.
That is enforced, not asserted: exactly one module in the package imports a network library
(`providers/live.py`, reached only through `--live`), and `tests/test_offline.py` walks every
other module's AST to keep it so. The two things that *do* use a network are `--live` itself
and installing pytest once during setup; neither is needed to reproduce any published number.

### Determinism

```bash
python -m ssf_hve score && cp results/results.json /tmp/a.json
python -m ssf_hve score && diff <(jq 'del(.generated_utc)' /tmp/a.json) \
                                <(jq 'del(.generated_utc)' results/results.json)
```

Expected: no differences. (`tests/test_scoring.py::test_published_results_are_derived_and_deterministic`
asserts the same thing without needing `jq`.)

## 5. Single cases and trajectories

```bash
python -m ssf_hve baseline --case C01 --replay                   # the comparator
python -m ssf_hve run --case C10 --config final --replay         # fails closed, MALFORMED
python -m ssf_hve run --case C09 --config final --replay         # HOLD at the bound
python -m ssf_hve run --case C09 --config rm-bound-ok --replay   # same content, ACCEPT
                                                                 # (deliberately unsafe control)

python -m ssf_hve export-trajectory --run <RUN_ID>               # JSONL + Markdown
```

`<RUN_ID>` is printed by every `run` / `baseline` / `evaluate` line. Exported trajectories
land in `trajectories/solution/`. Eight representative ones are already committed, including
the fail-closed run and the `HOLD` / `ACCEPT` pair.

## 5a. The judge UI (optional; same evidence, no CLI)

```bash
python -m ssf_hve ui                 # serves http://127.0.0.1:8765/
python -m ssf_hve ui --port 9000     # a different port
```

The UI is standard-library WSGI bound to 127.0.0.1 — nothing to install, no
database, no login. It runs cases in replay by default (no key), shows the
scored verdict (SAFE / UNSAFE / HOLD), claim map, script, deterministic and
verifier findings per cycle, workflow steps, trajectory, H1/H2 state, the
corrected score table, the baseline/removal comparisons and the provenance
verification result. Runs started in the UI are written to a throwaway session
directory printed at startup — never into `results/runs/`. Rendering from the
UI enforces the same H1 gate as the CLI and shows the refusal; approving H1 or
H2 from the browser is impossible by design. Live mode requires starting with
`--allow-live` AND `SSF_HVE_API_KEY` in the environment; the browser never
sees or accepts a key.

## 6. Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | usage, configuration or IO error |
| `2` | the workflow terminated `HOLD` / `MALFORMED`, or unresolved findings remain |
| `3` | replay incomplete — no fixture for this exact prompt (fails closed; nothing invented) |
| `4` | a human gate is not approved |

Verify code 3 yourself — ask for a model nobody captured:

```bash
python -m ssf_hve run --case C01 --config final --replay --model no-such-model
echo $?        # 3
```

## 7. Tests

```bash
python -m pytest tests -q
```

Expected: **all tests pass** — the current total is printed by the suite itself and
pinned against the documents by `tests/test_documented_counts.py` (README states the
number). Runtime: under a minute installed; a few minutes when run straight from
`src/` via PYTHONPATH (the CLI and repository-copy subprocess tests dominate).
Coverage includes schema validation, malformed-output fail-closed behaviour, quantity and
unit checking, limitation checking, reference integrity, prompt-injection handling, the
correction-cycle bound, human-gate enforcement, replay hash invalidation, fixture provenance,
CLI exit codes, scoring denominators, trajectory redaction, and a repository-wide secret scan.

Tests write their run records to a temporary directory (`SSF_HVE_RESULTS_DIR`), so running
the suite can never alter a published result.

## 8. Human gates

Two gates, both human-only, both tamper-evident.

**H1 — one exact script version.** Production is blocked until a person approves it. There is
no flag, environment variable or API that can approve on their behalf:

```bash
export SSF_HVE_GATE_SECRET='<the owner's secret>'          # never stored in the repository
python -m ssf_hve gate-status --run <RUN_ID>               # exit 4, NOT APPROVED, with the reason
python -m ssf_hve approve --run <RUN_ID> --approver "Your Name"   # optional: --valid-days N
```

`approve` refuses unless stdin is an interactive terminal, and then requires the word
`APPROVE` typed in full. The approval binds the exact run: the narration hash, the
byte-exact run record, the canonical trajectory (JSONL and Markdown) derived from it,
the candidate script, the configuration snapshot, and the run/case/config/sample
identifiers — all recomputed from disk at every check — **and the exported trajectory
files themselves**: an export that exists must be byte-identical to the canonical
text, an export verified at approval must not vanish, and nothing can be approved
over a divergent export. Change one character of any of them and it no longer applies;
copy the record beside another run — even one with identical narration — and it is
refused; and it expires (default 30 days, chosen and signed at approval time). H2 is
approved only through `approve-submission`; no other route exists.

**Approvals are signed.** Each gate record carries an HMAC-SHA-256 signature over its own
canonical content, keyed by `SSF_HVE_GATE_SECRET`. Verification uses a constant-time
comparison and **fails closed**: an unsigned record, an edited record, a record signed with a
different secret, and the case where no secret is set are all treated as *not approved*.
There is no flag to disable the check.

Without this, the interactive prompt was theatre — any process that could write into
`results/gates/` could mint an approval, including the agent the gate exists to constrain.
`tests/test_gate_signatures.py` writes each of those forgeries and asserts the gate refuses
it. The secret lives only in the owner's environment: it is never written to disk, never
logged, never placed in a run record, trajectory or archive, and never in a test (tests
generate their own throwaway values).

**H2 — one exact submission package.** A zip can be rebuilt between the moment a person
reads it and the moment it is uploaded, so H2 does not approve "a submission"; it approves a
binding statement naming the archive filename, byte size and SHA-256, the manifest digest
(a content hash stable across rebuilds), the video's SHA-256 when one is submitted, and
**verified** commit evidence: the commit id appears only under set equality — the
archive's entries are exactly that commit's submission set (nothing missing, nothing
extra, nothing renamed) and every entry is byte-identical; otherwise the statement
says "not established" and names the gap,
and the checkout that ran the check is listed separately under its own honest label:

```bash
python -m ssf_hve approve-submission --archive dist/ssf-hve-submission.zip \
    --video ssf-hve-solution-video.mp4 --approver "Your Name" --show   # prints, approves nothing
python -m ssf_hve gate-status --gate H2 --archive dist/ssf-hve-submission.zip
```

Drop `--show` to approve interactively. Change any component and the statement hash changes,
so the approval no longer applies. **Nothing in this repository uploads, publishes or submits
anything**, H2 included; the gate records a decision, it does not act on it.

## 9. Production and rendering

```bash
python -m ssf_hve render --run <RUN_ID>
```

Without an H1 approval this prints the gate refusal and exits 2 — the designed behaviour.
With approval it writes `samples/<RUN_ID>/` containing narration timing, `captions.srt`,
citation frames, the verbatim script and render instructions. If `ffmpeg` is on the PATH it
also produces `demo.mp4`; **if ffmpeg is missing or fails, the package is still complete and
nothing else is blocked.**

## 10. Live mode (optional, costs money, not needed to reproduce anything)

```bash
export SSF_HVE_API_KEY=...            # never committed, never logged, never in a trajectory
python -m ssf_hve run --case C01 --config final --live --model <model-id>
```

Live mode records what it receives as a new fixture with provenance `live-api`. Approximate
cost of one advanced case at 2026 frontier-model pricing: a few US cents; the full eight-
configuration sweep would be a few dollars. **We did not run live mode for the published
results** — see `EVAL_PROTOCOL.md` §6.1 for what was done instead and why it is labelled the
way it is.

## 11. Clean-room procedure

What we ran before submission, and what a judge can repeat:

```bash
git clone <archive or repository> /tmp/cleanroom && cd /tmp/cleanroom
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
unset SSF_HVE_API_KEY
python -m ssf_hve verify-gold             # 1. verify the SHIPPED state first…
python -m ssf_hve verify-provenance       #    …including the full binding
python -m ssf_hve fixtures
python -m pytest tests -q                 # 2. the suite, against the shipped state
rm -rf results/runs                       # 3. now discard our run records…
python -m ssf_hve evaluate --all --config baseline --samples 3 --replay
for c in iter-1 iter-2 iter-3 iter-4 rm-bound-ok rm-model-checks final; do
  python -m ssf_hve evaluate --all --config $c --replay
done
python -m ssf_hve score                   # 4. …and regenerate them from fixtures
```

The `score` output must match §4 exactly. **Order matters for one honest
reason:** `verify-provenance` binds the *shipped* run-record inventory, so run it
(and the suite) before step 3. After you regenerate, your fresh run records have
new identifiers, and `verify-provenance` will — correctly — report that
`results/runs/` no longer matches the shipped binding: you replaced the shipped
evidence with your own reproduction. At that point the reproduction claim is the
`score` identity, not the binding.

## 12. Known platform notes

- **Windows:** activate with `.venv\Scripts\activate`; use `$env:PYTHONPATH="src"` instead of
  `export`. Line endings are normalised by `.gitattributes`, and fixture keys hash the prompt
  text after newline normalisation, so a CRLF checkout does not change any hash.
- **Python 3.9 and earlier** are not supported (PEP 604 `X | Y` annotations).
- `jq` in §4 is a convenience only; the equivalent assertion is in the test suite.
- Long paths on Windows: fixture filenames are 64-character hashes; enable long-path support
  if you clone into a deeply nested directory.

---

## 13. Clean-room result, performed before submission

Re-run after the post-re-verification remediation, from a fresh extraction of the
candidate archive into an empty directory (`/tmp`), CPython 3.10, no API key, no
network for any verification or replay step:

```
389 files extracted
verify-gold                  MATCH
verify-provenance            RESULT: all checked relationships hold (binding included)
fixtures                     122 fixtures, all keys verified, all blinded-agent-capture
gate-status (shipped run)    exit 4, NOT APPROVED, with the reason
render before H1             exit 2, actual refusal, no production output
missing fixture              exit 3, fails closed
--live with no key           exit 1, refused before any network call
evaluate (8 configurations)  100 fresh run records regenerated, ~2 s total, $0
score                        identical to section 4, to the decimal
pytest                       284 collected; 6 archive-only skips (the H2
                             commit-evidence tests need git history and say so);
                             278 of them run and pass from the archive, and the
                             full 284 pass from a git clone / the repository
shipped trajectories         every solution .jsonl byte-matches a canonical
                             rebuild from its own run record
```

(Earlier editions of this section reported the pre-audit archive's figures; those
are preserved in git history rather than restated beside a different archive.)
