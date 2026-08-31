"""Prompt-hash-keyed replay fixtures.

A fixture is keyed by sha256 over the role, the model identifier and the
complete rendered instruction. Change the prompt, the case or the model and the
key changes, so a stale response cannot be silently reused. The full rendered
prompt is stored inside the fixture, which makes every key independently
verifiable by a judge.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path

from ssf_hve.paths import FIXTURES_DIR

SCHEMA = "ssf-hve/replay-fixture/1"

PROVENANCE = ("live-api", "blinded-agent-capture", "handcrafted")


class MissingFixture(KeyError):
    """No recorded response for this exact prompt. Replay fails closed."""

    def __init__(self, key: str, role: str, model: str):
        self.key, self.role, self.model = key, role, model
        super().__init__(
            f"no replay fixture for role={role} model={model} key={key[:16]}... "
            f"(capture it, or run with --live)")


def prompt_hash(role: str, model: str, rendered_prompt: str) -> str:
    h = hashlib.sha256()
    h.update(b"ssf-hve/v1\n")
    h.update(role.encode("utf-8") + b"\n")
    h.update(model.encode("utf-8") + b"\n")
    h.update(rendered_prompt.encode("utf-8"))
    return h.hexdigest()


@dataclass
class Fixture:
    schema: str
    key: str
    role: str
    model: str
    provenance: str
    captured_utc: str
    rendered_prompt: str
    response_text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    note: str = ""

    def verify_key(self) -> bool:
        return self.key == prompt_hash(self.role, self.model, self.rendered_prompt)


class FixtureStore:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else FIXTURES_DIR
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def has(self, key: str) -> bool:
        return self.path_for(key).exists()

    def load(self, key: str, *, role: str, model: str) -> Fixture:
        p = self.path_for(key)
        if not p.exists():
            raise MissingFixture(key, role, model)
        with p.open(encoding="utf-8") as fh:
            raw = json.load(fh)
        fx = Fixture(**raw)
        if fx.provenance not in PROVENANCE:
            raise ValueError(f"fixture {key[:12]}: unknown provenance {fx.provenance!r}")
        if not fx.verify_key():
            raise ValueError(
                f"fixture {key[:12]}: stored key does not match its own prompt; "
                "the fixture has been edited and is not trustworthy")
        return fx

    def save(self, fx: Fixture) -> Path:
        if fx.provenance not in PROVENANCE:
            raise ValueError(f"refusing to store unknown provenance {fx.provenance!r}")
        if not fx.verify_key():
            raise ValueError("refusing to store a fixture whose key does not match its prompt")
        p = self.path_for(fx.key)
        with p.open("w", encoding="utf-8") as fh:
            json.dump(asdict(fx), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return p

    def record(self, *, role: str, model: str, rendered_prompt: str,
               response_text: str, provenance: str, note: str = "",
               input_tokens: int | None = None, output_tokens: int | None = None,
               estimated_cost_usd: float | None = None) -> Fixture:
        key = prompt_hash(role, model, rendered_prompt)
        fx = Fixture(
            schema=SCHEMA, key=key, role=role, model=model, provenance=provenance,
            captured_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            rendered_prompt=rendered_prompt, response_text=response_text,
            input_tokens=input_tokens, output_tokens=output_tokens,
            estimated_cost_usd=estimated_cost_usd, note=note)
        self.save(fx)
        return fx

    def provenance_summary(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for p in sorted(self.root.glob("*.json")):
            with p.open(encoding="utf-8") as fh:
                counts_key = json.load(fh).get("provenance", "unknown")
            counts[counts_key] = counts.get(counts_key, 0) + 1
        return counts
