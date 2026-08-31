# Coding-agent record

The challenge requires representative trajectories **for every agent used**, and separately
requires that coding-agent use be disclosed. This directory covers the agents that *built*
the edition. `../solution/` covers the agents that *run inside* it.

## What this is, and what it is not

`WORK_LOG.md` in this directory is a **reconstructed work log**. It is assembled from the
git history of this repository, the run records under `results/`, the fixture store, and the
commands actually executed during the build.

**It is not a native transcript export.** The development environment used here does not
expose one, so none is claimed. Every timestamp in it is taken from a git commit, a file
mtime or a run record — none is invented — but the log is a reconstruction and is labelled
as one throughout.

## Tools disclosed

| Tool | Role in this build |
|---|---|
| Claude (Claude Agent SDK / Cowork), model configured as `claude-opus-5` | The coding agent. Wrote the implementation, designed the evaluation, authored the ten cases, ran the sweeps, drafted the documents. Worked under human direction with the scope frozen in `SCOPE_FREEZE.md`. |
| Claude, in isolated sub-sessions | The **subject under evaluation**. Each session received only one rendered prompt — no gold table, no defect list, no knowledge that an evaluation was running — and its response was stored as a fixture with provenance `blinded-agent-capture`. |
| `git`, CPython 3.10.12, `pytest` 8.2.2, `ffmpeg` 4.4.2 | Standard tooling. |

The same model family appears on both sides of this evaluation. That is a real limitation of
the measurement, not a detail, and it is stated in `README.md` (limitation 5),
`EVAL_PROTOCOL.md` §6.1, and here.

## Human direction and human decisions

The owner set the scope and the constraints, and holds both gates. No gate in this system can
be opened by an agent — `record_approval` refuses unless a person types `APPROVE` at an
interactive terminal, and `tests/test_gates.py` asserts structurally that the runner has no
code path to it.

## Where to look

| Question | File |
|---|---|
| What happened, when, and what came out of it | `WORK_LOG.md` |
| What the solution agents did on a real case | `../solution/*.md` |
| What every instruction said | `../../prompts/` |
| What the numbers were | `../../results/RESULTS.md` |
