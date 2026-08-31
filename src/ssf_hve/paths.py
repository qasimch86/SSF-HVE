"""Repository paths. Resolved from this file so the CLI works from any cwd."""
from __future__ import annotations

import os
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parent
SRC_DIR = PKG_DIR.parent
ROOT = SRC_DIR.parent

PROMPTS_DIR = ROOT / "prompts"
CASES_DIR = ROOT / "evaluation" / "cases"
GOLD_DIR = ROOT / "evaluation" / "gold"
FIXTURES_DIR = ROOT / "fixtures" / "replay"
# Tests and sandboxed runs redirect results with SSF_HVE_RESULTS_DIR so that a
# test can never write a run record into the published evaluation.
RESULTS_DIR = Path(os.environ.get("SSF_HVE_RESULTS_DIR") or (ROOT / "results"))
RUNS_DIR = RESULTS_DIR / "runs"
# Redirected with the rest of the results, so that a test process can never
# write a gate approval into the published tree. Before this, GATES_DIR was
# pinned to the repository and a failing test could leave an approval behind.
GATES_DIR = RESULTS_DIR / "gates"
# Exported trajectories follow the results redirection for the same reason the
# gates do: a test or UI session must never write into the published, tracked
# trajectories/solution/. When no redirection is active, exports land beside
# the published evidence as before.
TRAJ_SOLUTION_DIR = (RESULTS_DIR / "trajectories" / "solution"
                     if os.environ.get("SSF_HVE_RESULTS_DIR")
                     else ROOT / "trajectories" / "solution")
SAMPLES_DIR = ROOT / "samples"

GOLD_TABLE_V1 = GOLD_DIR / "gold_table_2026-08-29.json"
GOLD_TABLE_V2 = GOLD_DIR / "gold_table_2026-08-29_v2.json"
GOLD_TABLE_V3 = GOLD_DIR / "gold_table_2026-08-29_v3.json"
GOLD_TABLE_V31 = GOLD_DIR / "gold_table_2026-08-29_v3.1.json"
GOLD_TABLE_V32 = GOLD_DIR / "gold_table_2026-08-29_v3.2.json"
GOLD_TABLE_V4 = GOLD_DIR / "gold_table_2026-08-30_v4-postaudit.json"
# Active table. Retrospective, created after the runs it scores; see its own
# provenance_statement and EVAL_PROTOCOL.md section 9. Not a preregistration.
GOLD_TABLE = GOLD_DIR / "gold_table_2026-08-30_v5-stance.json"


def ensure_dirs() -> None:
    for d in (RESULTS_DIR, RUNS_DIR, GATES_DIR, TRAJ_SOLUTION_DIR, FIXTURES_DIR):
        d.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------- run identifiers

import re as _re                                                   # noqa: E402

# A run identifier reaches the filesystem twice: it selects a run record to
# read, and it names the trajectory files that get written. Both are joined
# straight onto a directory, so an identifier containing a path separator or a
# parent reference would read or write outside the results tree. It is accepted
# from the command line, so it is untrusted input and is validated as such.
#
# Shape: <case>-<config>-s<sample>-<8 hex>, e.g. C09-rm-bound-ok-s1-d65046b4.
RUN_ID_RE = _re.compile(r"^C\d{2}-[a-z0-9]+(?:-[a-z0-9]+)*-s\d{1,3}-[0-9a-f]{8}$")


class InvalidRunId(ValueError):
    """Raised for a run identifier that could leave the results directory."""


def validate_run_id(run_id: str) -> str:
    """Return `run_id` unchanged, or raise. Never returns a sanitised value.

    Silently repairing a malformed identifier would hide the attempt; the
    caller is told no instead.
    """
    if not isinstance(run_id, str) or not RUN_ID_RE.match(run_id):
        raise InvalidRunId(
            f"not a run identifier: {run_id!r}. Expected the form "
            "C09-final-s1-2ba6b49f. Identifiers are used to build file paths, "
            "so anything else is refused rather than sanitised.")
    return run_id


def run_record_path(run_id: str) -> Path:
    """The one place a run identifier becomes a path to read."""
    p = (RUNS_DIR / f"{validate_run_id(run_id)}.json").resolve()
    if RUNS_DIR.resolve() not in p.parents:
        raise InvalidRunId(f"{run_id!r} resolves outside the runs directory")
    return p


def trajectory_path(run_id: str, suffix: str) -> Path:
    """The one place a run identifier becomes a path to write."""
    if suffix not in (".jsonl", ".md"):
        raise InvalidRunId(f"unsupported trajectory suffix {suffix!r}")
    p = (TRAJ_SOLUTION_DIR / f"{validate_run_id(run_id)}{suffix}").resolve()
    if TRAJ_SOLUTION_DIR.resolve() not in p.parents:
        raise InvalidRunId(f"{run_id!r} resolves outside the trajectory directory")
    return p
