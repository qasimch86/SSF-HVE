"""Provider abstraction. Model output is data; providers never execute anything."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelResponse:
    text: str
    model: str
    provenance: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    from_fixture: bool = False
    # The replay-store key this response was served from, or stored under. Recorded
    # in the run so that a trajectory step resolves to fixtures/replay/<key>.json.
    fixture_key: str = ""


class Provider:
    name = "abstract"

    def __init__(self, model: str):
        self.model = model

    def complete(self, *, role: str, prompt: str) -> ModelResponse:
        raise NotImplementedError
