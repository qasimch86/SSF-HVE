"""Gate approvals must be unforgeable AND untransferable.

The original gates enforced one property: an approval could only be *created*
through an interactive terminal. A first fix added signatures, so a record
could not be forged by writing a file. Independent re-verification (AUD-002)
then showed the remaining gap: H1 bound only the narration text, so a valid
record copied beside a different run with identical narration was accepted, a
correctly signed record from 2000 stayed valid forever, and the (unsigned)
algorithm label could be edited freely.

These tests are the adversary for all three properties. Each one constructs
the kind of record an attacker or a careless script would produce, and asserts
that the gate refuses it, with binding recomputed from the run record on disk.

Every secret here is a throwaway string created inside the test process. The
owner secret is never in the repository, never in a fixture, and never in a
test. No real approval is created: every record written lands in the
throwaway results directory that `tests/conftest.py` installs.
"""
import io
import json
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ssf_hve import gates
from ssf_hve.paths import GATES_DIR, RUNS_DIR
from ssf_hve.schemas import GateRecord

SECRET = "test-only-secret-A"
OTHER_SECRET = "test-only-secret-B"
SCRIPT = "The exact script version a person read before approving it."

RUN_A = "C01-final-s1-aaaa1111"
RUN_B = "C01-final-s2-bbbb2222"    # different run, IDENTICAL narration


class _FakeTTY(io.StringIO):
    def isatty(self):
        return True


def _write_run(run_id: str, narration: str = SCRIPT, sample: int = 1) -> Path:
    """A minimal but schema-complete run record in the throwaway results dir."""
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run = {
        "schema": "ssf-hve/run/1",
        "meta": {"run_id": run_id, "case_id": run_id.split("-")[0],
                 "config_id": "final", "condition": "advanced",
                 "provider": "replay", "model": "test-model", "mode": "replay",
                 "started_utc": "2026-08-30T00:00:00Z",
                 "finished_utc": "2026-08-30T00:00:01Z", "model_calls": 1,
                 "input_tokens": None, "output_tokens": None,
                 "estimated_cost_usd": None, "wall_clock_s": 1.0,
                 "correction_cycles": 0, "terminal_status": "ACCEPT",
                 "error": ""},
        "config": {"config_id": "final", "sample": sample},
        "steps": [], "cycles": [],
        "claim_map": None,
        "final_script": {"case_id": run_id.split("-")[0], "audience": "a",
                         "target_duration_s": 60,
                         "beats": [{"beat": "b", "narration": narration,
                                    "on_screen": "", "claim_refs": []}]},
        "final_narration": narration,
        "h1_gate": {"gate": "H1", "state": "BLOCKED_AWAITING_HUMAN"},
        "unresolved_findings": [],
    }
    p = RUNS_DIR / f"{run_id}.json"
    p.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    return p


@pytest.fixture(autouse=True)
def _secret_env(monkeypatch):
    monkeypatch.setenv(gates.SECRET_ENV, SECRET)
    yield
    from ssf_hve.paths import TRAJ_SOLUTION_DIR
    for p in GATES_DIR.glob("*.json"):
        p.unlink(missing_ok=True)
    for p in RUNS_DIR.glob("C01-final-*.json"):
        p.unlink(missing_ok=True)
    for p in TRAJ_SOLUTION_DIR.glob("C01-final-*"):
        p.unlink(missing_ok=True)


def _approve(run_id: str = RUN_A, **kw):
    return gates.approve_h1(run_id, approver="Test Person",
                            stdin=_FakeTTY("APPROVE\n"), stdout=io.StringIO(), **kw)


def _rewrite(rec, path: Path | None = None, **changes):
    """Write a tampered record to the same path the gate reads from."""
    data = rec.as_dict()
    data.update(changes)
    path = path or gates.h1_record_path(rec.binding["run_id"])
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return path


def _resign(rec, **changes):
    """A tampered record RE-SIGNED with the real secret — the strongest forgery
    available to an attacker who somehow ran our own signing code but must
    still get past the semantic validation."""
    tampered = replace(rec, **changes, signature="")
    return replace(tampered, signature=gates.sign(tampered, SECRET.encode()))


# --------------------------------------------------------------- happy path

def test_a_real_approval_verifies_and_binds():
    _write_run(RUN_A)
    rec = _approve()
    assert rec.signature and rec.signature_algorithm == "HMAC-SHA-256"
    assert rec.gate_schema_version == gates.GATE_SCHEMA_VERSION
    assert rec.expires_utc > rec.approved_utc
    for key in gates.REQUIRED_H1_BINDING:
        assert rec.binding.get(key) not in (None, ""), f"binding lacks {key}"
    assert gates.verify(rec)
    got, why = gates.h1_status(RUN_A)
    assert got is not None and why == ""
    assert got.approver == "Test Person"


def test_the_signature_is_not_the_secret():
    _write_run(RUN_A)
    rec = _approve()
    blob = gates.h1_record_path(RUN_A).read_text(encoding="utf-8")
    assert SECRET not in blob
    assert gates.SECRET_ENV not in blob


# ------------------------------------------------- forgeries (file writing)

def test_an_unsigned_record_is_not_an_approval():
    _write_run(RUN_A)
    rec = _approve()
    _rewrite(rec, signature="", signature_algorithm="")
    got, why = gates.h1_status(RUN_A)
    assert got is None and "algorithm" in why


def test_a_handwritten_record_is_not_an_approval():
    """No prior real approval at all: just a plausible file dropped in place."""
    p = _write_run(RUN_A)
    run = json.loads(p.read_text(encoding="utf-8"))
    binding = gates.h1_binding(run, p)
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    gates.h1_record_path(RUN_A).write_text(json.dumps({
        "gate": "H1", "artifact_sha256": gates.artifact_sha256(SCRIPT),
        "artifact_kind": "script", "approver": "Not The Owner",
        "approved_utc": "2026-08-30T00:00:00Z",
        "expires_utc": "2036-08-30T00:00:00Z", "note": "", "binding": binding,
        "purpose": gates.H1_PURPOSE,
        "gate_schema_version": gates.GATE_SCHEMA_VERSION,
        "signature": "0" * 64,
        "signature_algorithm": "HMAC-SHA-256"}), encoding="utf-8")
    got, why = gates.h1_status(RUN_A)
    assert got is None and "does not verify" in why


@pytest.mark.parametrize("field,value", [
    ("approver", "Someone Else"),
    ("approved_utc", "2026-01-01T00:00:00Z"),
    ("expires_utc", "2036-01-01T00:00:00Z"),
    ("artifact_kind", "something else entirely"),
    ("note", "approved for a different purpose"),
    ("purpose", "some-other-purpose"),
])
def test_editing_any_signed_field_breaks_the_signature(field, value):
    _write_run(RUN_A)
    rec = _approve()
    _rewrite(rec, **{field: value})
    got, why = gates.h1_status(RUN_A)
    assert got is None, f"{field} is not covered by the signature"


def test_editing_the_binding_breaks_the_signature():
    _write_run(RUN_A)
    rec = _approve()
    tampered = dict(rec.binding, run_record_sha256="b" * 64)
    _rewrite(rec, binding=tampered)
    got, _ = gates.h1_status(RUN_A)
    assert got is None


def test_a_signature_from_a_different_secret_is_refused():
    _write_run(RUN_A)
    rec = _approve()
    forged = gates.sign(rec, OTHER_SECRET.encode("utf-8"))
    _rewrite(rec, signature=forged)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "does not verify" in why


def test_an_h1_signature_does_not_open_h2():
    """Domain separation: the gate name is inside the signed payload."""
    _write_run(RUN_A)
    rec = _approve()
    data = rec.as_dict()
    data["gate"] = "H2"
    sha = rec.artifact_sha256
    (GATES_DIR / f"H2_{sha[:16]}.json").write_text(
        json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    assert gates.approval_for("H2", SCRIPT) is None


def test_a_malformed_record_is_refused_not_crashed():
    _write_run(RUN_A)
    gates.h1_record_path(RUN_A).write_text("{not json", encoding="utf-8")
    got, why = gates.h1_status(RUN_A)
    assert got is None and "malformed" in why


# ------------------------------------- transfer, staleness, unknown labels
# The AUD-002 bypasses. Each of these was ACCEPTED before this remediation.

def test_a_copied_record_does_not_approve_another_run_with_identical_narration():
    """The central AUD-002 bypass: same narration, different run."""
    _write_run(RUN_A)
    _write_run(RUN_B, narration=SCRIPT, sample=2)      # byte-identical script
    rec = _approve(RUN_A)
    # the attacker copies the valid record file beside the other run
    src = gates.h1_record_path(RUN_A).read_text(encoding="utf-8")
    gates.h1_record_path(RUN_B).write_text(src, encoding="utf-8")
    got, why = gates.h1_status(RUN_B)
    assert got is None, "a copied H1 record approved a different run"
    assert "copied between runs" in why or "binds run" in why
    # and the original is still valid where it belongs
    assert gates.h1_status(RUN_A)[0] is not None


def test_a_modified_run_record_invalidates_the_approval():
    p = _write_run(RUN_A)
    _approve(RUN_A)
    assert gates.h1_status(RUN_A)[0] is not None
    run = json.loads(p.read_text(encoding="utf-8"))
    run["unresolved_findings"] = [{"id": "F99", "severity": "MAJOR"}]
    p.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    got, why = gates.h1_status(RUN_A)
    assert got is None and "no longer matches" in why


def test_a_modified_narration_invalidates_the_approval():
    p = _write_run(RUN_A)
    _approve(RUN_A)
    run = json.loads(p.read_text(encoding="utf-8"))
    run["final_narration"] = SCRIPT + " With one more sentence."
    run["final_script"]["beats"][0]["narration"] = run["final_narration"]
    p.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    got, _ = gates.h1_status(RUN_A)
    assert got is None


# ---------------------------------------------- exported artifacts (FV-001)
# The final verification's failing probe: the exported JSONL was modified
# after approval and the record was still accepted, because only a hash
# recomputed from the run record was checked. Verification now re-reads the
# actual exported files.

def _export(run_id: str):
    from ssf_hve.trajectory.export import export_run
    return export_run(run_id)


def test_the_final_verification_probe_a_modified_exported_jsonl_is_refused():
    _write_run(RUN_A)
    _approve(RUN_A)                                 # approved with no export
    paths = _export(RUN_A)                          # matching export appears
    assert gates.h1_status(RUN_A)[0] is not None, "a matching export must not break approval"
    jsonl = next(p for p in paths if p.suffix == ".jsonl")
    jsonl.write_text(jsonl.read_text(encoding="utf-8")
                     .replace('"terminal_status": "ACCEPT"',
                              '"terminal_status": "LOOKS_FINE"'),
                     encoding="utf-8")
    got, why = gates.h1_status(RUN_A)
    assert got is None, "a modified exported trajectory was accepted (FV-001)"
    assert "exported trajectory" in why and "no longer matches" in why


def test_a_modified_exported_markdown_is_refused_too():
    _write_run(RUN_A)
    _approve(RUN_A)
    paths = _export(RUN_A)
    md = next(p for p in paths if p.suffix == ".md")
    md.write_text(md.read_text(encoding="utf-8") + "\n\nAll findings resolved.\n",
                  encoding="utf-8")
    got, why = gates.h1_status(RUN_A)
    assert got is None and "exported trajectory" in why


def test_approval_is_refused_over_an_already_divergent_export():
    _write_run(RUN_A)
    paths = _export(RUN_A)
    jsonl = next(p for p in paths if p.suffix == ".jsonl")
    jsonl.write_text(jsonl.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(gates.GateNotApproved, match="divergent"):
        _approve(RUN_A)


def test_an_export_verified_at_approval_must_not_vanish():
    _write_run(RUN_A)
    _export(RUN_A)
    rec = _approve(RUN_A)                           # bound state: verified-match
    assert rec.binding["exported_trajectory"] == "verified-match"
    from ssf_hve.paths import TRAJ_SOLUTION_DIR
    for p in TRAJ_SOLUTION_DIR.glob(f"{RUN_A}*"):
        p.unlink()
    got, why = gates.h1_status(RUN_A)
    assert got is None and "missing" in why


def test_a_matching_export_appearing_after_approval_is_fine():
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    assert rec.binding["exported_trajectory"] == "absent"
    _export(RUN_A)
    assert gates.h1_status(RUN_A)[0] is not None


def test_the_binding_carries_both_canonical_trajectory_hashes():
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    from ssf_hve.trajectory.export import trajectory_md_sha256, trajectory_sha256
    run = json.loads((RUNS_DIR / f"{RUN_A}.json").read_text(encoding="utf-8"))
    assert rec.binding["trajectory_sha256"] == trajectory_sha256(run)
    assert rec.binding["trajectory_md_sha256"] == trajectory_md_sha256(run)


def test_a_stale_approval_is_refused_by_the_freshness_policy():
    _write_run(RUN_A)
    rec = _approve(RUN_A, valid_days=30)
    later = datetime.now(timezone.utc) + timedelta(days=31)
    got, why = gates.h1_status(RUN_A, now=later)
    assert got is None and "expired" in why
    # ...and inside the window it is still valid
    assert gates.h1_status(RUN_A, now=datetime.now(timezone.utc))[0] is not None


def test_a_correctly_signed_year_2000_record_is_refused():
    """Before this remediation a valid record from 2000 was accepted."""
    p = _write_run(RUN_A)
    rec = _approve(RUN_A)
    ancient = _resign(rec, approved_utc="2000-01-01T00:00:00Z",
                      expires_utc="2000-01-31T00:00:00Z")
    _rewrite(ancient)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "expired" in why


def test_a_record_with_no_expiry_is_refused():
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    noexp = _resign(rec, expires_utc="")
    _rewrite(noexp)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "timestamps" in why


def test_an_unknown_signature_algorithm_fails_closed_even_when_resigned():
    """The label is signed AND validated: an unknown algorithm is refused
    before any cryptography, even if its HMAC-SHA-256 signature would pass."""
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    exotic = _resign(rec, signature_algorithm="HMAC-SHAKE-9000")
    _rewrite(exotic)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "algorithm" in why


def test_an_unknown_gate_schema_version_fails_closed_even_when_resigned():
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    future = _resign(rec, gate_schema_version="ssf-hve/gate-record/v99")
    _rewrite(future)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "schema" in why


def test_a_record_missing_binding_data_fails_closed_even_when_resigned():
    _write_run(RUN_A)
    rec = _approve(RUN_A)
    stripped = dict(rec.binding)
    del stripped["trajectory_sha256"]
    partial = _resign(rec, binding=stripped)
    _rewrite(partial)
    got, why = gates.h1_status(RUN_A)
    assert got is None and "missing binding" in why


def test_approval_for_refuses_to_look_up_h1_by_text():
    """Narration-keyed H1 lookup is the transfer bug; the API refuses it."""
    with pytest.raises(ValueError):
        gates.approval_for("H1", SCRIPT)


def test_record_approval_refuses_an_h1_without_binding():
    with pytest.raises(gates.GateNotApproved):
        gates.record_approval("H1", SCRIPT, "script", approver="Test Person",
                              stdin=_FakeTTY("APPROVE\n"), stdout=io.StringIO())


# --------------------------------------------------------------- fail closed

def test_verification_fails_closed_when_no_secret_is_configured(monkeypatch):
    """A valid approval plus a missing key is NOT approval. That is the point."""
    _write_run(RUN_A)
    rec = _approve()
    assert gates.h1_status(RUN_A)[0] is not None
    monkeypatch.delenv(gates.SECRET_ENV, raising=False)
    assert gates.verify(rec) is False
    got, why = gates.h1_status(RUN_A)
    assert got is None and gates.SECRET_ENV in why


def test_an_empty_secret_is_the_same_as_no_secret(monkeypatch):
    _write_run(RUN_A)
    monkeypatch.setenv(gates.SECRET_ENV, "   ")
    with pytest.raises(gates.GateSecretMissing):
        _approve()


def test_approval_refuses_before_prompting_when_the_secret_is_missing(monkeypatch):
    """The person must not type APPROVE into something that cannot record it."""
    _write_run(RUN_A)
    monkeypatch.delenv(gates.SECRET_ENV, raising=False)
    out = io.StringIO()
    with pytest.raises(gates.GateSecretMissing):
        gates.approve_h1(RUN_A, approver="Test Person",
                         stdin=_FakeTTY("APPROVE\n"), stdout=out)
    assert out.getvalue() == "", "the prompt was shown before the secret was checked"


# --------------------------------------------------------------- structural

def test_comparison_is_constant_time():
    """A timing-variable compare on a signature is a real attack surface."""
    import ast
    import inspect

    source = inspect.getsource(gates)
    tree = ast.parse(source)
    verify_fn = next(n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "verify")
    calls = {n.func.attr for n in ast.walk(verify_fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "compare_digest" in calls, "verify() must use hmac.compare_digest"
    assert "rec.signature ==" not in source


def test_the_secret_is_never_written_to_disk_by_this_module():
    """No path in gates.py persists the key, only signatures derived from it."""
    import inspect

    src = inspect.getsource(gates)
    for line in src.splitlines():
        if "json.dump" in line:
            assert "secret" not in line.lower()


def test_all_fields_except_the_signature_are_signed():
    """A field added to GateRecord but not to SIGNED_FIELDS would be unsigned.

    AUD-002 found exactly this: `signature_algorithm` existed on the record
    but was excluded from the signed payload, so the label could be edited
    freely. The rule is now: everything except the signature itself is signed.
    """
    _write_run(RUN_A)
    rec = _approve()
    covered = set(gates.SIGNED_FIELDS)
    present = set(rec.as_dict()) - {"signature"}
    assert present == covered, (
        f"unsigned field(s) in the gate record: {sorted(present - covered)}")
    assert "signature_algorithm" in covered
    assert "gate_schema_version" in covered
    assert "expires_utc" in covered
