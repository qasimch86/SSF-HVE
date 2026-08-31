"""A2 - Script Designer. Writes from the approved claim map only."""
from __future__ import annotations

from ssf_hve.cases import Case
from ssf_hve.prompting import as_json, render
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.schemas import ClaimMap, Script, parse_or_fail_closed

ROLE = "a2"
WORDS_PER_SECOND = 2.4


def build_prompt(case: Case, claim_map: ClaimMap) -> str:
    return render("a2_designer.md", {
        "CASE_ID": case.case_id,
        "AUDIENCE": case.audience,
        "DURATION": case.target_duration_s,
        "WORDS": int(case.target_duration_s * WORDS_PER_SECOND),
        "CLAIM_MAP": as_json(_claim_map_payload(claim_map)),
    })


def build_correction_prompt(case: Case, claim_map: ClaimMap, script: Script,
                            findings: list[dict], cycle: int, max_cycles: int) -> str:
    return render("a2_correction.md", {
        "CYCLE": cycle,
        "MAX_CYCLES": max_cycles,
        "CLAIM_MAP": as_json(_claim_map_payload(claim_map)),
        "SCRIPT": as_json(script.to_dict()),
        "FINDINGS": as_json(findings),
    })


def _claim_map_payload(cm: ClaimMap) -> dict:
    return {
        "case_id": cm.case_id,
        "claims": [
            {"id": c.id, "text": c.text, "evidence_level": c.evidence_level,
             "evidence_refs": list(c.evidence_refs),
             "quantities": [{"label": q.label, "value": q.value, "unit": q.unit}
                            for q in c.quantities],
             "limitations": list(c.limitations), "uncertainty": c.uncertainty,
             "scope": c.scope}
            for c in cm.claims],
        "source_limitations": list(cm.source_limitations),
        "prohibited_extensions": list(cm.prohibited_extensions),
        "embedded_instruction_text_found_in_source": list(cm.embedded_instruction_text),
    }


def _parse(resp_text: str, where: str) -> Script:
    return parse_or_fail_closed(resp_text, lambda o, w: Script.parse(o, w), where)


def run(case: Case, claim_map: ClaimMap, provider: Provider) -> tuple[Script, ModelResponse, str]:
    prompt = build_prompt(case, claim_map)
    resp = provider.complete(role=ROLE, prompt=prompt)
    return _parse(resp.text, "A2.script"), resp, prompt


def run_correction(case: Case, claim_map: ClaimMap, script: Script,
                   findings: list[dict], cycle: int, max_cycles: int,
                   provider: Provider) -> tuple[Script, ModelResponse, str]:
    prompt = build_correction_prompt(case, claim_map, script, findings, cycle, max_cycles)
    resp = provider.complete(role=f"a2-correction-{cycle}", prompt=prompt)
    return _parse(resp.text, f"A2.script.correction{cycle}"), resp, prompt
