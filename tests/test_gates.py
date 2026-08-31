"""Human-only gates. No agent status can open one, and H2 has one route only."""
import io

import pytest

from ssf_hve import gates

SCRIPT = "A script version that a person would have to read before approving it."

# A throwaway value that exists only inside this test process. The real owner
# secret is never in the repository, never in a fixture and never in a test.
TEST_SECRET = "test-only-secret-not-the-owner-secret"


@pytest.fixture(autouse=True)
def _test_gate_secret(monkeypatch):
    monkeypatch.setenv(gates.SECRET_ENV, TEST_SECRET)
    yield


class _FakeTTY(io.StringIO):
    def isatty(self):
        return True


class _NotATTY(io.StringIO):
    def isatty(self):
        return False


def test_absence_of_approval_blocks():
    got, why = gates.h1_status("C01-final-s1-00000000")
    assert got is None and "no approval record" in why


def test_h2_absence_blocks():
    with pytest.raises(gates.GateNotApproved):
        gates.require("H2", "an artifact nobody approved " + SCRIPT)


def test_non_interactive_approval_is_refused():
    with pytest.raises(gates.NotAHuman):
        gates.record_approval("H2", SCRIPT, "package", approver="a-script",
                              stdin=_NotATTY("APPROVE\n"), stdout=io.StringIO())


def test_wrong_word_is_not_approval():
    with pytest.raises(gates.GateNotApproved):
        gates.record_approval("H2", SCRIPT, "package", approver="person",
                              stdin=_FakeTTY("yes\n"), stdout=io.StringIO())


def test_approve_h1_refuses_a_missing_run():
    with pytest.raises(gates.GateNotApproved):
        gates.approve_h1("C01-final-s1-00000000", approver="Person",
                         stdin=_FakeTTY("APPROVE\n"), stdout=io.StringIO())


def test_runner_cannot_reach_record_approval():
    """Structural check: the workflow has no path to writing a gate record."""
    import ast
    import inspect

    import ssf_hve.runner as runner
    tree = ast.parse(inspect.getsource(runner))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    # The runner may ASK whether a gate is approved. It may not create an
    # approval, and it may not demand one and treat the exception as a branch.
    assert "record_approval" not in called, (
        "the runner can write a gate approval; the gate is then decorative")
    assert "approve_h1" not in called, (
        "the runner can write a gate approval; the gate is then decorative")
    assert "require" not in called, (
        "the runner calls gates.require; gate state belongs to the caller, "
        "not to the workflow being gated")
    assert "h1_status" in called, (
        "the runner no longer reports H1 state into the run record")


def test_the_cli_has_no_legacy_narration_h2_route():
    """AUD-002: `approve --gate H2` bound H2 to narration text. Removed —
    the ONLY H2 route is `approve-submission`, which binds the package."""
    from ssf_hve.cli import build_parser

    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["approve", "--run", "C01-final-s1-00000000",
                           "--gate", "H2", "--approver", "X"])
    # and `approve` itself parses without any gate choice
    args = parser.parse_args(["approve", "--run", "C01-final-s1-00000000",
                              "--approver", "X"])
    assert not hasattr(args, "gate")


def test_gate_record_schema_is_validated():
    from ssf_hve.schemas import GateRecord, SchemaError
    with pytest.raises(SchemaError):
        GateRecord.parse({"gate": "H3", "artifact_sha256": "x", "artifact_kind": "k",
                          "approver": "p", "approved_utc": "t", "note": ""})
