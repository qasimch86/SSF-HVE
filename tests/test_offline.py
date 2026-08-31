"""`runs offline` must be a checked property, not a promise in a README.

The evaluation path is claimed to make no network call. That claim is only
worth something if something enforces it, so this walks every module in the
package and fails if any module other than the one live provider can reach the
network at all.

It also states the exceptions plainly rather than letting a reader infer that
nothing anywhere touches a network: `--live` does, and installing the dev
dependency does. Running the evaluation, scoring it and reproducing every
published number does not.
"""
import ast
import pkgutil
from pathlib import Path

import ssf_hve
from ssf_hve.paths import ROOT

# Modules that can open a socket, directly or as a client.
NETWORK_MODULES = {
    "socket", "ssl", "http", "http.client", "urllib.request",
    "urllib.error", "ftplib", "smtplib", "telnetlib", "poplib", "imaplib",
    "asyncio", "requests", "httpx", "aiohttp", "urllib3", "websockets",
    "xmlrpc", "xmlrpc.client",
}
# `urllib.parse` is deliberately NOT here: it is pure string handling with no
# socket path, and the judge UI uses it to parse form bodies. The modules that
# can actually open a connection are urllib.request / urllib.error, which stay
# restricted to the live provider.

# Modules allowed to touch sockets, each with a reason:
#   providers.live — the ONLY module that makes an outbound network call,
#     reached only behind an explicit --live flag.
#   ui.server — the judge UI's local LISTENER (wsgiref on 127.0.0.1), reached
#     only through the explicit `ui` command. It serves; it calls nothing.
#     The rest of ssf_hve.ui is plain WSGI with no socket imports, which this
#     test continues to enforce.
ALLOWED = {"ssf_hve.providers.live", "ssf_hve.ui.server"}


def _package_modules():
    pkg_dir = Path(ssf_hve.__file__).parent
    for info in pkgutil.walk_packages([str(pkg_dir)], prefix="ssf_hve."):
        yield info.name, Path(pkg_dir, *info.name.split(".")[1:]).with_suffix(".py")


def _imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def test_only_the_live_provider_can_reach_the_network():
    offenders = {}
    checked = 0
    for name, path in _package_modules():
        if name in ALLOWED or not path.exists():
            continue
        checked += 1
        hits = sorted(m for m in _imported_modules(path)
                      if m in NETWORK_MODULES or m.split(".")[0] in NETWORK_MODULES)
        if hits:
            offenders[name] = hits
    assert checked >= 10, f"only {checked} modules were scanned; the walk is broken"
    assert not offenders, f"a non-live module imports a network library: {offenders}"


def test_the_ui_server_binds_localhost_only():
    """The UI listener is allowed a socket; it must be loopback-only and it
    must be the only ui module that needs the allowance."""
    path = Path(ssf_hve.__file__).parent / "ui" / "server.py"
    source = path.read_text(encoding="utf-8")
    assert 'HOST = "127.0.0.1"' in source
    assert "0.0.0.0" not in source
    for name, mpath in _package_modules():
        if name.startswith("ssf_hve.ui") and name not in ALLOWED and mpath.exists():
            hits = _imported_modules(mpath) & NETWORK_MODULES
            assert not hits, f"{name} imports {hits}; only ui.server may listen"


def test_the_live_provider_really_is_the_exception():
    """If live.py stops importing urllib, ALLOWED is stale and should shrink."""
    path = Path(ssf_hve.__file__).parent / "providers" / "live.py"
    assert any(m.startswith("urllib") for m in _imported_modules(path)), (
        "ssf_hve.providers.live no longer reaches the network; remove it from "
        "ALLOWED rather than leaving a permission nothing uses")


def test_the_replay_provider_reaches_only_the_filesystem():
    path = Path(ssf_hve.__file__).parent / "providers" / "replay.py"
    imports = _imported_modules(path)
    assert not (imports & NETWORK_MODULES)
    assert "json" in imports and "pathlib" in imports


def test_live_mode_is_never_reached_by_omission():
    """Every caller must state the mode; none can drift into live."""
    import inspect

    from ssf_hve.providers import get_provider

    sig = inspect.signature(get_provider)
    live = sig.parameters["live"]
    assert live.kind is inspect.Parameter.KEYWORD_ONLY, (
        "`live` must be keyword-only so it cannot be passed positionally")
    assert live.default is inspect.Parameter.empty, (
        "`live` must have no default: every caller states the mode explicitly, "
        "which is stronger than defaulting to replay")
    assert get_provider(live=False, model="claude-opus-5").name == "replay"


def test_only_the_cli_can_ask_for_live_and_only_behind_the_flag():
    """`--live` is the single door to the network. Nothing else opens it."""
    asks_for_live = set()
    for name, path in _package_modules():
        if not path.exists():
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call)
                    and getattr(node.func, "id",
                                getattr(node.func, "attr", "")) == "get_provider"):
                continue
            for kw in node.keywords:
                if kw.arg == "live" and not (
                        isinstance(kw.value, ast.Constant) and kw.value.value is False):
                    asks_for_live.add(name)
    # Two doors, both explicit and user-facing: the CLI behind --live, and the
    # judge UI behind the server's --allow-live flag plus a per-run choice.
    assert asks_for_live <= {"ssf_hve.cli", "ssf_hve.ui.app"}, (
        f"an unexpected module can request live mode: "
        f"{sorted(asks_for_live - {'ssf_hve.cli', 'ssf_hve.ui.app'})}")

    # ...in the CLI it is reached only from the parsed --live flag.
    import inspect

    from ssf_hve import cli

    source = inspect.getsource(cli._provider)
    before_true = source.split("live=True")[0]
    assert 'args, "live"' in before_true or "args.live" in before_true, (
        "the CLI reaches live mode without first reading the --live flag")

    # ...and in the UI it is refused before execution unless the server was
    # started with --allow-live; tests/test_ui.py exercises the refusal.
    ui_app = Path(ssf_hve.__file__).parent / "ui" / "app.py"
    ui_source = ui_app.read_text(encoding="utf-8")
    guard = ui_source.index('mode == "live" and not state.allow_live')
    use = ui_source.index('live=(job.mode == "live")')
    assert guard < use, "the UI reaches live mode before checking --allow-live"


def test_the_documented_offline_claim_names_its_exceptions():
    """A claim of 'offline' with no exceptions stated would be the overclaim."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "tests/test_offline.py" in readme, (
        "README should point at the test that enforces the offline claim")
    assert "--live" in readme and "pytest" in readme, (
        "README should name the two cases that do use the network")
