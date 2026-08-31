"""A3 - Independent Verifier. Recommends; never decides, never rewrites."""
from __future__ import annotations

from ssf_hve.cases import Case
from ssf_hve.paths import PROMPTS_DIR
from ssf_hve.prompting import as_json, render
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.schemas import (ClaimMap, MalformedModelOutput, Script,
                             VerifierResult, parse_or_fail_closed)

ROLE = "a3"

_OBSERVATION_LINE = (PROMPTS_DIR / "a3_verifier_observation_note.txt")


CODE_OWNED_POLICY = (
    "Deterministic checks have already run over this script and their results are\n"
    "included below. Do not repeat them and do not re-litigate them. Report only\n"
    "what code cannot already establish."
)

MODEL_OWNED_POLICY = (
    "No deterministic checks were run in this configuration. You must therefore\n"
    "also perform them yourself: compare every number in the script against the\n"
    "source record, confirm that each stated limitation in the source appears in\n"
    "the script, and confirm that every beat stating science cites a claim id that\n"
    "exists in the claim map. Report those alongside anything else you find."
)


def build_prompt(case: Case, claim_map: ClaimMap | None, script: Script,
                 deterministic: list[dict], *, split_observation: bool,
                 deterministic_owner: str = "code") -> str:
    obs = _OBSERVATION_LINE.read_text(encoding="utf-8") if split_observation else ""
    policy = CODE_OWNED_POLICY if deterministic_owner == "code" else MODEL_OWNED_POLICY
    return render("a3_verifier.md", {
        "DETERMINISTIC_POLICY": policy,
        "OBSERVATION_FIELD": obs,
        "CLAIM_MAP": as_json(_cm_payload(claim_map)),
        "SCRIPT": as_json(script.to_dict()),
        "DETERMINISTIC": as_json(deterministic) if deterministic
                         else "No deterministic findings were raised.",
        "SOURCE": case.source_text(),
    })


def _cm_payload(cm: ClaimMap | None) -> object:
    if cm is None:
        return "No claim map was produced in this configuration."
    return {
        "claims": [{"id": c.id, "text": c.text, "evidence_level": c.evidence_level,
                    "scope": c.scope, "evidence_refs": list(c.evidence_refs),
                    "limitations": list(c.limitations)} for c in cm.claims],
        "source_limitations": list(cm.source_limitations),
        "prohibited_extensions": list(cm.prohibited_extensions),
    }


def run(case: Case, claim_map: ClaimMap | None, script: Script,
        deterministic: list[dict], provider: Provider, *,
        split_observation: bool, deterministic_owner: str = "code",
        cycle: int = 0) -> tuple[VerifierResult, ModelResponse, str]:
    prompt = build_prompt(case, claim_map, script, deterministic,
                          split_observation=split_observation,
                          deterministic_owner=deterministic_owner)
    suffix = "-split" if split_observation else ""
    if deterministic_owner != "code":
        suffix += "-modelchecks"
    role = f"{ROLE}{suffix}-c{cycle}"
    resp = provider.complete(role=role, prompt=prompt)
    result = parse_or_fail_closed(
        resp.text,
        lambda o, w: VerifierResult.parse(o, w, split_observation=split_observation),
        f"A3.verifier_result.cycle{cycle}")
    return result, resp, prompt
