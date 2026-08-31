"""Prompt-hash replay: invalidation, provenance, and no-network guarantees."""
import json

import pytest

from ssf_hve.providers.replay import ReplayProvider
from ssf_hve.replay.store import (Fixture, FixtureStore, MissingFixture,
                                  prompt_hash)


@pytest.fixture()
def store(tmp_path):
    return FixtureStore(tmp_path)


def test_hash_changes_with_prompt(store):
    a = prompt_hash("a1", "m1", "prompt one")
    b = prompt_hash("a1", "m1", "prompt one.")
    assert a != b


def test_hash_changes_with_model(store):
    assert prompt_hash("a1", "m1", "p") != prompt_hash("a1", "m2", "p")


def test_hash_changes_with_role(store):
    assert prompt_hash("a1", "m", "p") != prompt_hash("a2", "m", "p")


def test_edited_prompt_invalidates_the_fixture(store):
    store.record(role="a1", model="m", rendered_prompt="original",
                 response_text="{}", provenance="handcrafted")
    p = ReplayProvider("m", store=store, record_pending=False)
    assert p.complete(role="a1", prompt="original").text == "{}"
    with pytest.raises(MissingFixture):
        p.complete(role="a1", prompt="original, but edited")


def test_unknown_provenance_is_refused(store):
    with pytest.raises(ValueError, match="provenance"):
        store.record(role="a1", model="m", rendered_prompt="p",
                     response_text="{}", provenance="captured-from-somewhere")


def test_tampered_fixture_is_refused(store):
    fx = store.record(role="a1", model="m", rendered_prompt="p",
                      response_text="{}", provenance="handcrafted")
    path = store.path_for(fx.key)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["rendered_prompt"] = "a different prompt entirely"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="not trustworthy"):
        store.load(fx.key, role="a1", model="m")


def test_shipped_fixtures_declare_honest_provenance():
    """No shipped fixture may claim to be a live API capture unless it was one."""
    from ssf_hve.paths import FIXTURES_DIR
    from ssf_hve.replay.store import PROVENANCE
    bad = []
    for p in sorted(FIXTURES_DIR.glob("*.json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        if raw["provenance"] not in PROVENANCE:
            bad.append((p.name, raw["provenance"]))
        if not Fixture(**raw).verify_key():
            bad.append((p.name, "key does not match prompt"))
    assert not bad, bad


def test_replay_provider_does_no_network_io():
    import ast
    import inspect

    import ssf_hve.providers.replay as mod
    tree = ast.parse(inspect.getsource(mod))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"urllib", "http", "socket", "requests", "httpx"}
