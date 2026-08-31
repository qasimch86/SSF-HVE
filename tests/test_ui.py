"""The judge UI: thin over the domain services, safe by construction.

Covers the remediation brief's required list: startup, replay execution with
no keys, case/config validation, results rendering, SAFE/UNSAFE/HOLD
presentation, gate-status presentation, render refusal without H1, download
containment, run-id traversal, CSRF protection, secret non-disclosure,
live-mode opt-in, no database, no effect on scoring or provenance, and no
imports from any other application.
"""
import ast
import io
import json
import os
import re
from pathlib import Path

import pytest

from ssf_hve.paths import RUNS_DIR
from ssf_hve.ui.app import JudgeUI, build_app

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "src" / "ssf_hve" / "ui"


# ------------------------------------------------------------ tiny WSGI client

class Client:
    def __init__(self, app: JudgeUI):
        self.app = app

    def request(self, method: str, path: str, data: dict | None = None):
        from urllib.parse import urlencode
        query = ""
        if "?" in path:
            path, query = path.split("?", 1)
        body = urlencode(data or {}).encode() if data is not None else b""
        environ = {
            "REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": query,
            "CONTENT_LENGTH": str(len(body)), "wsgi.input": io.BytesIO(body),
        }
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        chunks = self.app(environ, start_response)
        return (captured["status"], captured["headers"],
                b"".join(chunks).decode("utf-8", "replace"))

    def get(self, path):
        return self.request("GET", path)

    def post(self, path, data):
        return self.request("POST", path, data)


@pytest.fixture()
def app():
    return build_app(allow_live=False, background=False)


@pytest.fixture()
def client(app):
    return Client(app)


def _csrf(app):
    return app.state.csrf_token


def _run_case(client, app, case="C01", config="baseline"):
    status, headers, _ = client.post(
        "/run", {"case": case, "config": config, "mode": "replay",
                 "csrf": _csrf(app)})
    assert status.startswith("303"), status
    loc = headers["Location"]
    assert loc.startswith("/runs/"), loc
    return loc.split("/runs/")[1]


# ------------------------------------------------------------------ startup

def test_ui_startup_serves_the_home_page(client):
    status, headers, body = client.get("/")
    assert status.startswith("200")
    assert "Run the workflow" in body
    assert 'name="case"' in body and 'name="config"' in body
    assert "replay / demo" in body            # replay is the default mode
    assert "Content-Security-Policy" in headers


def test_the_home_page_is_honest_about_what_is_produced(client):
    _, _, body = client.get("/")
    assert "does not produce a finished, polished video" in body


# ------------------------------------------------- replay execution, no keys

def test_replay_run_executes_without_any_key(client, app, monkeypatch):
    monkeypatch.delenv("SSF_HVE_API_KEY", raising=False)
    run_id = _run_case(client, app, "C01", "baseline")
    status, _, body = client.get(f"/runs/{run_id}")
    assert status.startswith("200")
    assert "SAFE" in body and "Script / narration" in body


def test_case_and_configuration_are_validated(client, app):
    for bad in ({"case": "C99", "config": "final"},
                {"case": "C01", "config": "warp-drive"},
                {"case": "../C01", "config": "final"}):
        bad = dict(bad, mode="replay", csrf=_csrf(app))
        status, _, body = client.post("/run", bad)
        assert status.startswith("400"), (bad, status)


# --------------------------------------------------------- results rendering

def test_run_page_renders_the_full_evidence(client, app):
    run_id = _run_case(client, app, "C09", "final")
    _, _, body = client.get(f"/runs/{run_id}")
    assert "A1 — claim map" in body
    assert "Verification and review cycles" in body
    assert "Workflow steps" in body
    assert "Human gate H1" in body
    assert "UNSAFE" in body                    # C09 final is HOLD-at-bound
    assert "HOLD" in body                      # terminal status shown
    _, _, traj = client.get(f"/runs/{run_id}/trajectory")
    assert "Trajectory" in traj and run_id in traj
    status, headers, raw = client.get(f"/runs/{run_id}/trajectory.jsonl")
    assert status.startswith("200")
    assert headers["Content-Type"].startswith("text/plain")
    assert raw.splitlines()[0].startswith('{"event": "run_start"')


def test_safe_unsafe_hold_badges_render_distinctly():
    from ssf_hve.ui.views import verdict_badge
    assert "SAFE" in verdict_badge("clear")
    assert "UNSAFE" in verdict_badge("asserted")
    assert "HOLD" in verdict_badge("hold") and "human" in verdict_badge("hold")


# ------------------------------------------------------- gates and rendering

def test_gate_status_is_presented_with_the_reason(client, app):
    run_id = _run_case(client, app, "C01", "final")
    _, _, body = client.get(f"/runs/{run_id}")
    assert "NOT APPROVED" in body
    assert "no approval record exists" in body
    _, _, gates_body = client.get(f"/gates?run={run_id}")
    assert "NOT APPROVED" in gates_body


def test_render_refuses_without_h1(client, app):
    run_id = _run_case(client, app, "C01", "final")
    status, _, body = client.post(f"/runs/{run_id}/render",
                                  {"csrf": _csrf(app)})
    assert status.startswith("403")
    assert "H1 is not approved" in body
    assert "production not produced" in body


def test_the_ui_offers_no_gate_approval_control(client, app):
    run_id = _run_case(client, app, "C01", "final")
    for path in (f"/runs/{run_id}", "/gates"):
        _, _, body = client.get(path)
        lowered = body.lower()
        assert 'action="/approve' not in lowered
        assert "type the word approve" not in lowered
    status, _, _ = client.post("/approve", {"csrf": _csrf(app)})
    assert status.startswith("404")


# ------------------------------------------------------ containment and CSRF

def test_download_paths_are_contained(client, app):
    for path in ("/downloads/C01-final-s1-00000000/../../.env",
                 "/downloads/C01-final-s1-00000000/..%2f..%2fpyproject.toml",
                 "/downloads/not-a-run-id/script.txt",
                 "/downloads/C01-final-s1-00000000/.hidden"):
        status, _, _ = client.get(path)
        assert status.startswith(("400", "404")), path


def test_download_of_a_nonexistent_package_explains_h1(client, app):
    status, _, body = client.get("/downloads/C01-final-s1-00000000/script.txt")
    assert status.startswith("404")
    assert "H1" in body


def test_run_id_traversal_is_refused_everywhere(client, app):
    for path in ("/runs/..%2f..%2fetc%2fpasswd",
                 "/runs/../../secrets", "/runs/C01-final-s1-zzzz;rm"):
        status, _, _ = client.get(path)
        assert status.startswith(("400", "404")), path


def test_posts_without_the_csrf_token_are_refused(client, app):
    for data in ({}, {"csrf": "wrong"},
                 {"case": "C01", "config": "final", "mode": "replay"}):
        status, _, body = client.post("/run", dict(data))
        assert status.startswith("403"), data
        assert "CSRF" in body


# --------------------------------------------------------------- no secrets

def test_no_secret_value_ever_reaches_a_page(client, app, monkeypatch):
    fake_key = "fake-api-key-value-for-ui-test-only"  # shaped to trip nothing else
    fake_secret = "gate-secret-fake-test-value"
    monkeypatch.setenv("SSF_HVE_API_KEY", fake_key)
    monkeypatch.setenv("SSF_HVE_GATE_SECRET", fake_secret)
    run_id = _run_case(client, app, "C01", "baseline")
    for path in ("/", "/providers", "/gates", f"/runs/{run_id}", "/runs"):
        _, _, body = client.get(path)
        assert fake_key not in body, path
        assert fake_secret not in body, path
    _, _, body = client.get("/providers")
    assert "configured (value never shown)" in body


def test_the_ui_has_no_key_entry_form(client):
    for path in ("/", "/providers", "/gates"):
        _, _, body = client.get(path)
        assert 'type="password"' not in body
        assert "api_key" not in body.lower().replace("ssf_hve_api_key", "")


# ------------------------------------------------------------- live opt-in

def test_live_mode_requires_the_server_flag(client, app):
    status, _, body = client.post(
        "/run", {"case": "C01", "config": "final", "mode": "live",
                 "csrf": _csrf(app)})
    assert status.startswith("403")
    assert "--allow-live" in body


def test_live_mode_with_flag_but_no_key_fails_closed(monkeypatch):
    monkeypatch.delenv("SSF_HVE_API_KEY", raising=False)
    app = build_app(allow_live=True, background=False)
    client = Client(app)
    status, headers, _ = client.post(
        "/run", {"case": "C01", "config": "final", "mode": "live",
                 "csrf": app.state.csrf_token})
    assert status.startswith("303")
    _, _, body = client.get(headers["Location"])
    assert "failed" in body.lower()
    assert "SSF_HVE_API_KEY" in body


# ------------------------------------------------- structural guarantees

def _ui_sources():
    for p in sorted(UI_DIR.glob("*.py")):
        yield p, p.read_text(encoding="utf-8")


def test_the_ui_uses_no_database():
    forbidden = {"sqlite3", "dbm", "shelve", "sqlalchemy", "psycopg2", "pymysql"}
    for path, source in _ui_sources():
        imports = {n.name.split(".")[0] for node in ast.walk(ast.parse(source))
                   if isinstance(node, ast.Import) for n in node.names}
        imports |= {node.module.split(".")[0]
                    for node in ast.walk(ast.parse(source))
                    if isinstance(node, ast.ImportFrom) and node.module}
        assert not (imports & forbidden), f"{path.name} imports a database module"


def test_the_ui_imports_only_stdlib_and_ssf_hve():
    """Clean-room boundary: nothing from Flask, nothing from any other app."""
    import sys
    stdlib = set(getattr(sys, "stdlib_module_names", ()))
    for path, source in _ui_sources():
        for node in ast.walk(ast.parse(source)):
            names = []
            if isinstance(node, ast.Import):
                names = [n.name for n in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for name in names:
                top = name.split(".")[0]
                assert top == "ssf_hve" or top in stdlib, (
                    f"{path.name} imports {name!r}, which is neither the "
                    "standard library nor ssf_hve")


def test_the_ui_carries_no_foreign_framework_or_asset_references():
    markers = ("flask", "jinja", "bootstrap", "jquery", "cdn.", "cdnjs",
               "googleapis", "unpkg", "<script src=", "http://", "https://")
    allowed = ("http://127.0.0.1", "http://localhost")   # the local listener's own address
    for path, source in _ui_sources():
        low = source.lower()
        for marker in markers:
            if marker in ("http://", "https://"):
                for m in re.finditer(re.escape(marker) + r"[^\s\"')]+", low):
                    assert m.group(0).startswith(allowed), (
                        f"{path.name} references an external URL: {m.group(0)}")
                continue
            assert marker not in low, f"{path.name} contains {marker!r}"


def test_the_ui_does_not_touch_scoring_logic_or_bound_provenance():
    """Importing and exercising the UI must not change what the verifier
    certifies: every provenance-bound file still matches its binding."""
    from ssf_hve.provenance import verify
    report = verify()
    assert not report.failures, report.failures


def test_the_ui_writes_runs_only_to_the_session_directory(client, app):
    published = ROOT / "results" / "runs"
    before = {p.name for p in published.glob("*.json")}
    run_id = _run_case(client, app, "C02", "baseline")
    after = {p.name for p in published.glob("*.json")}
    assert before == after, "a UI run landed in the published results"
    assert (RUNS_DIR / f"{run_id}.json").exists()


def test_the_published_run_pages_render_too(client):
    published = sorted((ROOT / "results" / "runs").glob("C05-final-*.json"))
    assert published
    run_id = published[-1].stem
    status, _, body = client.get(f"/runs/{run_id}")
    assert status.startswith("200")
    assert "SAFE" in body
