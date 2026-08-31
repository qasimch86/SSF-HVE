"""CLI behaviour and exit codes."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, results_dir=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    if results_dir:
        env["SSF_HVE_RESULTS_DIR"] = str(results_dir)
    return subprocess.run([sys.executable, "-m", "ssf_hve", *args],
                          cwd=ROOT, env=env, capture_output=True, text=True)


def test_version():
    p = run("--version")
    assert p.returncode == 0 and "ssf-hve" in p.stdout


def test_unknown_command_is_a_usage_error():
    assert run("frobnicate").returncode != 0


def test_verify_gold_matches():
    p = run("verify-gold")
    assert p.returncode == 0 and "MATCH" in p.stdout


def test_fixture_integrity_command():
    p = run("fixtures")
    assert p.returncode == 0
    assert "all fixture keys verified" in p.stdout
    assert "live-api" not in p.stdout, "no fixture may claim a live API capture"


def test_unknown_case_is_reported_clearly(tmp_path):
    p = run("baseline", "--case", "C99", "--replay", results_dir=tmp_path)
    assert p.returncode != 0
    assert "no such case" in (p.stdout + p.stderr)


def test_baseline_replay_succeeds_without_a_key(tmp_path):
    env_had_key = os.environ.pop("SSF_HVE_API_KEY", None)
    try:
        p = run("baseline", "--case", "C01", "--replay", results_dir=tmp_path)
        assert p.returncode == 0, p.stdout + p.stderr
        assert "status=ACCEPT" in p.stdout
    finally:
        if env_had_key:
            os.environ["SSF_HVE_API_KEY"] = env_had_key


def test_hold_returns_exit_code_2(tmp_path):
    p = run("run", "--case", "C09", "--config", "final", "--replay",
            results_dir=tmp_path)
    assert p.returncode == 2 and "HOLD" in p.stdout


def test_malformed_returns_exit_code_2(tmp_path):
    p = run("run", "--case", "C10", "--config", "final", "--replay",
            results_dir=tmp_path)
    assert p.returncode == 2 and "MALFORMED" in p.stdout


def test_missing_fixture_returns_exit_code_3(tmp_path):
    """Replay fails closed on an unseen prompt rather than inventing a response."""
    p = run("run", "--case", "C01", "--config", "final", "--replay",
            "--model", "a-model-nobody-captured", results_dir=tmp_path)
    assert p.returncode == 3
    assert "missing replay fixture" in (p.stdout + p.stderr)


def test_live_mode_requires_an_explicit_key(tmp_path):
    env_had_key = os.environ.pop("SSF_HVE_API_KEY", None)
    try:
        p = run("baseline", "--case", "C01", "--live", results_dir=tmp_path)
        assert p.returncode == 1
        assert "SSF_HVE_API_KEY" in (p.stdout + p.stderr)
    finally:
        if env_had_key:
            os.environ["SSF_HVE_API_KEY"] = env_had_key


def test_gate_status_reports_not_approved(tmp_path):
    run("run", "--case", "C04", "--config", "final", "--replay", results_dir=tmp_path)
    runs = sorted((tmp_path / "runs").glob("C04-final-*.json"))
    assert runs
    p = run("gate-status", "--run", runs[-1].stem, results_dir=tmp_path)
    assert p.returncode == 4 and "NOT APPROVED" in p.stdout


def test_render_refuses_without_h1(tmp_path):
    run("run", "--case", "C04", "--config", "final", "--replay", results_dir=tmp_path)
    runs = sorted((tmp_path / "runs").glob("C04-final-*.json"))
    p = run("render", "--run", runs[-1].stem, results_dir=tmp_path)
    assert "H1 is not approved" in p.stdout
    assert p.returncode == 2
