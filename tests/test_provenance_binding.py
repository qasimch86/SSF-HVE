"""The provenance binding must FAIL when any active input changes.

Re-verification finding NEW-RA-01, reproduced before fixing: an active C05
detector was edited in a temporary copy; `verify-provenance` still exited 0
and printed "all checked relationships hold" while `score` changed the
baseline from 0/30 to 3/30. A verifier that certifies a score-changing
mutation is worse than no verifier, because it converts an edit into a claim.

These tests perform that exact attack — and its siblings — against a
temporary copy of the repository, and assert the verification now fails,
loudly, naming the changed file. The canonical repository is never touched.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

COPIED = ("src", "evaluation", "prompts", "fixtures", "results", "pyproject.toml")


@pytest.fixture(scope="module")
def repo_copy(tmp_path_factory):
    dst = tmp_path_factory.mktemp("ssf-hve-mutation")
    for name in COPIED:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dst / name,
                            ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst / name)
    return dst


def _verify(copy: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(copy / "src")
    env.pop("SSF_HVE_RESULTS_DIR", None)   # verify the COPY's published results
    return subprocess.run([sys.executable, "-m", "ssf_hve", "verify-provenance"],
                          cwd=copy, env=env, capture_output=True, text=True,
                          timeout=300)


@pytest.fixture()
def clean_copy(repo_copy):
    """Verify green before each mutation, and restore files afterwards."""
    p = _verify(repo_copy)
    assert p.returncode == 0, f"copy does not verify before mutation:\n{p.stdout[-2000:]}"
    saved: dict[Path, bytes] = {}

    def mutate(rel: str, transform):
        path = repo_copy / rel
        saved[path] = path.read_bytes() if path.exists() else None
        transform(path)
        return path

    yield repo_copy, mutate
    for path, blob in saved.items():
        if blob is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(blob)


@pytest.mark.slow
def test_the_audit_probe_editing_active_c05_now_fails_verification(clean_copy):
    """THE probe from the re-verification, verbatim in spirit: change an
    active C05 detector so scores move, and demand verification notices."""
    copy, mutate = clean_copy

    def swap_detector(path: Path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["planted_defects"][0]["detector"]["patterns"] = ["zz-impossible-phrase-zz"]
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    mutate("evaluation/cases/C05.json", swap_detector)
    p = _verify(copy)
    assert p.returncode != 0, "a score-changing case mutation still verifies"
    assert "evaluation/cases/C05.json" in p.stdout
    assert "MISMATCH" in p.stdout or "bound file changed" in p.stdout


@pytest.mark.slow
def test_editing_the_scorer_fails_verification(clean_copy):
    copy, mutate = clean_copy
    mutate("src/ssf_hve/scoring/scorer.py",
           lambda p: p.write_bytes(p.read_bytes() + b"\n# tampered\n"))
    p = _verify(copy)
    assert p.returncode != 0
    assert "scoring/scorer.py" in p.stdout


@pytest.mark.slow
def test_editing_the_normaliser_fails_verification(clean_copy):
    copy, mutate = clean_copy
    mutate("src/ssf_hve/scoring/normalise.py",
           lambda p: p.write_bytes(p.read_bytes() + b"\n# tampered\n"))
    assert _verify(copy).returncode != 0


@pytest.mark.slow
def test_editing_a_prompt_template_fails_verification(clean_copy):
    copy, mutate = clean_copy
    mutate("prompts/a3_verifier.md",
           lambda p: p.write_bytes(p.read_bytes() + b"\nBe lenient.\n"))
    p = _verify(copy)
    assert p.returncode != 0
    assert "prompts/a3_verifier.md" in p.stdout


@pytest.mark.slow
def test_an_unbound_extra_fixture_fails_verification(clean_copy):
    copy, mutate = clean_copy

    def plant(path: Path):
        path.write_text(json.dumps({"schema": "ssf-hve/replay-fixture/1",
                                    "key": "0" * 64, "role": "a2", "model": "m",
                                    "provenance": "handcrafted",
                                    "captured_utc": "2026-08-30T00:00:00Z",
                                    "rendered_prompt": "x",
                                    "response_text": "y"}), encoding="utf-8")

    mutate("fixtures/replay/" + "0" * 64 + ".json", plant)
    p = _verify(copy)
    assert p.returncode != 0
    assert "not bound" in p.stdout


@pytest.mark.slow
def test_editing_published_results_fails_verification(clean_copy):
    copy, mutate = clean_copy

    def inflate(path: Path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["configs"]["final"]["unsafe_count"] = 0
        doc["configs"]["final"]["unsafe_output_rate"] = 0.0
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    mutate("results/results.json", inflate)
    p = _verify(copy)
    assert p.returncode != 0
    assert "results.json" in p.stdout


@pytest.mark.slow
def test_editing_the_binding_file_itself_fails_its_self_hash(clean_copy):
    copy, mutate = clean_copy

    def relabel(path: Path):
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["payload"]["case_set_id"] = "CS-99-fake"
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

    mutate("evaluation/provenance_binding.json", relabel)
    p = _verify(copy)
    assert p.returncode != 0
    assert "self-hash" in p.stdout


def test_the_binding_exists_and_covers_the_active_surfaces():
    doc = json.loads((ROOT / "evaluation" / "provenance_binding.json")
                     .read_text(encoding="utf-8"))
    bound = doc["payload"]["bound_files"]
    for must in ("evaluation/cases/C05.json",
                 "src/ssf_hve/scoring/scorer.py",
                 "src/ssf_hve/scoring/normalise.py",
                 "src/ssf_hve/cases.py",
                 "src/ssf_hve/config.py",
                 "src/ssf_hve/checks/deterministic.py"):
        assert must in bound, f"{must} is not provenance-bound"
    assert sum(1 for k in bound if k.startswith("fixtures/replay/")) == len(
        list((ROOT / "fixtures" / "replay").glob("*.json")))
    assert sum(1 for k in bound if k.startswith("results/runs/")) == len(
        list((ROOT / "results" / "runs").glob("*.json")))
    assert any(k.startswith("prompts/") for k in bound)
    assert doc["payload"]["results_content_sha256"]
