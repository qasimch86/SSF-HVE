"""A1 - Scientific Analyst. Produces a claim map. Designs nothing, approves nothing."""
from __future__ import annotations

from ssf_hve.cases import Case
from ssf_hve.prompting import render
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.schemas import ClaimMap, parse_or_fail_closed

ROLE = "a1"


def build_prompt(case: Case) -> str:
    return render("a1_analyst.md", {
        "CASE_ID": case.case_id,
        "SOURCE": case.source_text(),
    })


def run(case: Case, provider: Provider) -> tuple[ClaimMap, ModelResponse, str]:
    prompt = build_prompt(case)
    resp = provider.complete(role=ROLE, prompt=prompt)
    claim_map = parse_or_fail_closed(
        resp.text, lambda o, w: ClaimMap.parse(o, w), "A1.claim_map")
    return claim_map, resp, prompt
