"""Untrusted input that reaches a filesystem path or a credential header.

Two places take a value from outside the program and use it somewhere that
matters. Neither validated it.

* A **run identifier** arrives on the command line and is joined onto a
  directory twice: once to read a run record, once to name the trajectory files
  that get written. `--run ../../x` was a read outside the results tree and a
  write outside the trajectory tree.
* The **live endpoint** arrives from an environment variable and receives the
  API key in a request header. Any host, any scheme.

Both now refuse rather than sanitise. Silently repairing bad input hides the
attempt; the caller is told no.
"""
import pytest

from ssf_hve.paths import (RUN_ID_RE, InvalidRunId, run_record_path,
                           trajectory_path, validate_run_id)
from ssf_hve.providers.live import (DEFAULT_ENDPOINT, ENDPOINT_ENV,
                                    ENDPOINT_OPT_IN_ENV, UnsafeEndpoint,
                                    resolve_endpoint)

# ------------------------------------------------------------------ run ids

GOOD = ["C09-final-s1-2ba6b49f", "C01-baseline-s3-00829745",
        "C03-iter-1-s1-abcdef01", "C09-rm-bound-ok-s1-d65046b4",
        "C10-rm-model-checks-s1-0123abcd"]

TRAVERSAL = [
    "../../etc/passwd",
    "../C09-final-s1-2ba6b49f",
    "C09-final-s1-2ba6b49f/../../x",
    "/etc/passwd",
    "C:\\Windows\\System32\\config",
    "..",
    ".",
    "C09-final-s1-2ba6b49f/..",
    "subdir/C09-final-s1-2ba6b49f",
    "C09-final-s1-2ba6b49f\x00.json",
    "~/secrets",
    "C09-final-s1-2ba6b49f%2f..%2f..",
]

MALFORMED = ["", "C09", "C09-final", "C9-final-s1-2ba6b49f", "x09-final-s1-2ba6b49f",
             "C09-final-s1-ZZZZZZZZ", "C09-final-sX-2ba6b49f",
             "C09-final-s1-2ba6b49f-extra", "C09-final-s1-2ba6b49", " C09-final-s1-2ba6b49f"]


@pytest.mark.parametrize("run_id", GOOD)
def test_real_run_identifiers_are_accepted(run_id):
    assert validate_run_id(run_id) == run_id


@pytest.mark.parametrize("run_id", TRAVERSAL)
def test_path_traversal_is_refused(run_id):
    with pytest.raises(InvalidRunId):
        validate_run_id(run_id)
    with pytest.raises(InvalidRunId):
        run_record_path(run_id)
    with pytest.raises(InvalidRunId):
        trajectory_path(run_id, ".md")


@pytest.mark.parametrize("run_id", MALFORMED)
def test_malformed_identifiers_are_refused(run_id):
    with pytest.raises(InvalidRunId):
        validate_run_id(run_id)


def test_refusal_never_returns_a_sanitised_value():
    """A repaired identifier would silently read a different run."""
    with pytest.raises(InvalidRunId):
        validate_run_id("../C09-final-s1-2ba6b49f")


def test_every_shipped_run_record_and_trajectory_passes():
    """The validator must not reject the project's own identifiers."""
    from ssf_hve.paths import ROOT
    runs = sorted((ROOT / "results" / "runs").glob("*.json"))
    assert runs, "no run records found"
    bad = [p.stem for p in runs if not RUN_ID_RE.match(p.stem)]
    assert not bad, f"the validator rejects shipped run records: {bad[:5]}"
    traj = [p for p in (ROOT / "trajectories" / "solution").glob("*")
            if p.suffix in (".jsonl", ".md")]
    bad = [p.stem for p in traj if not RUN_ID_RE.match(p.stem)]
    assert not bad, f"the validator rejects shipped trajectories: {bad[:5]}"


def test_trajectory_export_refuses_a_traversing_identifier():
    from ssf_hve.trajectory.export import export_run
    with pytest.raises(InvalidRunId):
        export_run("../../../tmp/escape")


def test_render_refuses_a_traversing_identifier():
    from ssf_hve.rendering.render import render_run
    result = render_run("../../tmp/escape")
    assert not result.ok
    assert any("not a run identifier" in m for m in result.messages)


# ---------------------------------------------------------------- endpoint

def test_unset_endpoint_uses_the_default():
    assert resolve_endpoint({}) == DEFAULT_ENDPOINT
    assert resolve_endpoint({ENDPOINT_ENV: ""}) == DEFAULT_ENDPOINT
    assert resolve_endpoint({ENDPOINT_ENV: "   "}) == DEFAULT_ENDPOINT


def test_the_explicit_default_needs_no_opt_in():
    assert resolve_endpoint({ENDPOINT_ENV: DEFAULT_ENDPOINT}) == DEFAULT_ENDPOINT


@pytest.mark.parametrize("url", [
    "http://api.anthropic.com/v1/messages",
    "http://localhost:8080/v1/messages",
    "ftp://example.test/x",
    "file:///etc/passwd",
    "//example.test/x",
    "example.test/x",
])
def test_a_non_https_endpoint_is_refused_even_with_opt_in(url):
    """Opting in to a custom host is not opting out of transport security."""
    with pytest.raises(UnsafeEndpoint):
        resolve_endpoint({ENDPOINT_ENV: url, ENDPOINT_OPT_IN_ENV: "1"})


def test_a_custom_https_endpoint_requires_explicit_opt_in():
    env = {ENDPOINT_ENV: "https://someone-elses-host.test/v1"}
    with pytest.raises(UnsafeEndpoint):
        resolve_endpoint(env)
    env[ENDPOINT_OPT_IN_ENV] = "1"
    assert resolve_endpoint(env) == "https://someone-elses-host.test/v1"


@pytest.mark.parametrize("flag", ["0", "", "no", "false", "maybe", "TRUE-ish"])
def test_a_non_affirmative_opt_in_does_not_count(flag):
    with pytest.raises(UnsafeEndpoint):
        resolve_endpoint({ENDPOINT_ENV: "https://elsewhere.test/v1",
                          ENDPOINT_OPT_IN_ENV: flag})


def test_an_https_url_without_a_host_is_refused():
    with pytest.raises(UnsafeEndpoint):
        resolve_endpoint({ENDPOINT_ENV: "https:///v1",
                          ENDPOINT_OPT_IN_ENV: "1"})


def test_the_refusal_message_never_contains_a_key():
    """Error text is printed and logged; it must not carry the credential."""
    # Assembled at runtime so this file does not itself contain something the
    # repository secret scanner must flag.
    fake_key = "sk" + "-" + "should-never-appear-in-output"
    try:
        resolve_endpoint({ENDPOINT_ENV: "http://evil.test/v1",
                          "SSF_HVE_API_KEY": fake_key})
    except UnsafeEndpoint as exc:
        assert fake_key not in str(exc)
    else:
        pytest.fail("expected a refusal")
