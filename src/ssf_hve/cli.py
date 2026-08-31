"""Command line interface.

Exit codes
  0  success
  1  usage, configuration or IO error
  2  the workflow terminated HOLD, or unresolved findings remain
  3  replay incomplete - a fixture is missing for this exact prompt
  4  a human gate is not approved
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ssf_hve import __version__, gates
from ssf_hve.cases import all_case_ids, load_case
from ssf_hve.config import ABLATION_ORDER, CONFIGS, get_config
from ssf_hve.paths import (GOLD_TABLE, RESULTS_DIR, RUNS_DIR, InvalidRunId,
                           ensure_dirs, run_record_path)
from ssf_hve.providers import DEFAULT_MODEL, get_provider
from ssf_hve.providers.replay import PENDING_DIR
from ssf_hve.replay.store import FixtureStore
from ssf_hve.runner import execute

EXIT_OK, EXIT_USAGE, EXIT_HOLD, EXIT_REPLAY, EXIT_GATE = 0, 1, 2, 3, 4


def _provider(args):
    if getattr(args, "live", False):
        try:
            return get_provider(live=True, model=args.model)
        except Exception as exc:                     # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            raise SystemExit(EXIT_USAGE)
    return get_provider(live=False, model=args.model)


def _mode(args) -> str:
    return "live" if getattr(args, "live", False) else "replay"


def _run_one(case_id: str, config_id: str, args, sample: int = 1) -> int:
    case = load_case(case_id)
    config = get_config(config_id)
    rec = execute(case, config, _provider(args), mode=_mode(args), sample=sample)
    status = rec.meta.terminal_status
    print(f"{case_id}  config={config_id}  s{sample}  status={status}  "
          f"cycles={rec.meta.correction_cycles}  calls={rec.meta.model_calls}  "
          f"run={rec.meta.run_id}")
    if rec.meta.error:
        print(f"  error: {rec.meta.error}", file=sys.stderr)
    if rec.h1_gate.get("state") == "BLOCKED_AWAITING_HUMAN":
        print(f"  H1: awaiting human approval of {rec.h1_gate['artifact_sha256'][:16]}…")
    if status == "ERROR" and "missing replay fixture" in rec.meta.error:
        return EXIT_REPLAY
    if status in ("HOLD", "REWORK", "MALFORMED", "ERROR"):
        return EXIT_HOLD
    return EXIT_OK


def cmd_baseline(args) -> int:
    return _run_one(args.case, "baseline", args)


def cmd_run(args) -> int:
    return _run_one(args.case, args.config, args, sample=getattr(args, "sample", 1))


def cmd_evaluate(args) -> int:
    ensure_dirs()
    cases = all_case_ids() if args.all else [args.case]
    if not cases or cases == [None]:
        print("error: pass --all or --case Cnn", file=sys.stderr)
        return EXIT_USAGE
    configs = [args.config] if args.config else ["baseline", "final"]
    worst = EXIT_OK
    samples = max(1, int(getattr(args, "samples", 1) or 1))
    for config_id in configs:
        get_config(config_id)
        for case_id in cases:
            for sample in range(1, samples + 1):
                rc = _run_one(case_id, config_id, args, sample=sample)
                worst = max(worst, rc)
    print(f"\nevaluated {len(cases)} case(s) x {len(configs)} config(s). "
          f"Score with: python -m ssf_hve score")
    return worst


def cmd_score(args) -> int:
    from ssf_hve.scoring.report import score_all, write_reports
    scored = score_all()
    if not scored:
        print("no runs found in results/runs. Run an evaluation first.",
              file=sys.stderr)
        return EXIT_USAGE
    jpath, mpath = write_reports(scored)
    for cid in ABLATION_ORDER:
        s = scored.get(cid)
        if not s:
            continue
        print(f"{cid:16s} UOR={s.unsafe_output_rate:.2f} ({s.unsafe_count}/{s.n_cases})"
              f"  clean-claim retention={s.clean_claim_retention:.2f}"
              f"  malformed={s.malformed_runs} errors={s.error_runs}")
    print(f"\nwrote {mpath}\nwrote {jpath}")
    return EXIT_OK


def cmd_verify_gold(args) -> int:
    import hashlib
    with GOLD_TABLE.open(encoding="utf-8") as fh:
        doc = json.load(fh)
    blob = json.dumps(doc["payload"], sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    actual = hashlib.sha256(blob).hexdigest()
    ok = actual == doc["gold_table_sha256"]
    print(f"gold table: {GOLD_TABLE}")
    print(f"recorded : {doc['gold_table_sha256']}")
    print(f"computed : {actual}")
    print("MATCH" if ok else "MISMATCH - the frozen table has been edited")
    return EXIT_OK if ok else EXIT_USAGE


def cmd_verify_provenance(args) -> int:
    from ssf_hve.provenance import render, verify
    report = verify()
    print(render(report))
    return EXIT_OK if not report.failures else EXIT_USAGE


def cmd_ui(args) -> int:
    """Local judge UI on 127.0.0.1. Replay by default; live only behind
    --allow-live plus the same environment variable the CLI already uses."""
    from ssf_hve.ui.server import serve
    return serve(port=args.port, allow_live=args.allow_live)


def cmd_bind_provenance(args) -> int:
    """Regenerate the active provenance binding. A deliberate act, not a fix:
    the resulting diff in git IS the record of what changed."""
    from ssf_hve.provenance import BINDING_FILE, write_binding
    existed = BINDING_FILE.exists()
    path = write_binding()
    print(f"{'rewrote' if existed else 'wrote'} {path}")
    print("Commit the change. verify-provenance fails whenever any bound file "
          "no longer matches this binding.")
    return EXIT_OK


def cmd_pending(args) -> int:
    if not PENDING_DIR.exists():
        print("no pending captures")
        return EXIT_OK
    metas = sorted(PENDING_DIR.glob("*.meta.json"))
    store = FixtureStore()
    open_items = []
    for m in metas:
        info = json.loads(m.read_text(encoding="utf-8"))
        if not store.has(info["key"]):
            open_items.append(info)
    for info in open_items:
        print(f"{info['key']}  role={info['role']}  model={info['model']}")
    print(f"\n{len(open_items)} prompt(s) awaiting a captured response.")
    print(f"Prompts are in {PENDING_DIR}")
    return EXIT_OK


def cmd_ingest_fixture(args) -> int:
    store = FixtureStore()
    meta_path = PENDING_DIR / f"{args.key}.meta.json"
    prompt_path = PENDING_DIR / f"{args.key}.prompt.txt"
    if not meta_path.exists() or not prompt_path.exists():
        print(f"error: no pending capture for key {args.key}", file=sys.stderr)
        return EXIT_USAGE
    info = json.loads(meta_path.read_text(encoding="utf-8"))
    response = Path(args.response_file).read_text(encoding="utf-8")
    fx = store.record(role=info["role"], model=info["model"],
                      rendered_prompt=prompt_path.read_text(encoding="utf-8"),
                      response_text=response, provenance=args.provenance,
                      note=args.note or "")
    print(f"stored fixture {fx.key[:16]}… role={fx.role} provenance={fx.provenance}")
    return EXIT_OK


def cmd_fixtures(args) -> int:
    store = FixtureStore()
    counts = store.provenance_summary()
    total = sum(counts.values())
    print(f"{total} fixture(s) in {store.root}")
    for k, v in sorted(counts.items()):
        print(f"  {k:26s} {v}")
    bad = []
    for p in sorted(store.root.glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        from ssf_hve.replay.store import Fixture
        if not Fixture(**raw).verify_key():
            bad.append(p.name)
    if bad:
        print(f"\nINTEGRITY FAILURE - key does not match prompt: {bad}", file=sys.stderr)
        return EXIT_USAGE
    print("\nall fixture keys verified against their stored prompts")
    return EXIT_OK


def cmd_export_trajectory(args) -> int:
    from ssf_hve.trajectory.export import export_run
    try:
        paths = export_run(args.run)
    except InvalidRunId as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    for p in paths:
        print(f"wrote {p}")
    return EXIT_OK


def cmd_render(args) -> int:
    from ssf_hve.rendering.render import render_run
    result = render_run(args.run, allow_missing_ffmpeg=True)
    print(result.summary())
    return EXIT_OK if result.ok else EXIT_HOLD


def cmd_approve(args) -> int:
    """Gate H1 only. H2 has exactly one route: `approve-submission`."""
    try:
        rec = gates.approve_h1(args.run, approver=args.approver,
                               note=args.note or "",
                               valid_days=args.valid_days)
    except InvalidRunId as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except gates.GateSecretMissing as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_GATE
    except gates.NotAHuman as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_GATE
    except gates.GateNotApproved as exc:
        print(f"not approved: {exc}", file=sys.stderr)
        return EXIT_GATE
    print(f"{rec.gate} approved by {rec.approver} at {rec.approved_utc} "
          f"for run {rec.binding['run_id']} "
          f"(narration {rec.artifact_sha256[:16]}…, expires {rec.expires_utc})")
    return EXIT_OK


def cmd_gate_status(args) -> int:
    if getattr(args, "archive", None):
        return _h2_status(args)
    if not getattr(args, "run", None):
        print("error: gate-status needs --run (H1) or --archive (H2)", file=sys.stderr)
        return EXIT_USAGE
    try:
        run_path = run_record_path(args.run)
    except InvalidRunId as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if not run_path.exists():
        print(f"error: no run {args.run}", file=sys.stderr)
        return EXIT_USAGE
    run = json.loads(run_path.read_text(encoding="utf-8"))
    artifact = run.get("final_narration") or ""
    rec, why = gates.h1_status(args.run)
    if rec is None:
        print(f"H1: NOT APPROVED for run {args.run} "
              f"(narration {gates.artifact_sha256(artifact)[:16]}…)")
        print(f"  reason: {why}")
        return EXIT_GATE
    print(f"H1: approved by {rec.approver} at {rec.approved_utc} "
          f"(expires {rec.expires_utc})")
    print(f"  bound to run {rec.binding['run_id']}: run record, trajectory, "
          "candidate and configuration hashes all verified")
    print("  signature verified")
    return EXIT_OK


def _h2_binding(args):
    from ssf_hve.submission import binding_statement, collect_binding
    archive = Path(args.archive)
    video = Path(args.video) if getattr(args, "video", None) else None
    binding = collect_binding(archive, video)
    return binding, binding_statement(binding)


def _h2_status(args) -> int:
    try:
        binding, statement = _h2_binding(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    rec = gates.approval_for("H2", statement)
    print(f"archive          : {binding['archive_filename']} "
          f"({binding['archive_bytes']} bytes)")
    print(f"archive sha256   : {binding['archive_sha256']}")
    print(f"manifest sha256  : {binding['manifest_sha256']}")
    print(f"archive commit   : {binding['archive_commit']}")
    print(f"                   {binding['archive_commit_evidence']}")
    print(f"checkout         : {binding['checkout_head']} "
          f"({binding['checkout_tree_state']}) — the checkout running this "
          "check, not a property of the archive")
    if "video_sha256" in binding:
        print(f"video sha256     : {binding['video_sha256']}")
    print(f"statement sha256 : {gates.artifact_sha256(statement)}")
    if rec is None:
        print("H2: NOT APPROVED for this exact package")
        print(f"  reason: {gates.why_not_approved('H2', statement)}")
        return EXIT_GATE
    print(f"H2: approved by {rec.approver} at {rec.approved_utc}")
    print("  signature verified")
    return EXIT_OK


def cmd_approve_submission(args) -> int:
    """Gate H2. Binds one approval to one exact package. Uploads nothing."""
    try:
        binding, statement = _h2_binding(args)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if args.show:
        print(statement)
        print(f"statement sha256 : {gates.artifact_sha256(statement)}")
        print("\nNot approved. Re-run without --show to approve interactively.")
        return EXIT_OK
    print(statement)
    try:
        rec = gates.record_approval("H2", statement, "submission package",
                                    approver=args.approver, note=args.note or "",
                                    binding=binding)
    except gates.GateSecretMissing as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_GATE
    except gates.NotAHuman as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return EXIT_GATE
    except gates.GateNotApproved as exc:
        print(f"not approved: {exc}", file=sys.stderr)
        return EXIT_GATE
    print(f"H2 approved by {rec.approver} at {rec.approved_utc} "
          f"for statement {rec.artifact_sha256[:16]}…")
    print("This approval covers this package only. Nothing has been uploaded.")
    return EXIT_OK


def cmd_package(args) -> int:
    from ssf_hve.packaging import ALLOWLIST, build
    out = Path(args.out)
    report = build(out, dry_run=args.dry_run)
    print(f"allowlist patterns : {len(ALLOWLIST)}")
    print(f"files selected     : {len(report.files)}")
    print(f"total size         : {report.total_bytes / 1024:.0f} KiB")
    if report.refused:
        print("\nREFUSED - the archive was not written:", file=sys.stderr)
        for r in report.refused:
            print(f"  {r}", file=sys.stderr)
        return EXIT_USAGE
    if args.list:
        print("\nfile list:")
        for f in report.files:
            print(f"  {f.relative_to(Path(__file__).resolve().parents[2])}")
    if args.dry_run:
        print("\ndry run: nothing written. Inspected and clean.")
        return EXIT_OK
    print(f"\nwrote {report.archive}")
    print(f"sha256 {report.sha256}")
    print("\nH2 is not approved by this command and cannot be. Nothing has been "
          "uploaded, published or submitted.")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ssf_hve",
        description="SSF-HVE - research paper to verified scientific video")
    p.add_argument("--version", action="version", version=f"ssf-hve {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--replay", action="store_true", default=True,
                        help="use recorded fixtures (default)")
        sp.add_argument("--live", action="store_true",
                        help="call the provider API; requires SSF_HVE_API_KEY")
        sp.add_argument("--model", default=DEFAULT_MODEL)

    sp = sub.add_parser("baseline", help="one direct prompt, one case")
    sp.add_argument("--case", required=True)
    add_common(sp)
    sp.set_defaults(func=cmd_baseline)

    sp = sub.add_parser("run", help="the staged workflow, one case")
    sp.add_argument("--case", required=True)
    sp.add_argument("--config", default="final", choices=list(CONFIGS))
    sp.add_argument("--sample", type=int, default=1)
    add_common(sp)
    sp.set_defaults(func=cmd_run)

    sp = sub.add_parser("evaluate", help="run a configuration over the case set")
    sp.add_argument("--all", action="store_true")
    sp.add_argument("--case")
    sp.add_argument("--config", choices=list(CONFIGS))
    sp.add_argument("--samples", type=int, default=1,
                    help="independent samples per case (default 1)")
    add_common(sp)
    sp.set_defaults(func=cmd_evaluate)

    sp = sub.add_parser("score", help="score every run against the frozen gold table")
    sp.set_defaults(func=cmd_score)

    sp = sub.add_parser("verify-gold", help="recompute the frozen gold table hash")
    sp.set_defaults(func=cmd_verify_gold)

    sp = sub.add_parser(
        "verify-provenance",
        help="check which case set, scorer policy and gold table produced results/, "
             "and report where a documented claim rests on a self-assertion")
    sp.set_defaults(func=cmd_verify_provenance)

    sp = sub.add_parser(
        "ui", help="local judge interface on 127.0.0.1 (replay by default; "
                   "runs land in a throwaway session directory)")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--allow-live", action="store_true",
                    help="permit live-mode runs from the UI (still requires "
                         "SSF_HVE_API_KEY in the environment; never entered in "
                         "the browser)")
    sp.set_defaults(func=cmd_ui)

    sp = sub.add_parser(
        "bind-provenance",
        help="regenerate evaluation/provenance_binding.json over the active "
             "cases, gold table, prompts, scorer source, fixtures and run records")
    sp.set_defaults(func=cmd_bind_provenance)

    sp = sub.add_parser("pending", help="prompts awaiting a captured response")
    sp.set_defaults(func=cmd_pending)

    sp = sub.add_parser("ingest-fixture", help="store a captured response as a fixture")
    sp.add_argument("--key", required=True)
    sp.add_argument("--response-file", required=True)
    sp.add_argument("--provenance", required=True,
                    choices=["live-api", "blinded-agent-capture", "handcrafted"])
    sp.add_argument("--note", default="")
    sp.set_defaults(func=cmd_ingest_fixture)

    sp = sub.add_parser("fixtures", help="fixture inventory and integrity check")
    sp.set_defaults(func=cmd_fixtures)

    sp = sub.add_parser("export-trajectory", help="export one run as JSONL + Markdown")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=cmd_export_trajectory)

    sp = sub.add_parser("render", help="deterministic production of the demo package")
    sp.add_argument("--run", required=True)
    sp.set_defaults(func=cmd_render)

    sp = sub.add_parser(
        "approve",
        help="gate H1: human-only approval bound to one exact run (interactive). "
             "H2 has exactly one route: approve-submission.")
    sp.add_argument("--run", required=True)
    sp.add_argument("--approver", required=True)
    sp.add_argument("--note", default="")
    sp.add_argument("--valid-days", type=int, default=gates.H1_DEFAULT_VALID_DAYS,
                    help="freshness window in days (signed into the approval; "
                         f"default {gates.H1_DEFAULT_VALID_DAYS})")
    sp.set_defaults(func=cmd_approve)

    sp = sub.add_parser(
        "approve-submission",
        help="gate H2: human-only approval bound to one exact package (uploads nothing)")
    sp.add_argument("--archive", default="dist/ssf-hve-submission.zip")
    sp.add_argument("--video", default="")
    sp.add_argument("--approver", required=True)
    sp.add_argument("--note", default="")
    sp.add_argument("--show", action="store_true",
                    help="print the binding statement and its hash, approve nothing")
    sp.set_defaults(func=cmd_approve_submission)

    sp = sub.add_parser("package", help="build the allowlisted submission archive")
    sp.add_argument("--out", default="dist/ssf-hve-submission.zip")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--list", action="store_true", help="print the full file list")
    sp.set_defaults(func=cmd_package)

    sp = sub.add_parser("gate-status",
                        help="report gate state for a run (H1) or a package (H2)")
    sp.add_argument("--run", default="")
    sp.add_argument("--archive", default="",
                    help="check H2 for this package instead of a run")
    sp.add_argument("--video", default="")
    sp.set_defaults(func=cmd_gate_status)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        code = exc.code
        if isinstance(code, int):
            return code
        print(code, file=sys.stderr)
        return EXIT_USAGE
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
