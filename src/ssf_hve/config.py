"""Workflow configurations.

Each entry is one row of the improvement changelog, runnable on its own so the
ablation is a real experiment rather than a description of one.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Config:
    config_id: str
    condition: str                     # "baseline" | "advanced"
    label: str
    use_claim_map: bool                # A1 runs
    use_designer: bool                 # A2 runs as a separate role
    deterministic_checks: bool         # deterministic source checks run at all
    deterministic_owner: str           # "code" | "model"
    use_verifier: bool                 # A3 runs
    split_observation: bool            # A3 separates observation from recommended action
    max_correction_cycles: int
    allow_progress_at_bound: bool      # removal experiment; never true in a retained config
    requires_h1: bool

    def material(self) -> dict:
        return asdict(self)


CONFIGS: dict[str, Config] = {
    "baseline": Config(
        config_id="baseline",
        condition="baseline",
        label="One direct prompt, same model, same source, same target output",
        use_claim_map=False, use_designer=False,
        deterministic_checks=False, deterministic_owner="code",
        use_verifier=False, split_observation=False,
        max_correction_cycles=0, allow_progress_at_bound=True,
        requires_h1=False,
    ),
    "iter-1": Config(
        config_id="iter-1",
        condition="advanced",
        label="Baseline prompt plus deterministic source checks and one code-driven correction",
        use_claim_map=False, use_designer=False,
        deterministic_checks=True, deterministic_owner="code",
        use_verifier=False, split_observation=False,
        max_correction_cycles=1, allow_progress_at_bound=False,
        requires_h1=True,
    ),
    "iter-2": Config(
        config_id="iter-2",
        condition="advanced",
        label="Staged claim map (A1) then script design (A2); no verifier, no deterministic checks",
        use_claim_map=True, use_designer=True,
        deterministic_checks=False, deterministic_owner="code",
        use_verifier=False, split_observation=False,
        max_correction_cycles=0, allow_progress_at_bound=False,
        requires_h1=True,
    ),
    "iter-3": Config(
        config_id="iter-3",
        condition="advanced",
        label="A1 + A2 + deterministic checks + independent verifier (A3) with a bounded correction loop",
        use_claim_map=True, use_designer=True,
        deterministic_checks=True, deterministic_owner="code",
        use_verifier=True, split_observation=False,
        max_correction_cycles=2, allow_progress_at_bound=False,
        requires_h1=True,
    ),
    "iter-4": Config(
        config_id="iter-4",
        condition="advanced",
        label="iter-3 with observation separated from recommended action in every finding",
        use_claim_map=True, use_designer=True,
        deterministic_checks=True, deterministic_owner="code",
        use_verifier=True, split_observation=True,
        max_correction_cycles=2, allow_progress_at_bound=False,
        requires_h1=True,
    ),
    # ---- removal experiments -------------------------------------------------
    "rm-bound-ok": Config(
        config_id="rm-bound-ok",
        condition="advanced",
        label="REMOVAL EXPERIMENT: treat exhausting the correction limit as success",
        use_claim_map=True, use_designer=True,
        deterministic_checks=True, deterministic_owner="code",
        use_verifier=True, split_observation=True,
        max_correction_cycles=2, allow_progress_at_bound=True,
        requires_h1=True,
    ),
    "rm-model-checks": Config(
        config_id="rm-model-checks",
        condition="advanced",
        label="REMOVAL EXPERIMENT: route deterministically checkable findings through the model",
        use_claim_map=True, use_designer=True,
        deterministic_checks=True, deterministic_owner="model",
        use_verifier=True, split_observation=True,
        max_correction_cycles=2, allow_progress_at_bound=False,
        requires_h1=True,
    ),
    # ---- final retained ------------------------------------------------------
    "final": Config(
        config_id="final",
        condition="advanced",
        label="Final retained combination",
        use_claim_map=True, use_designer=True,
        deterministic_checks=True, deterministic_owner="code",
        use_verifier=True, split_observation=True,
        max_correction_cycles=2, allow_progress_at_bound=False,
        requires_h1=True,
    ),
}

DEFAULT_ADVANCED = "final"
ABLATION_ORDER = ["baseline", "iter-1", "iter-2", "iter-3", "iter-4",
                  "rm-bound-ok", "rm-model-checks", "final"]


def get_config(config_id: str) -> Config:
    try:
        return CONFIGS[config_id]
    except KeyError:
        raise SystemExit(
            f"unknown config '{config_id}'. Known: {', '.join(ABLATION_ORDER)}")
