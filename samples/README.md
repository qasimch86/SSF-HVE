# samples/ — the production package, and the gate in front of it

## Why this directory does not contain a video

Production is blocked until a person approves one exact script version. That is the design,
not a missing feature. `A4` will not run, `render` exits 2, and no MP4, caption file or
citation frame is produced until an H1 approval exists that is bound to the SHA-256 of the
script below.

There is no flag, environment variable, configuration value or API that can create that
approval. `gates.record_approval` refuses unless stdin is an interactive terminal and a
person types `APPROVE` in full, and `tests/test_gates.py::test_runner_cannot_reach_record_approval`
asserts structurally that the workflow has no code path to it.

## The H1 candidate

| | |
|---|---|
| Run | `C03-final-s1-7fd4522f` |
| Case | C03 — classroom air filtration and pupil absence |
| Configuration | `final` |
| Terminal status | `ACCEPT` after 1 correction cycle(s) |
| Model calls | 5 |
| Script SHA-256 | `a09b79f49b80ceeb92698c431899a42e1817bdb69144358ea873c5f3a5b29cd6` |
| H1 state | **BLOCKED_AWAITING_HUMAN** |

Pre-production artifacts, all of them outputs of A1/A2/A3 rather than A4:

- `H1_CANDIDATE_script.txt` — the exact verified script text an approval would bind to
- `H1_CANDIDATE_claim_map.json` — A1's claim map, with evidence level, quantities and scope
- `H1_CANDIDATE_findings.json` — every deterministic check result and verifier finding, per cycle

The full audit trail for this run, prompts and responses included:
`../trajectories/solution/C03-final-s1-7fd4522f.md`

## To approve and produce (a person, at a terminal)

```bash
python -m ssf_hve gate-status --run C03-final-s1-7fd4522f --gate H1        # exit 4 until approved
python -m ssf_hve approve     --run C03-final-s1-7fd4522f --gate H1 --approver "Your Name"
python -m ssf_hve render      --run C03-final-s1-7fd4522f
```

`render` then writes `samples/C03-final-s1-7fd4522f/` with narration timing, `captions.srt`, citation frames,
the verbatim script and render instructions — and, if `ffmpeg` is on the PATH, `demo.mp4`.
If ffmpeg is absent or fails, the package is still complete and nothing else is blocked.
