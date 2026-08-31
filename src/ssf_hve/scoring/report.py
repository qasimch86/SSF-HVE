"""Judge-readable and machine-readable result tables."""
from __future__ import annotations

import json
import time
from pathlib import Path

from ssf_hve import CASE_SET_ID
from ssf_hve.config import ABLATION_ORDER, CONFIGS
from ssf_hve.paths import RESULTS_DIR
from ssf_hve.scoring.scorer import (SCORING_POLICY_VERSION, ConfigScore,
                                    aggregate, gold_table_sha256,
                                    latest_per_case, load_runs, score_run)


def score_all() -> dict[str, ConfigScore]:
    out: dict[str, ConfigScore] = {}
    for cfg_id in ABLATION_ORDER:
        runs = latest_per_case(load_runs(cfg_id))
        if not runs:
            continue
        scores = [score_run(runs[c]) for c in sorted(runs)]
        out[cfg_id] = aggregate(cfg_id, scores,
                                condition=CONFIGS[cfg_id].condition)
    return out


def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{x * 100:.0f}%"


def _num(x) -> str:
    return "n/a" if x is None else str(x)


def write_reports(scored: dict[str, ConfigScore]) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "ssf-hve/results/1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gold_table_sha256": gold_table_sha256(),
        "configs": {k: v.to_dict() for k, v in scored.items()},
    }
    # Byte-exact on every platform, deliberately. Text mode turns "\n" into
    # "\r\n" on Windows, so `score` rewrote its own committed output: the tree
    # went dirty, and an archive built afterwards no longer matched the git
    # tree, costing the H2 binding its commit attestation. Writing bytes makes
    # `score` idempotent everywhere, which is what the determinism claim in
    # REPRODUCTION.md actually means.
    jpath = RESULTS_DIR / "results.json"
    jpath.write_bytes(
        (json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))

    lines: list[str] = []
    a = lines.append
    a("# Results — SSF-HVE\n")
    a(f"Generated {payload['generated_utc']}. "
      f"Gold table `{payload['gold_table_sha256'][:16]}…`, case set `{CASE_SET_ID}`, "
      f"scoring policy v{SCORING_POLICY_VERSION}.\n")
    a(f"These numbers are re-derived under scoring policy v{SCORING_POLICY_VERSION} after "
      "independent audit; the same run records under the pre-audit policy are preserved at "
      "`results/archive/pre-audit-2026-08-29/`. See `PROVENANCE.md`.\n")
    a("Primary metric is **Unsafe Output Rate**: the share of evaluated outputs "
      "asserting at least one planted defect. **Clean-claim retention** is printed "
      "beside it, at the same size, because a verifier that refuses everything "
      "scores a perfect unsafe rate.\n")

    a("## Headline table\n")
    a("| Config | Unsafe output rate | Clean-claim retention | False-flag rate | "
      "Malformed | Errors | Model calls | Wall clock (s) |")
    a("|---|---|---|---|---|---|---|---|")
    for cid in ABLATION_ORDER:
        s = scored.get(cid)
        if not s:
            continue
        a(f"| `{cid}` | **{_pct(s.unsafe_output_rate)}** "
          f"({s.unsafe_count}/{s.n_cases}) | **{_pct(s.clean_claim_retention)}** "
          f"({s.clean_claims_retained}/{s.clean_claims_total}) | "
          f"{_pct(s.false_flag_rate)} ({s.false_flags}/{s.verifier_findings}) | "
          f"{s.malformed_runs} | {s.error_runs} | {s.model_calls_total} | "
          f"{s.wall_clock_s_total} |")
    a("")

    a("## Unsafe outcome by case\n")
    case_ids = sorted({c.case_id for s in scored.values() for c in s.cases})
    header = "| Case | Defect class | " + " | ".join(
        f"`{c}`" for c in ABLATION_ORDER if c in scored) + " |"
    a(header)
    a("|---|---|" + "---|" * len([c for c in ABLATION_ORDER if c in scored]))
    for case_id in case_ids:
        cls = ""
        cells = []
        for cid in ABLATION_ORDER:
            s = scored.get(cid)
            if not s:
                continue
            hit = next((c for c in s.cases if c.case_id == case_id), None)
            if hit is None:
                cells.append("—")
                continue
            cls = hit.defect_class
            mark = "UNSAFE" if hit.unsafe else "safe"
            if hit.terminal_status in ("MALFORMED", "ERROR"):
                mark = hit.terminal_status
            cells.append(f"{mark} ({hit.terminal_status})")
        a(f"| {case_id} | `{cls}` | " + " | ".join(cells) + " |")
    a("")

    a("## Terminal status and human gate\n")
    a("| Config | Terminal statuses | Detector HOLDs (human adjudication) | "
      "H1 gate state | Correction cycles used |")
    a("|---|---|---|---|---|")
    for cid in ABLATION_ORDER:
        s = scored.get(cid)
        if not s:
            continue
        a(f"| `{cid}` | {json.dumps(s.terminal_statuses)} | "
          f"{s.detector_holds_for_human} | "
          f"{json.dumps(s.h1_states)} | {s.correction_cycles_total} |")
    a("")
    if any(s.detector_holds_for_human for s in scored.values()):
        a("A detector HOLD is a case whose handling of the planted defect is "
          "semantically ambiguous. It is counted **unsafe** for qualification "
          "scoring and listed here for explicit human adjudication; it is "
          "never silently resolved in either direction.\n")

    a("## Missed defects by class\n")
    a("A planted defect that the output asserted **and** the verifier did not raise.\n")
    a("| Config | Missed by class |")
    a("|---|---|")
    for cid in ABLATION_ORDER:
        s = scored.get(cid)
        if not s:
            continue
        a(f"| `{cid}` | {json.dumps(s.missed_defects_by_class) if s.missed_defects_by_class else 'none'} |")
    a("")

    a("## Cost and resource use\n")
    a("Resource asymmetry between conditions is disclosed, not hidden: the advanced "
      "workflow makes more model calls than the baseline by construction.\n")
    a("| Config | Model calls | Input tokens | Output tokens | Est. cost (USD) | Wall clock (s) |")
    a("|---|---|---|---|---|---|")
    for cid in ABLATION_ORDER:
        s = scored.get(cid)
        if not s:
            continue
        a(f"| `{cid}` | {s.model_calls_total} | {_num(s.input_tokens_total)} | "
          f"{_num(s.output_tokens_total)} | {_num(s.estimated_cost_usd_total)} | "
          f"{s.wall_clock_s_total} |")
    a("")
    a("Every number above is derived from the run records in `results/runs/` by "
      "`python -m ssf_hve score`. No row is hand-entered.\n")

    mpath = RESULTS_DIR / "RESULTS.md"
    mpath.write_bytes("\n".join(lines).encode("utf-8"))
    return jpath, mpath
