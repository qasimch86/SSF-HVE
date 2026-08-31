"""The judge UI as one WSGI application. Standard library only.

Every route reads through the existing domain services and renders their
output; no scoring, gating, provenance or workflow logic is duplicated here,
and nothing here can approve a gate, publish, upload or submit.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ssf_hve import CASE_SET_ID, gates
from ssf_hve.cases import all_case_ids, load_case
from ssf_hve.config import ABLATION_ORDER, CONFIGS
from ssf_hve.paths import ROOT, RUNS_DIR, SAMPLES_DIR, InvalidRunId, validate_run_id
from ssf_hve.scoring.scorer import SCORING_POLICY_VERSION, score_run
from ssf_hve.ui import views
from ssf_hve.ui.views import esc, kv_table, layout, pre, pre_json, verdict_badge

PUBLISHED_RUNS = ROOT / "results" / "runs"
MAX_FORM_BYTES = 64 * 1024
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$")
_SAFE_ARCHIVE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.zip$")


@dataclass
class Job:
    job_id: str
    case_id: str
    config_id: str
    mode: str
    status: str = "queued"            # queued | running | done | failed
    run_id: str = ""
    error: str = ""
    thread: threading.Thread | None = None


@dataclass
class UIState:
    allow_live: bool = False
    background: bool = True
    csrf_token: str = field(default_factory=lambda: secrets.token_hex(32))
    jobs: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


class Response:
    def __init__(self, body: str | bytes, status: str = "200 OK",
                 content_type: str = "text/html; charset=utf-8",
                 headers: list | None = None):
        self.body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers = [("Content-Type", content_type),
                        ("Content-Length", str(len(self.body))),
                        ("X-Content-Type-Options", "nosniff"),
                        ("X-Frame-Options", "DENY"),
                        ("Referrer-Policy", "no-referrer"),
                        ("Content-Security-Policy",
                         "default-src 'none'; style-src 'unsafe-inline'; "
                         "img-src 'self'; form-action 'self'")]
        if headers:
            self.headers.extend(headers)


def redirect(location: str) -> Response:
    return Response("", status="303 See Other", headers=[("Location", location)])


def _page(title: str, body: str, status: str = "200 OK", refresh=None) -> Response:
    return Response(layout(title, body, refresh=refresh), status=status)


def _error_page(status: str, message: str) -> Response:
    return _page("Refused", f'<section class="card"><div class="error">'
                            f"{esc(message)}</div></section>", status=status)


# ------------------------------------------------------------------ run access

def _run_path(run_id: str) -> Path | None:
    """Session runs first, then the published evidence. Read-only."""
    rid = validate_run_id(run_id)
    for base in (RUNS_DIR, PUBLISHED_RUNS):
        p = (base / f"{rid}.json").resolve()
        if base.resolve() in p.parents and p.exists():
            return p
    return None


def _load_run(run_id: str) -> dict | None:
    p = _run_path(run_id)
    return json.loads(p.read_text(encoding="utf-8")) if p else None


def _list_runs() -> list[dict]:
    rows, seen = [], set()
    for origin, base in (("session", RUNS_DIR), ("published", PUBLISHED_RUNS)):
        if not base.exists() or base.resolve() in seen:
            continue
        seen.add(base.resolve())
        for p in sorted(base.glob("*.json")):
            try:
                run = json.loads(p.read_text(encoding="utf-8"))
                rows.append({"origin": origin, "run": run})
            except (OSError, ValueError):
                continue
    rows.sort(key=lambda r: (r["run"]["meta"].get("started_utc", ""),
                             r["run"]["meta"].get("run_id", "")), reverse=True)
    return rows


def _run_verdict(run: dict):
    try:
        return score_run(run, load_case(run["meta"]["case_id"]))
    except Exception:                                            # noqa: BLE001
        return None


def _badge_for(cs) -> str:
    if cs is None:
        return '<span class="badge neutral">UNSCORED</span>'
    if cs.hold_for_human:
        return verdict_badge("hold")
    return verdict_badge("unsafe" if cs.unsafe else "safe")


# ------------------------------------------------------------------ handlers

def home(state: UIState) -> Response:
    case_opts = []
    for cid in all_case_ids():
        case = load_case(cid)
        case_opts.append(f'<option value="{esc(cid)}">{esc(cid)} — '
                         f"{esc(case.title[:70])}</option>")
    cfg_opts = "".join(
        f'<option value="{esc(cid)}"{" selected" if cid == "final" else ""}>'
        f"{esc(cid)} — {esc(CONFIGS[cid].label[:80])}</option>"
        for cid in ABLATION_ORDER)
    live_note = ("" if state.allow_live else
                 '<p class="note">Disabled: start the server with '
                 "<code>--allow-live</code> AND set <code>SSF_HVE_API_KEY</code> "
                 "to use live mode. Replay needs neither.</p>")
    live_radio = (f'<label><input type="radio" name="mode" value="live"'
                  f'{"" if state.allow_live else " disabled"}> live '
                  f"(calls the provider API; costs money)</label>{live_note}")
    body = f"""
<h1>Run the workflow</h1>
<section class="card">
<p>Pick one synthetic case and one configuration, then run it. <b>Replay is the
default and needs no API key</b>: every model response is served from the recorded,
hash-verified fixtures, so what you see is exactly the published evidence.
Runs started here are written to this session's scratch directory and never
touch the published results.</p>
<form class="run" method="post" action="/run">
<input type="hidden" name="csrf" value="{esc(state.csrf_token)}">
<label for="case">Synthetic case (C01–C10)</label>
<select id="case" name="case">{''.join(case_opts)}</select>
<label for="config">Configuration</label>
<select id="config" name="config">{cfg_opts}</select>
<fieldset><legend>Mode</legend>
<label><input type="radio" name="mode" value="replay" checked> replay / demo
(default — recorded fixtures, offline, no key)</label>
{live_radio}
</fieldset>
<button class="primary" type="submit">Run</button>
</form>
</section>
<section class="card"><h2>What this produces</h2>
<p class="note">The workflow's output is a <b>verified script</b> with its claim
map, findings, review cycles and trajectory, plus — only after a person approves
gate H1 at a terminal — a production/render package (timing, captions, citation
frames, render instructions). It does not produce a finished, polished video, and
this interface will not pretend otherwise.</p></section>"""
    return _page("Run", body)


def run_post(state: UIState, form: dict) -> Response:
    case_id = (form.get("case") or [""])[0]
    config_id = (form.get("config") or [""])[0]
    mode = (form.get("mode") or ["replay"])[0]
    if case_id not in all_case_ids():
        return _error_page("400 Bad Request", f"unknown case {case_id!r}")
    if config_id not in CONFIGS:
        return _error_page("400 Bad Request", f"unknown configuration {config_id!r}")
    if mode not in ("replay", "live"):
        return _error_page("400 Bad Request", f"unknown mode {mode!r}")
    if mode == "live" and not state.allow_live:
        return _error_page(
            "403 Forbidden",
            "Live mode is disabled. It requires starting the server with "
            "--allow-live and providing SSF_HVE_API_KEY in the environment; "
            "there is no way to enable it, or to enter a key, from the browser.")
    job = Job(job_id=uuid.uuid4().hex[:12], case_id=case_id,
              config_id=config_id, mode=mode)
    with state.lock:
        state.jobs[job.job_id] = job
    if state.background:
        job.thread = threading.Thread(target=_execute_job, args=(job,), daemon=True)
        job.thread.start()
        return redirect(f"/jobs/{job.job_id}")
    _execute_job(job)
    if job.status == "done":
        return redirect(f"/runs/{job.run_id}")
    return redirect(f"/jobs/{job.job_id}")


def _execute_job(job: Job) -> None:
    from ssf_hve.providers import DEFAULT_MODEL, get_provider
    from ssf_hve.runner import execute
    job.status = "running"
    try:
        provider = get_provider(live=(job.mode == "live"), model=DEFAULT_MODEL)
        case = load_case(job.case_id)
        rec = execute(case, CONFIGS[job.config_id], provider, mode=job.mode)
        job.run_id = rec.meta.run_id
        job.status = "done"
    except Exception as exc:                                     # noqa: BLE001
        job.status = "failed"
        job.error = f"{type(exc).__name__}: {exc}"


def job_page(state: UIState, job_id: str) -> Response:
    job = state.jobs.get(job_id)
    if job is None:
        return _error_page("404 Not Found", "no such job")
    rows = [("Case", esc(job.case_id)), ("Configuration", esc(job.config_id)),
            ("Mode", esc(job.mode)), ("Status", esc(job.status))]
    if job.status == "done":
        body = (f"<h1>Run complete</h1><section class='card'>{kv_table(rows)}"
                f'<p><a href="/runs/{esc(job.run_id)}">Open the result: '
                f"{esc(job.run_id)}</a></p></section>")
        return _page("Run complete", body,
                     refresh=None if not state.background else 1)
    if job.status == "failed":
        body = (f"<h1>Run failed</h1><section class='card'>{kv_table(rows)}"
                f'<div class="error">{esc(job.error)}</div>'
                "<p class='note'>A missing replay fixture or an unavailable live "
                "provider fails closed — nothing is invented.</p></section>")
        return _page("Run failed", body)
    body = (f"<h1>Running…</h1><section class='card'>{kv_table(rows)}"
            "<p class='note'>The page refreshes each second. Replay runs finish "
            "in well under a second; live runs take as long as the provider "
            "does.</p></section>")
    return _page("Running", body, refresh=1)


def runs_page(state: UIState) -> Response:
    rows = []
    for entry in _list_runs():
        run = entry["run"]
        meta = run["meta"]
        cs = _run_verdict(run)
        rows.append(
            f"<tr><td><a href='/runs/{esc(meta['run_id'])}'>"
            f"{esc(meta['run_id'])}</a></td>"
            f"<td>{esc(meta['case_id'])}</td><td>{esc(meta['config_id'])}</td>"
            f"<td>{esc(meta.get('terminal_status', ''))}</td>"
            f"<td>{_badge_for(cs)}</td><td>{esc(entry['origin'])}</td></tr>")
    body = (f"<h1>Runs</h1><section class='card'><table><tr><th>Run</th>"
            "<th>Case</th><th>Config</th><th>Terminal status</th>"
            "<th>Scored verdict</th><th>Origin</th></tr>"
            + "".join(rows) + "</table>"
            "<p class='note'>“published” rows are the shipped evidence in "
            "results/runs (read-only); “session” rows were started from this "
            "interface and live in a scratch directory.</p></section>")
    return _page("Runs", body)


def _findings_table(findings: list[dict]) -> str:
    if not findings:
        return "<p class='note'>none</p>"
    rows = "".join(
        f"<tr><td>{esc(f.get('id', f.get('check', '')))}</td>"
        f"<td>{esc(f.get('severity', ''))}</td>"
        f"<td>{esc(f.get('claim_ref', ''))}</td>"
        f"<td>{esc(f.get('observation') or f.get('explanation', ''))}</td>"
        f"<td class='mono'>{esc((f.get('quoted_span') or '')[:160])}</td>"
        f"<td>{esc(f.get('recommended_correction', ''))}</td></tr>"
        for f in findings)
    return ("<table><tr><th>Id</th><th>Severity</th><th>Claim</th>"
            "<th>Observation / explanation</th><th>Quoted</th>"
            f"<th>Recommended</th></tr>{rows}</table>")


def run_page(state: UIState, run_id: str) -> Response:
    run = _load_run(run_id)
    if run is None:
        return _error_page("404 Not Found", f"no run {run_id}")
    meta = run["meta"]
    cs = _run_verdict(run)
    case = load_case(meta["case_id"])

    verdict_rows = ""
    if cs:
        for d in cs.defects_asserted:
            verdict_rows += (
                f"<tr><td>{esc(d.get('defect_id'))}</td><td>{esc(d.get('class'))}</td>"
                f"<td>{verdict_badge(d.get('verdict', 'asserted' if d.get('asserted') else 'clear'))}</td>"
                f"<td>{esc(d.get('evidence', ''))}</td></tr>")
    verdict_card = f"""
<section class="card"><h2>Scored verdict {_badge_for(cs)}</h2>
{kv_table([
    ("Terminal status", esc(meta.get('terminal_status'))),
    ("Unsafe reason", esc(cs.unsafe_reason) if cs and cs.unsafe_reason else "—"),
    ("Clean claims retained",
     f"{cs.clean_claims_retained}/{cs.clean_claims_total}" if cs else "n/a"),
    ("Scoring", f"case set {esc(CASE_SET_ID)}, policy v{SCORING_POLICY_VERSION}"),
])}
<h2>Planted-defect detectors</h2>
<table><tr><th>Defect</th><th>Class</th><th>Verdict</th><th>Evidence</th></tr>
{verdict_rows or '<tr><td colspan="4">no detector rows</td></tr>'}</table>
<p class="note">A HOLD verdict means the handling is semantically ambiguous: it is
counted unsafe for qualification scoring and a person must adjudicate it.</p>
</section>"""

    approval, why = gates.h1_status(meta["run_id"])
    if approval:
        h1_html = (f'<span class="badge safe">APPROVED</span> by '
                   f"{esc(approval.approver)} at {esc(approval.approved_utc)} "
                   f"(expires {esc(approval.expires_utc)})")
    else:
        h1_html = (f'<span class="badge blocked">NOT APPROVED</span>'
                   f'<p class="note">{esc(why)}</p>')
    render_form = f"""
<form method="post" action="/runs/{esc(meta['run_id'])}/render">
<input type="hidden" name="csrf" value="{esc(state.csrf_token)}">
<button class="primary" type="submit">Attempt A4 render</button>
</form>
<p class="note">Rendering is gated on H1. Without a verified, unexpired approval
bound to this exact run it refuses — try it. Approving H1 is a deliberate owner
action at an interactive terminal
(<code>python -m ssf_hve approve --run {esc(meta['run_id'])} --approver "…"</code>);
this interface cannot do it, by design.</p>"""
    gate_card = (f"<section class='card'><h2>Human gate H1</h2>{h1_html}"
                 f"{render_form}{_downloads_html(meta['run_id'])}</section>")

    meta_card = f"""
<section class="card"><h2>Run</h2>{kv_table([
    ("Run id", f"<span class='mono'>{esc(meta['run_id'])}</span>"),
    ("Case", f"{esc(meta['case_id'])} — {esc(case.title)}"),
    ("Configuration",
     f"{esc(meta['config_id'])} ({esc(meta.get('condition',''))}) — "
     f"{esc(CONFIGS[meta['config_id']].label) if meta['config_id'] in CONFIGS else ''}"),
    ("Mode / provider", f"{esc(meta.get('mode'))} / {esc(meta.get('provider'))} "
                        f"({esc(meta.get('model'))})"),
    ("Model calls", esc(meta.get('model_calls'))),
    ("Correction cycles", esc(meta.get('correction_cycles'))),
    ("Wall clock (s)", esc(meta.get('wall_clock_s'))),
    ("Started (UTC)", esc(meta.get('started_utc'))),
    ("Error", esc(meta.get('error') or '—')),
])}</section>"""

    narration = run.get("final_narration") or "(no script produced)"
    beats = (run.get("final_script") or {}).get("beats") or []
    beat_rows = "".join(
        f"<tr><td>{esc(b.get('beat'))}</td><td>{esc(b.get('narration'))}</td>"
        f"<td>{esc(b.get('on_screen', ''))}</td>"
        f"<td class='mono'>{esc(', '.join(b.get('claim_refs') or []))}</td></tr>"
        for b in beats)
    script_card = f"""
<section class="card"><h2>Script / narration</h2>{pre(narration)}
<details><summary>Beats and storyboard ({len(beats)})</summary>
<table><tr><th>Beat</th><th>Narration</th><th>On screen</th><th>Claims</th></tr>
{beat_rows}</table></details></section>"""

    cm = run.get("claim_map")
    if cm:
        claim_rows = "".join(
            f"<tr><td class='mono'>{esc(c.get('id'))}</td><td>{esc(c.get('text'))}</td>"
            f"<td>{esc(c.get('evidence_level'))}</td><td>{esc(c.get('scope'))}</td>"
            f"<td class='mono'>{esc(', '.join(c.get('evidence_refs') or []))}</td>"
            f"<td>{esc('; '.join(c.get('limitations') or []) or '—')}</td></tr>"
            for c in cm.get("claims", []))
        cm_card = f"""
<section class="card"><h2>A1 — claim map (extracted claims)</h2>
<table><tr><th>Id</th><th>Claim</th><th>Evidence level</th><th>Scope</th>
<th>Refs</th><th>Limitations</th></tr>{claim_rows}</table>
{('<p><b>Instruction-like text found in the source:</b> '
  + esc('; '.join(cm.get('embedded_instruction_text_found_in_source') or [])) + '</p>')
 if cm.get('embedded_instruction_text_found_in_source') else ''}
</section>"""
    else:
        cm_card = ("<section class='card'><h2>A1 — claim map</h2>"
                   "<p class='note'>This configuration runs no A1 stage.</p></section>")

    cycle_html = ""
    for cyc in run.get("cycles", []):
        v = cyc.get("verifier") or {}
        cycle_html += f"""
<details open><summary>Cycle {esc(cyc.get('index'))} —
{esc(cyc.get('blocking_count'))} blocking finding(s); action:
<code>{esc(cyc.get('action'))}</code></summary>
<p><b>Deterministic checks (code):</b></p>{_findings_table(cyc.get('deterministic_findings') or [])}
<p><b>A3 verifier:</b> {esc(v.get('recommendation', 'not run'))}
{('— ' + esc(v.get('rationale', ''))) if v else ''}</p>
{_findings_table(v.get('findings') or []) if v else ''}
</details>"""
    unresolved = run.get("unresolved_findings") or []
    review_card = f"""
<section class="card"><h2>Verification and review cycles</h2>
{cycle_html or "<p class='note'>no cycles recorded</p>"}
{('<h2>Unresolved at the correction bound</h2>' + _findings_table(unresolved))
 if unresolved else ''}
</section>"""

    step_rows = ""
    for st in run.get("steps", []):
        step_rows += f"""
<details><summary>Step {esc(st.get('index'))} — {esc(st.get('role'))}
({esc(st.get('kind'))}) {'✓' if st.get('ok') else '✗ ' + esc(st.get('error', ''))}
· provenance {esc(st.get('provenance') or 'n/a')}</summary>
<p class="note">prompt sha <span class="mono">{esc((st.get('prompt_sha256') or '')[:16])}…</span>
· tokens in/out {esc(st.get('input_tokens'))}/{esc(st.get('output_tokens'))}</p>
<p><b>Rendered instruction</b></p>{pre(st.get('rendered_prompt') or '')}
<p><b>Response</b></p>{pre(st.get('response_text') or '')}
<p class="note">parsed: <span class="mono">{esc(json.dumps(st.get('parsed_summary') or {}))}</span></p>
</details>"""
    steps_card = f"""
<section class="card"><h2>Workflow steps (agent calls, in order)</h2>
{step_rows or "<p class='note'>none</p>"}
<p><a href="/runs/{esc(meta['run_id'])}/trajectory">Full trajectory view</a> ·
<a href="/runs/{esc(meta['run_id'])}/trajectory.jsonl">raw JSONL</a></p></section>"""

    body = (f"<h1>Run {esc(meta['run_id'])}</h1>" + verdict_card + meta_card
            + gate_card + script_card + cm_card + review_card + steps_card)
    return _page(f"Run {meta['run_id']}", body)


def _downloads_html(run_id: str) -> str:
    pkg = SAMPLES_DIR / run_id
    if not pkg.is_dir():
        return ("<p class='note'><b>Production package:</b> none exists for this "
                "run. A4 writes one only after H1 is approved; nothing to "
                "download is the correct state here.</p>")
    links = "".join(
        f"<li><a href='/downloads/{esc(run_id)}/{esc(p.name)}'>{esc(p.name)}</a> "
        f"({p.stat().st_size} bytes)</li>"
        for p in sorted(pkg.iterdir()) if p.is_file() and _SAFE_FILENAME.match(p.name))
    return f"<p><b>Production package (H1 was approved for this run):</b></p><ul>{links}</ul>"


def trajectory_page(state: UIState, run_id: str, raw: bool = False) -> Response:
    run = _load_run(run_id)
    if run is None:
        return _error_page("404 Not Found", f"no run {run_id}")
    from ssf_hve.trajectory import export
    events = export.build_events(run)
    if raw:
        return Response(export.jsonl_text(events),
                        content_type="text/plain; charset=utf-8")
    md = export._markdown(run, events)
    body = (f"<h1>Trajectory — {esc(run_id)}</h1><section class='card'>"
            "<p class='note'>Rendered from the run record by the same exporter "
            "the CLI uses; the canonical JSONL of exactly these events is what "
            "an H1 approval's trajectory hash binds.</p>"
            f"{pre(md)}</section>")
    return _page(f"Trajectory {run_id}", body)


def render_post(state: UIState, run_id: str) -> Response:
    try:
        validate_run_id(run_id)
    except InvalidRunId as exc:
        return _error_page("400 Bad Request", str(exc))
    from ssf_hve.rendering.render import render_run
    result = render_run(run_id, allow_missing_ffmpeg=True)
    tone = "note" if result.ok else "error"
    body = (f"<h1>A4 render — {esc(run_id)}</h1><section class='card'>"
            f"<div class='{tone}'>{pre(result.summary())}</div>"
            f"<p><a href='/runs/{esc(run_id)}'>Back to the run</a></p></section>")
    return _page("Render", body, status="200 OK" if result.ok else "403 Forbidden")


def score_page(state: UIState) -> Response:
    rf = PUBLISHED_RUNS.parent / "results.json"
    if not rf.exists():
        return _page("Score", "<section class='card'>No published results.json "
                              "found.</section>")
    res = json.loads(rf.read_text(encoding="utf-8"))
    configs = res.get("configs", {})
    rows = ""
    for cid in ABLATION_ORDER:
        c = configs.get(cid)
        if not c:
            continue
        rows += (f"<tr><td><code>{esc(cid)}</code></td>"
                 f"<td><b>{c['unsafe_output_rate']:.2f}</b> "
                 f"({c['unsafe_count']}/{c['n_cases']})</td>"
                 f"<td>{c['clean_claim_retention']:.2f}</td>"
                 f"<td>{esc(c.get('false_flags'))}/{esc(c.get('verifier_findings'))}</td>"
                 f"<td>{esc(c.get('malformed_runs'))}</td>"
                 f"<td>{esc(c.get('error_runs'))}</td>"
                 f"<td>{esc(c.get('detector_holds_for_human', 0))}</td>"
                 f"<td>{esc(c.get('model_calls_total'))}</td></tr>")
    case_ids = sorted({cs["case_id"] for c in configs.values() for cs in c["cases"]})
    grid = ""
    for case_id in case_ids:
        cells = ""
        for cid in ABLATION_ORDER:
            c = configs.get(cid)
            if not c:
                continue
            hit = next((x for x in c["cases"] if x["case_id"] == case_id), None)
            if hit is None:
                cells += "<td>—</td>"
            else:
                v = ("hold" if hit.get("hold_for_human")
                     else ("unsafe" if hit.get("unsafe") else "safe"))
                cells += (f"<td>{verdict_badge(v)}<br>"
                          f"<span class='note'>{esc(hit.get('terminal_status'))}</span></td>")
        grid += f"<tr><td>{esc(case_id)}</td>{cells}</tr>"
    header_cells = "".join(f"<th><code>{esc(c)}</code></th>"
                           for c in ABLATION_ORDER if c in configs)
    body = f"""
<h1>Corrected score table</h1>
<section class="card">
<p class="note">Read from the published <code>results/results.json</code> —
gold table <span class="mono">{esc(res.get('gold_table_sha256', '')[:16])}…</span>,
case set {esc(CASE_SET_ID)}, scoring policy v{SCORING_POLICY_VERSION}.
Every number is derived from the run records by <code>score</code>; none is
hand-entered, and the provenance binding covers all inputs.</p>
<table><tr><th>Config</th><th>Unsafe output rate</th><th>Retention</th>
<th>False flags</th><th>Malformed</th><th>Errors</th><th>HOLDs</th>
<th>Model calls</th></tr>{rows}</table>
<p class="warn"><b>Honest headline:</b> the final workflow did <b>not</b> beat the
baseline on the primary metric — baseline 0.00 (0/30) against final 0.20 — because
the baseline never failed. See Comparisons for what did and did not move.</p>
</section>
<section class="card"><h2>Verdict by case</h2>
<table><tr><th>Case</th>{header_cells}</tr>{grid}</table></section>"""
    return _page("Score table", body)


def compare_page(state: UIState) -> Response:
    rf = PUBLISHED_RUNS.parent / "results.json"
    if not rf.exists():
        return _page("Comparisons", "<section class='card'>No results.json.</section>")
    res = json.loads(rf.read_text(encoding="utf-8"))
    configs = res.get("configs", {})

    def row(cid, note=""):
        c = configs.get(cid)
        if not c:
            return ""
        return (f"<tr><td><code>{esc(cid)}</code></td>"
                f"<td>{c['unsafe_output_rate']:.2f} ({c['unsafe_count']}/{c['n_cases']})</td>"
                f"<td>{c['clean_claim_retention']:.2f}</td>"
                f"<td>{esc(c.get('malformed_runs'))}</td>"
                f"<td>{esc(c.get('model_calls_total'))}</td><td>{note}</td></tr>")

    body = f"""
<h1>Baseline vs final, and the removal experiments</h1>
<section class="card"><h2>Baseline versus final</h2>
<table><tr><th>Config</th><th>Unsafe rate</th><th>Retention</th><th>Malformed</th>
<th>Calls</th><th></th></tr>
{row('baseline', 'one direct prompt; 3 samples per case')}
{row('final', 'the shipped staged workflow')}
</table>
<p class="warn">The negative result, stated plainly: <b>final did not outperform
the baseline on the primary metric</b> (0.20 against 0.00) and the baseline had no
headroom to improve. The measured gains are inside the workflow — retention
0.81 → 0.96 with the claim map (iter-2), malformed 2 → 1 with split observation
(iter-3 → iter-4) — not against the baseline.</p></section>
<section class="card"><h2>Removal experiments (deliberately unsafe controls)</h2>
<table><tr><th>Config</th><th>Unsafe rate</th><th>Retention</th><th>Malformed</th>
<th>Calls</th><th></th></tr>
{row('final', 'reference')}
{row('rm-bound-ok', 'byte-identical C09 script relabelled ACCEPT at the bound — and the metric REWARDS it')}
{row('rm-model-checks', 'deterministic checks routed through the model — the strongest quantitative removal result')}
</table>
<p class="note"><code>rm-bound-ok</code> scoring better than <code>final</code>
(0.10 vs 0.20) is a control-safety counterexample, not an improvement: one boolean
relabels an unresolved run as finished and buys ten points of the headline metric.
<code>final</code> ships anyway because HOLD is the true description of that run.
<code>rm-model-checks</code> shows retention 0.86 → 0.36 and malformed 1 → 6 when
code-checkable work is pushed onto the model.</p></section>
<section class="card"><h2>Full ladder</h2>
<table><tr><th>Config</th><th>Unsafe rate</th><th>Retention</th><th>Malformed</th>
<th>Calls</th><th></th></tr>
{''.join(row(c) for c in ABLATION_ORDER)}
</table></section>"""
    return _page("Comparisons", body)


def provenance_page(state: UIState) -> Response:
    from ssf_hve.provenance import render as prender, verify as pverify
    report = pverify()
    ok = not report.failures
    verdict = ("<div class='note'><b>PASS — all checked relationships hold.</b></div>"
               if ok else "<div class='error'><b>FAIL — the repository and its "
                          "binding disagree.</b></div>")
    body = (f"<h1>Provenance verification</h1><section class='card'>{verdict}"
            f"{pre(prender(report))}</section>")
    return _page("Provenance", body, status="200 OK" if ok else "500 Internal Server Error")


def gates_page(state: UIState, query: dict) -> Response:
    run_q = (query.get("run") or [""])[0]
    h1_html = ""
    if run_q:
        try:
            validate_run_id(run_q)
            rec, why = gates.h1_status(run_q)
            if rec:
                h1_html = (f"<p>{esc(run_q)}: <span class='badge safe'>APPROVED</span> "
                           f"by {esc(rec.approver)} at {esc(rec.approved_utc)}, "
                           f"expires {esc(rec.expires_utc)}</p>")
            else:
                h1_html = (f"<p>{esc(run_q)}: <span class='badge blocked'>NOT "
                           f"APPROVED</span></p><p class='note'>{esc(why)}</p>")
        except InvalidRunId as exc:
            h1_html = f"<div class='error'>{esc(exc)}</div>"
    dist = ROOT / "dist"
    archives = sorted(dist.glob("*.zip")) if dist.exists() else []
    arch_q = (query.get("archive") or [""])[0]
    h2_html = ""
    if arch_q:
        if not _SAFE_ARCHIVE.match(arch_q) or not (dist / arch_q).exists():
            h2_html = "<div class='error'>unknown archive</div>"
        else:
            from ssf_hve.submission import binding_statement, collect_binding
            binding = collect_binding(dist / arch_q)
            statement = binding_statement(binding)
            rec = gates.approval_for("H2", statement)
            state_html = (f"<span class='badge safe'>APPROVED</span> by "
                          f"{esc(rec.approver)} at {esc(rec.approved_utc)}"
                          if rec else "<span class='badge blocked'>NOT APPROVED"
                                      "</span> for this exact package")
            h2_html = (f"<p>{esc(arch_q)}: {state_html}</p>"
                       f"<details><summary>Binding statement (what H2 would "
                       f"approve)</summary>{pre(statement)}</details>")
    arch_links = "".join(
        f"<li><a href='/gates?archive={esc(p.name)}'>{esc(p.name)}</a> "
        f"({p.stat().st_size} bytes)</li>" for p in archives) or "<li>none built</li>"
    body = f"""
<h1>Human gates</h1>
<section class="card"><h2>H1 — one exact run's script</h2>
<p class="note">An H1 approval binds the run id, narration hash, byte-exact run
record, canonical trajectory, candidate script and configuration, and expires.
This page only <b>reports</b> gate state. Approving is a deliberate owner action
at an interactive terminal; no browser control for it exists, by design.</p>
<form method="get" action="/gates">
<label>Check a run id: <input name="run" value="{esc(run_q)}" size="36"
class="mono"></label> <button type="submit">Check H1</button></form>
{h1_html}</section>
<section class="card"><h2>H2 — one exact submission package</h2>
<p class="note">H2 approves a binding statement over the archive digest, manifest
digest, sizes, filenames, verified commit evidence and video hash. The only
route is <code>approve-submission</code> at a terminal — after the final archive
and video exist, never before, and never from here.</p>
<ul>{arch_links}</ul>{h2_html}</section>"""
    return _page("Gates", body)


def providers_page(state: UIState) -> Response:
    import os

    from ssf_hve.providers.live import (API_KEY_ENV, ENDPOINT_ENV,
                                        ENDPOINT_OPT_IN_ENV, UnsafeEndpoint,
                                        resolve_endpoint)
    from ssf_hve.replay.store import FixtureStore
    store = FixtureStore()
    counts = store.provenance_summary()
    fixture_rows = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>"
                           for k, v in sorted(counts.items()))
    key_state = ("configured (value never shown)"
                 if os.environ.get(API_KEY_ENV, "").strip() else "not configured")
    try:
        endpoint = resolve_endpoint()
        host = urllib.parse.urlparse(endpoint).hostname
        endpoint_state = f"resolves to host <code>{esc(host)}</code>"
    except UnsafeEndpoint as exc:
        endpoint_state = f"refused: {esc(exc)}"
    custom = "set" if os.environ.get(ENDPOINT_ENV, "").strip() else "not set"
    optin = "set" if os.environ.get(ENDPOINT_OPT_IN_ENV, "").strip() else "not set"
    body = f"""
<h1>Provider status</h1>
<section class="card"><h2>Replay (default)</h2>
<p>{sum(counts.values())} fixtures on disk, keys verified on load, provenance:</p>
<table><tr><th>Provenance</th><th>Count</th></tr>{fixture_rows}</table>
<p class="note">Replay serves recorded responses from disk and opens no network
connection; a prompt with no fixture fails closed.</p></section>
<section class="card"><h2>Live (optional, explicitly separated)</h2>
{kv_table([
    ("Server flag --allow-live", "enabled" if state.allow_live else "disabled"),
    (f"{API_KEY_ENV}", esc(key_state)),
    ("Endpoint", endpoint_state),
    (f"{ENDPOINT_ENV} (custom endpoint)", esc(custom)),
    (f"{ENDPOINT_OPT_IN_ENV} (explicit opt-in)", esc(optin)),
])}
<p class="note">Keys are read from the environment only. There is no key-entry
form, keys are never stored by this interface, and no page prints one. A custom
endpoint must be HTTPS and explicitly opted into.</p></section>"""
    return _page("Providers", body)


def download(state: UIState, run_id: str, filename: str) -> Response:
    try:
        rid = validate_run_id(run_id)
    except InvalidRunId as exc:
        return _error_page("400 Bad Request", str(exc))
    if not _SAFE_FILENAME.match(filename) or ".." in filename:
        return _error_page("400 Bad Request", "refused filename")
    base = (SAMPLES_DIR / rid).resolve()
    target = (base / filename).resolve()
    if base not in target.parents or not target.is_file():
        return _error_page("404 Not Found",
                           "No such production-package file. A package exists "
                           "only after a person approves H1 for the run.")
    ctype = ("text/plain; charset=utf-8"
             if target.suffix in (".txt", ".srt", ".json", ".md") else
             "application/octet-stream")
    return Response(target.read_bytes(), content_type=ctype,
                    headers=[("Content-Disposition",
                              f'attachment; filename="{filename}"')])


# ------------------------------------------------------------------ the app

_ROUTES = [
    ("GET", re.compile(r"^/$"), lambda st, m, q, f: home(st)),
    ("POST", re.compile(r"^/run$"), lambda st, m, q, f: run_post(st, f)),
    ("GET", re.compile(r"^/jobs/([0-9a-f]{12})$"),
     lambda st, m, q, f: job_page(st, m.group(1))),
    ("GET", re.compile(r"^/runs$"), lambda st, m, q, f: runs_page(st)),
    ("GET", re.compile(r"^/runs/([^/]+)$"),
     lambda st, m, q, f: run_page(st, m.group(1))),
    ("GET", re.compile(r"^/runs/([^/]+)/trajectory$"),
     lambda st, m, q, f: trajectory_page(st, m.group(1))),
    ("GET", re.compile(r"^/runs/([^/]+)/trajectory\.jsonl$"),
     lambda st, m, q, f: trajectory_page(st, m.group(1), raw=True)),
    ("POST", re.compile(r"^/runs/([^/]+)/render$"),
     lambda st, m, q, f: render_post(st, m.group(1))),
    ("GET", re.compile(r"^/score$"), lambda st, m, q, f: score_page(st)),
    ("GET", re.compile(r"^/compare$"), lambda st, m, q, f: compare_page(st)),
    ("GET", re.compile(r"^/provenance$"), lambda st, m, q, f: provenance_page(st)),
    ("GET", re.compile(r"^/gates$"), lambda st, m, q, f: gates_page(st, q)),
    ("GET", re.compile(r"^/providers$"), lambda st, m, q, f: providers_page(st)),
    ("GET", re.compile(r"^/downloads/([^/]+)/([^/]+)$"),
     lambda st, m, q, f: download(st, m.group(1), m.group(2))),
]


class JudgeUI:
    """WSGI application object. State is per-instance; no globals, no storage."""

    def __init__(self, state: UIState | None = None):
        self.state = state or UIState()

    def __call__(self, environ, start_response):
        try:
            resp = self._dispatch(environ)
        except InvalidRunId as exc:
            resp = _error_page("400 Bad Request", str(exc))
        except Exception as exc:                                 # noqa: BLE001
            resp = _error_page("500 Internal Server Error",
                               f"{type(exc).__name__}: {exc}")
        start_response(resp.status, resp.headers)
        return [resp.body]

    def _dispatch(self, environ) -> Response:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        raw_path = environ.get("PATH_INFO", "/") or "/"
        path = urllib.parse.unquote(raw_path)
        query = urllib.parse.parse_qs(environ.get("QUERY_STRING", ""))
        form: dict = {}
        if method == "POST":
            try:
                length = min(int(environ.get("CONTENT_LENGTH") or 0), MAX_FORM_BYTES)
            except ValueError:
                length = 0
            body = environ["wsgi.input"].read(length).decode("utf-8", "replace")
            form = urllib.parse.parse_qs(body)
            token = (form.get("csrf") or [""])[0]
            if not secrets.compare_digest(token, self.state.csrf_token):
                return _error_page(
                    "403 Forbidden",
                    "State-changing requests require the per-session CSRF token "
                    "embedded in this interface's own forms. Cross-site or "
                    "replayed POSTs are refused.")
        for verb, pattern, handler in _ROUTES:
            m = pattern.match(path)
            if not m:
                continue
            if verb != method:
                return _error_page("405 Method Not Allowed",
                                  f"{method} is not allowed on {path}")
            return handler(self.state, m, query, form)
        return _error_page("404 Not Found", f"no route for {path}")


def build_app(*, allow_live: bool = False, background: bool = True) -> JudgeUI:
    return JudgeUI(UIState(allow_live=allow_live, background=background))
