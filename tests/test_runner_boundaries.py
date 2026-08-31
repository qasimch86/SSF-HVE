"""Agent boundaries, the correction bound, and fail-closed control flow."""
import json

import pytest

from ssf_hve.cases import load_case
from ssf_hve.config import get_config
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.runner import execute

CASE = load_case("C01")

CLAIM_MAP = json.dumps({
    "case_id": "C01",
    "claims": [{"id": "CL01", "text": "Irregular sleep timing was associated with events.",
                "evidence_level": "observational", "evidence_refs": ["abstract"],
                "quantities": [{"label": "hazard ratio", "value": "1.34", "unit": ""}],
                "limitations": ["Observational."], "uncertainty": "95% CI 1.18-1.52",
                "scope": "human"}],
    "source_limitations": ["Sleep timing was measured once, over 7 days."],
    "prohibited_extensions": ["Do not use causal language."],
    "embedded_instruction_text": []})

SCRIPT = json.dumps({
    "case_id": "C01", "audience": "General public", "target_duration_s": 60,
    "beats": [{"beat": "open", "narration": "People with irregular sleep timing had a higher event rate.",
               "on_screen": "chart", "claim_refs": ["CL01"]}]})


def _verifier(recommendation, severity="MAJOR"):
    findings = [] if recommendation == "ACCEPT" else [{
        "id": "F01", "severity": severity, "claim_ref": "CL01",
        "evidence_ref": "abstract", "quoted_span": "higher event rate",
        "observation": "Observed.", "explanation": "Because.",
        "recommended_correction": "Change it."}]
    return json.dumps({"findings": findings, "recommendation": recommendation,
                       "rationale": "test"})


class ScriptedProvider(Provider):
    """Serves canned responses by role prefix. No network, no fixtures."""
    name = "scripted"

    def __init__(self, verifier_response, model="test-model"):
        super().__init__(model)
        self.verifier_response = verifier_response
        self.calls = []

    def complete(self, *, role, prompt):
        self.calls.append(role)
        if role.startswith("a1"):
            text = CLAIM_MAP
        elif role.startswith("a3"):
            text = self.verifier_response
        else:
            text = SCRIPT
        return ModelResponse(text=text, model=self.model, provenance="handcrafted")


def test_bounded_correction_loop_stops_at_two_cycles():
    cfg = get_config("final")
    p = ScriptedProvider(_verifier("EDIT"))
    rec = execute(CASE, cfg, p)
    assert rec.meta.correction_cycles == cfg.max_correction_cycles == 2
    assert rec.meta.terminal_status == "HOLD"


def test_reaching_the_bound_is_not_success():
    """A counter running out is not evidence that anybody fixed anything."""
    rec = execute(CASE, get_config("final"), ScriptedProvider(_verifier("EDIT")))
    assert rec.meta.terminal_status == "HOLD"
    assert rec.unresolved_findings, "unresolved findings must remain visible"


def test_removal_experiment_makes_the_bound_look_like_success():
    """rm-bound-ok exists to show what the metric cannot see."""
    rec = execute(CASE, get_config("rm-bound-ok"), ScriptedProvider(_verifier("EDIT")))
    assert rec.meta.terminal_status == "ACCEPT"
    assert rec.unresolved_findings, "the findings are still there; only the label changed"


def test_malformed_verifier_output_fails_closed():
    rec = execute(CASE, get_config("final"), ScriptedProvider("I think it's fine!"))
    assert rec.meta.terminal_status == "MALFORMED"
    assert rec.final_script is None


def test_verifier_cannot_approve_while_reporting_a_blocker():
    bad = json.dumps({
        "findings": [{"id": "F01", "severity": "BLOCKER", "claim_ref": "CL01",
                      "evidence_ref": "a", "quoted_span": "x", "observation": "o",
                      "explanation": "e", "recommended_correction": "c"}],
        "recommendation": "ACCEPT", "rationale": "trust me"})
    rec = execute(CASE, get_config("final"), ScriptedProvider(bad))
    assert rec.meta.terminal_status == "MALFORMED"


def test_h1_gate_is_blocked_by_default():
    rec = execute(CASE, get_config("final"), ScriptedProvider(_verifier("ACCEPT")))
    assert rec.meta.terminal_status == "ACCEPT"
    assert rec.h1_gate["state"] == "BLOCKED_AWAITING_HUMAN"


def test_baseline_makes_exactly_one_model_call():
    p = ScriptedProvider(_verifier("ACCEPT"))
    rec = execute(CASE, get_config("baseline"), p)
    assert rec.meta.model_calls == 1
    assert [c.split("#")[0] for c in p.calls] == ["baseline"]


def test_advanced_calls_roles_in_order():
    p = ScriptedProvider(_verifier("ACCEPT"))
    execute(CASE, get_config("final"), p)
    roles = [c.split("#")[0].split("-")[0] for c in p.calls]
    assert roles[:3] == ["a1", "a2", "a3"]


def test_a2_never_sees_the_raw_source_in_its_prompt():
    """A2 writes from the approved claim map, not from the paper."""
    from ssf_hve.agents.a2_designer import build_prompt
    from ssf_hve.schemas import ClaimMap
    prompt = build_prompt(CASE, ClaimMap.parse(json.loads(CLAIM_MAP)))
    assert CASE.source["abstract"][:80] not in prompt


def test_run_record_is_written_even_on_failure(tmp_path):
    rec = execute(CASE, get_config("final"), ScriptedProvider("not json"))
    from ssf_hve.paths import RUNS_DIR
    assert (RUNS_DIR / f"{rec.meta.run_id}.json").exists()
