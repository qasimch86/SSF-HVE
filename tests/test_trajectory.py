"""Trajectory export: secrets are redacted, failures are not."""
from ssf_hve.trajectory.export import redact


# Built at runtime rather than written as a literal, so that the repository-wide
# secret scanner in test_secrets.py does not have to special-case this file.
FAKE_KEY = "sk-" + ("abcd1234efgh5678ijkl")
FAKE_KEY_2 = "sk-" + ("zzzz1111yyyywwww2222")


def test_api_keys_are_redacted():
    text = f"header x-api-key: {FAKE_KEY} and SSF_HVE_API_KEY={FAKE_KEY_2}"
    out = redact(text)
    assert FAKE_KEY not in out
    assert FAKE_KEY_2 not in out
    assert "REDACTED" in out


def test_authorization_header_is_redacted():
    assert "hunter2" not in redact("Authorization: Bearer hunter2secretvalue")


def test_findings_and_failures_survive_redaction():
    text = ("F01 BLOCKER: the script asserts approval. Correction cycle 2 did not "
            "resolve it; terminal status HOLD.")
    assert redact(text) == text


def test_exported_trajectory_keeps_unresolved_findings():
    import glob
    import json
    from ssf_hve.paths import RUNS_DIR
    holds = []
    for p in glob.glob(str(RUNS_DIR / "*.json")):
        run = json.loads(open(p, encoding="utf-8").read())
        if run["meta"]["terminal_status"] == "HOLD":
            holds.append(run)
    if not holds:
        return  # nothing held in this run set
    assert any(r["unresolved_findings"] for r in holds), \
        "a HOLD must carry the findings that were not resolved"
