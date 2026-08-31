"""Replay provider: serves recorded responses, never touches the network."""
from __future__ import annotations

import json
from pathlib import Path

from ssf_hve.paths import RESULTS_DIR
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.replay.store import FixtureStore, MissingFixture, prompt_hash

PENDING_DIR = RESULTS_DIR / "pending_capture"


class ReplayProvider(Provider):
    name = "replay"

    def __init__(self, model: str, store: FixtureStore | None = None,
                 record_pending: bool = True):
        super().__init__(model)
        self.store = store or FixtureStore()
        self.record_pending = record_pending

    def complete(self, *, role: str, prompt: str) -> ModelResponse:
        key = prompt_hash(role, self.model, prompt)
        if not self.store.has(key):
            if self.record_pending:
                self._write_pending(key, role, prompt)
            raise MissingFixture(key, role, self.model)
        fx = self.store.load(key, role=role, model=self.model)
        return ModelResponse(
            text=fx.response_text, model=fx.model, provenance=fx.provenance,
            input_tokens=fx.input_tokens, output_tokens=fx.output_tokens,
            estimated_cost_usd=fx.estimated_cost_usd, from_fixture=True,
            fixture_key=key)

    def _write_pending(self, key: str, role: str, prompt: str) -> Path:
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        meta = PENDING_DIR / f"{key}.meta.json"
        body = PENDING_DIR / f"{key}.prompt.txt"
        if not meta.exists():
            with meta.open("w", encoding="utf-8") as fh:
                json.dump({"key": key, "role": role, "model": self.model}, fh,
                          indent=2)
                fh.write("\n")
        if not body.exists():
            body.write_text(prompt, encoding="utf-8")
        return body
