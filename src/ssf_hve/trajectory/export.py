"""Trajectory export: JSONL for machines, Markdown for a person.

Secrets are redacted. Failures are not: a trajectory that hides the cycle where
the verifier was wrong is not evidence of anything.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from ssf_hve.paths import (RUNS_DIR, TRAJ_SOLUTION_DIR, run_record_path,
                           trajectory_path, validate_run_id)

REDACTIONS = (
    (re.compile(r"(sk-[A-Za-z0-9_\-]{12,})"), "[REDACTED-API-KEY]"),
    # Header-style secrets are redacted to the end of the line: a key can
    # contain spaces, and "Bearer <token>" must not leave the token behind.
    (re.compile(r"(?i)(x-api-key\s*[:=]\s*).*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(authorization\s*[:=]\s*).*"), r"\1[REDACTED]"),
    (re.compile(r"(?i)\b(SSF_HVE_API_KEY\s*=\s*)\S+"), r"\1[REDACTED]"),
)


def redact(text: str) -> str:
    for pattern, repl in REDACTIONS:
        text = pattern.sub(repl, text)
    return text


def _load(run_id: str) -> dict:
    # `run_id` comes from the command line and is about to become a path.
    p = run_record_path(run_id)
    if not p.exists():
        raise SystemExit(f"no such run: {run_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def build_events(run: dict) -> list[dict]:
    """The canonical trajectory event stream, derived purely from a run record.

    Deterministic: the same run record always yields the same events, which is
    what lets an H1 approval bind a trajectory hash that a verifier can
    recompute later without trusting any exported file.
    """
    meta = run["meta"]

    events: list[dict] = [{
        "event": "run_start", "run_id": meta["run_id"], "case_id": meta["case_id"],
        "config_id": meta["config_id"], "condition": meta["condition"],
        "provider": meta["provider"], "model": meta["model"], "mode": meta["mode"],
        "started_utc": meta["started_utc"], "config": run["config"],
    }]
    for step in run["steps"]:
        events.append({
            "event": "agent_call", "index": step["index"], "role": step["role"],
            "kind": step["kind"], "prompt_sha256": step["prompt_sha256"],
            "rendered_instruction": redact(step["rendered_prompt"]),
            "response": redact(step["response_text"]),
            "response_provenance": step["provenance"],
            "parsed": step["parsed_summary"], "ok": step["ok"],
            "error": step["error"],
            "input_tokens": step["input_tokens"], "output_tokens": step["output_tokens"],
        })
    for cyc in run["cycles"]:
        events.append({
            "event": "correction_cycle", "index": cyc["index"],
            "deterministic_findings": cyc["deterministic_findings"],
            "verifier": cyc["verifier"], "blocking_count": cyc["blocking_count"],
            "action": cyc["action"],
        })
    events.append({"event": "human_gate", **run["h1_gate"]})
    events.append({
        "event": "run_end", "terminal_status": meta["terminal_status"],
        "correction_cycles": meta["correction_cycles"],
        "unresolved_findings": run["unresolved_findings"],
        "model_calls": meta["model_calls"], "input_tokens": meta["input_tokens"],
        "output_tokens": meta["output_tokens"],
        "estimated_cost_usd": meta["estimated_cost_usd"],
        "wall_clock_s": meta["wall_clock_s"], "finished_utc": meta["finished_utc"],
        "error": meta["error"],
    })
    return events


def jsonl_text(events: list[dict]) -> str:
    """The exact JSONL text `export-trajectory` writes for these events."""
    return "".join(json.dumps(e, ensure_ascii=False) + "\n" for e in events)


def trajectory_sha256(run: dict) -> str:
    """SHA-256 of the canonical trajectory JSONL derived from this run record."""
    import hashlib
    return hashlib.sha256(jsonl_text(build_events(run)).encode("utf-8")).hexdigest()


def markdown_text(run: dict, events: list[dict] | None = None) -> str:
    """The exact Markdown text `export-trajectory` writes for this run."""
    return _markdown(run, events if events is not None else build_events(run))


def trajectory_md_sha256(run: dict) -> str:
    """SHA-256 of the canonical trajectory Markdown derived from this run record."""
    import hashlib
    return hashlib.sha256(markdown_text(run).encode("utf-8")).hexdigest()


def export_run(run_id: str) -> list[Path]:
    run = _load(run_id)
    TRAJ_SOLUTION_DIR.mkdir(parents=True, exist_ok=True)
    events = build_events(run)

    # Byte-exact on every platform, deliberately. `write_text` goes through
    # text mode, which on Windows turns every "\n" into "\r\n" - so the file
    # on disk no longer matched the canonical text that `trajectory_sha256`
    # hashes, and gate H1 judged every freshly exported trajectory "divergent".
    # Writing bytes makes what lands on disk exactly what was hashed.
    jsonl = trajectory_path(run_id, ".jsonl")
    jsonl.write_bytes(jsonl_text(events).encode("utf-8"))

    md = trajectory_path(run_id, ".md")
    md.write_bytes(_markdown(run, events).encode("utf-8"))
    return [jsonl, md]


def _fence(text: str, limit: int = 4000) -> str:
    text = text or ""
    if len(text) > limit:
        text = text[:limit] + f"\n… [{len(text) - limit} more characters]"
    return "```\n" + text + "\n```"


def _markdown(run: dict, events: list[dict]) -> str:
    meta = run["meta"]
    L: list[str] = []
    a = L.append
    a(f"# Trajectory — {meta['run_id']}\n")
    a(f"- **Case:** {meta['case_id']}")
    a(f"- **Configuration:** `{meta['config_id']}` ({meta['condition']})")
    a(f"- **Provider / model:** {meta['provider']} / {meta['model']} (mode: {meta['mode']})")
    a(f"- **Started / finished (UTC):** {meta['started_utc']} → {meta['finished_utc']}")
    a(f"- **Model calls:** {meta['model_calls']}  •  **Wall clock:** {meta['wall_clock_s']} s")
    a(f"- **Terminal status:** **{meta['terminal_status']}**")
    if meta.get("error"):
        a(f"- **Error:** `{meta['error']}`")
    a("")
    a("## Configuration\n")
    a(_fence(json.dumps(run["config"], indent=2)))
    a("")
    for step in run["steps"]:
        a(f"## Step {step['index']} — role `{step['role']}` ({step['kind']})\n")
        a(f"Prompt SHA-256 `{step['prompt_sha256']}` • response provenance "
          f"`{step['provenance']}`\n")
        a("<details><summary>Rendered instruction</summary>\n")
        a(_fence(redact(step["rendered_prompt"])))
        a("\n</details>\n")
        a("**Structured output**\n")
        a(_fence(redact(step["response_text"])))
        a(f"\nParsed: `{json.dumps(step['parsed_summary'])}`\n")
    for cyc in run["cycles"]:
        a(f"## Cycle {cyc['index']}\n")
        det = cyc["deterministic_findings"]
        a(f"**Deterministic checks:** {len(det)} finding(s)\n")
        for d in det:
            a(f"- `{d['check']}` **{d['severity']}** — {d['observation']}")
            a(f"  - recommended: {d['recommended_correction']}")
        v = cyc["verifier"]
        if v:
            a(f"\n**Verifier recommendation:** `{v['recommendation']}` — {v['rationale']}\n")
            for f in v["findings"]:
                a(f"- `{f['id']}` **{f['severity']}** claim `{f.get('claim_ref','')}` — "
                  f"{f.get('observation') or f.get('explanation','')}")
                a(f"  - quoted: “{f.get('quoted_span','')[:160]}”")
                a(f"  - recommended: {f.get('recommended_correction','')}")
        a(f"\n**Control action taken by the runner:** `{cyc['action']}`\n")
        a("> The verifier recommends. The runner decides what happens next, from a "
          "fixed set of actions. Neither can approve.\n")
    g = run["h1_gate"]
    a("## Human gate H1\n")
    a(f"- State: **{g.get('state')}**")
    a(f"- Artifact SHA-256: `{g.get('artifact_sha256','n/a')}`")
    a(f"- Approver: {g.get('approver') or '—'}")
    a(f"- {g.get('note','')}\n")
    if run["unresolved_findings"]:
        a("## Unresolved findings at the correction bound\n")
        a("These were **not** fixed. The run terminated without them being resolved, "
          "which is why its status is not ACCEPT.\n")
        a(_fence(json.dumps(run["unresolved_findings"], indent=2)))
    a("## Final script\n")
    a(_fence(run.get("final_narration") or "(no script produced)"))
    return "\n".join(L)
