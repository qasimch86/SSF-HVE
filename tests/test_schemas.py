"""Schema validation, and the rule that malformed model output fails closed."""
import json

import pytest

from ssf_hve.schemas import (ClaimMap, Finding, MalformedModelOutput, Script,
                             SchemaError, VerifierResult, extract_json_object,
                             parse_or_fail_closed)

GOOD_VERIFIER = {
    "findings": [{
        "id": "F01", "severity": "MAJOR", "claim_ref": "CL01",
        "evidence_ref": "results_table[0]", "quoted_span": "cuts your risk by 42%",
        "observation": "The figure is stated without the word relative.",
        "explanation": "The source reports a relative reduction.",
        "recommended_correction": "Say 42% relative reduction.",
    }],
    "recommendation": "EDIT",
    "rationale": "One material wording problem.",
}


def test_valid_verifier_result_parses():
    r = VerifierResult.parse(GOOD_VERIFIER, split_observation=True)
    assert r.recommendation == "EDIT"
    assert len(r.blocking()) == 1


def test_unknown_recommendation_rejected():
    bad = json.loads(json.dumps(GOOD_VERIFIER))
    bad["recommendation"] = "LOOKS_FINE_TO_ME"
    with pytest.raises(SchemaError):
        VerifierResult.parse(bad, split_observation=True)


def test_accept_with_blocking_finding_rejected():
    """The verifier may not approve while reporting a blocker. Not a judgement
    call: a structure that says both things is invalid."""
    bad = json.loads(json.dumps(GOOD_VERIFIER))
    bad["recommendation"] = "ACCEPT"
    with pytest.raises(SchemaError, match="inconsistent"):
        VerifierResult.parse(bad, split_observation=True)


def test_extra_field_rejected():
    bad = json.loads(json.dumps(GOOD_VERIFIER))
    bad["auto_approve"] = True
    with pytest.raises(SchemaError, match="unexpected field"):
        VerifierResult.parse(bad, split_observation=True)


def test_empty_quoted_span_rejected():
    bad = json.loads(json.dumps(GOOD_VERIFIER))
    bad["findings"][0]["quoted_span"] = "   "
    with pytest.raises(SchemaError):
        VerifierResult.parse(bad, split_observation=True)


def test_observation_field_absent_when_not_split():
    with pytest.raises(SchemaError, match="unexpected field"):
        VerifierResult.parse(GOOD_VERIFIER, split_observation=False)


def test_duplicate_finding_ids_rejected():
    bad = json.loads(json.dumps(GOOD_VERIFIER))
    bad["findings"].append(json.loads(json.dumps(bad["findings"][0])))
    with pytest.raises(SchemaError, match="duplicate"):
        VerifierResult.parse(bad, split_observation=True)


@pytest.mark.parametrize("text", [
    "", "   ", "no json here",
    "Sure! Here is the result:",
    "[1, 2, 3]",
    '{"findings": [], "recommendation": "EDIT"',            # truncated
    '```json\n{"a":1}\n```\n```json\n{"b":2}\n```',          # two blocks
])
def test_malformed_output_fails_closed(text):
    with pytest.raises(MalformedModelOutput):
        extract_json_object(text, where="test")


def test_parse_or_fail_closed_converts_schema_error():
    payload = json.dumps({"findings": [], "recommendation": "NOPE", "rationale": ""})
    with pytest.raises(MalformedModelOutput):
        parse_or_fail_closed(
            payload, lambda o, w: VerifierResult.parse(o, w, split_observation=True),
            "test")


def test_claim_requires_evidence_reference():
    cm = {"case_id": "C01", "claims": [{
        "id": "CL01", "text": "x", "evidence_level": "observational",
        "evidence_refs": [], "quantities": [], "limitations": [],
        "uncertainty": "", "scope": "human"}],
        "source_limitations": [], "prohibited_extensions": [],
        "embedded_instruction_text": []}
    with pytest.raises(SchemaError, match="at least one reference"):
        ClaimMap.parse(cm)


def test_script_requires_beats():
    with pytest.raises(SchemaError):
        Script.parse({"case_id": "C01", "audience": "a", "target_duration_s": 60,
                      "beats": []})
