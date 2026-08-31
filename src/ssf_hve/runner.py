"""Workflow execution: baseline and the staged advanced pipeline.

Control flow is owned here, in code. Model output is parsed, validated and then
used as data. Nothing a model returns selects the next step except through the
fixed vocabulary defined in ``schemas.RECOMMENDATIONS``, and even then a person,
not the model, decides whether the result may proceed.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from ssf_hve import gates
from ssf_hve.agents import a1_analyst, a2_designer, a3_verifier
from ssf_hve.cases import Case
from ssf_hve.checks.deterministic import (CheckFinding, check_reference_integrity,
                                          run_checks)
from ssf_hve.config import Config
from ssf_hve.paths import RUNS_DIR, ensure_dirs
from ssf_hve.prompting import as_json, render
from ssf_hve.providers.base import ModelResponse, Provider
from ssf_hve.replay.store import MissingFixture, prompt_hash
from ssf_hve.schemas import (ClaimMap, MalformedModelOutput, RunMetadata, Script,
                             VerifierResult)

BLOCKING = ("BLOCKER", "MAJOR")


@dataclass
class Step:
    index: int
    role: str
    kind: str
    prompt_sha256: str = ""
    rendered_prompt: str = ""
    response_text: str = ""
    provenance: str = ""
    ok: bool = True
    error: str = ""
    parsed_summary: dict = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class Cycle:
    index: int
    deterministic_findings: list[dict] = field(default_factory=list)
    verifier: dict | None = None
    blocking_count: int = 0
    action: str = ""


@dataclass
class RunRecord:
    meta: RunMetadata
    config: dict
    steps: list[Step] = field(default_factory=list)
    cycles: list[Cycle] = field(default_factory=list)
    claim_map: dict | None = None
    final_script: dict | None = None
    final_narration: str = ""
    h1_gate: dict = field(default_factory=dict)
    unresolved_findings: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": "ssf-hve/run/1",
            "meta": self.meta.to_dict(),
            "config": self.config,
            "steps": [s.__dict__ for s in self.steps],
            "cycles": [c.__dict__ for c in self.cycles],
            "claim_map": self.claim_map,
            "final_script": self.final_script,
            "final_narration": self.final_narration,
            "h1_gate": self.h1_gate,
            "unresolved_findings": self.unresolved_findings,
        }

    def save(self) -> str:
        ensure_dirs()
        path = RUNS_DIR / f"{self.meta.run_id}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        return str(path)


def new_run_id(case_id: str, config_id: str, sample: int) -> str:
    return f"{case_id}-{config_id}-s{sample}-{uuid.uuid4().hex[:8]}"


class SampledProvider:
    """Wraps a provider so that repeated samples of the same prompt get their
    own fixture key. Sampling index is part of the key, never of the prompt:
    every sample sees byte-identical instructions."""

    def __init__(self, inner: Provider, sample: int):
        self.inner, self.sample = inner, sample
        self.name, self.model = inner.name, inner.model
        # The most recent call, kept so that a response which fails schema
        # validation is still recorded in the run rather than lost with the
        # exception. Failing closed must not mean failing silently.
        self.last_call: tuple[str, str, ModelResponse] | None = None

    def complete(self, *, role: str, prompt: str) -> ModelResponse:
        scoped = f"{role}#s{self.sample}"
        resp = self.inner.complete(role=scoped, prompt=prompt)
        self.last_call = (scoped, prompt, resp)
        return resp


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _record_step(rec: RunRecord, role: str, kind: str, prompt: str,
                 resp: ModelResponse | None, *, ok: bool, error: str = "",
                 summary: dict | None = None, model: str = "") -> None:
    # The key the provider actually used, so that a trajectory step resolves to a
    # file in fixtures/replay/. Falls back to a locally computed hash only when no
    # provider response exists (an error before the call returned).
    key = (resp.fixture_key if resp is not None and resp.fixture_key
           else prompt_hash(role, model or rec.meta.model, prompt))
    step = Step(index=len(rec.steps) + 1, role=role, kind=kind,
                prompt_sha256=key,
                rendered_prompt=prompt,
                response_text=resp.text if resp else "",
                provenance=resp.provenance if resp else "",
                ok=ok, error=error, parsed_summary=summary or {},
                input_tokens=resp.input_tokens if resp else None,
                output_tokens=resp.output_tokens if resp else None)
    rec.steps.append(step)
    if resp is not None:
        rec.meta.model_calls += 1
        if resp.input_tokens is not None:
            rec.meta.input_tokens = (rec.meta.input_tokens or 0) + resp.input_tokens
        if resp.output_tokens is not None:
            rec.meta.output_tokens = (rec.meta.output_tokens or 0) + resp.output_tokens
        if resp.estimated_cost_usd is not None:
            rec.meta.estimated_cost_usd = ((rec.meta.estimated_cost_usd or 0.0)
                                           + resp.estimated_cost_usd)


def _baseline_prompt(case: Case) -> str:
    return render("baseline.md", {
        "CASE_ID": case.case_id,
        "AUDIENCE": case.audience,
        "DURATION": case.target_duration_s,
        "SOURCE": case.source_text(),
    })


def _deterministic(case: Case, script: Script, claim_map: ClaimMap | None) -> list[CheckFinding]:
    lims = list(case.source.get("limitations") or [])
    findings = run_checks(script_text=script.narration_text,
                          source_text=case.source_text(),
                          claim_map=claim_map, source_limitations=lims)
    findings.extend(check_reference_integrity(script, claim_map))
    return findings


def execute(case: Case, config: Config, provider: Provider, *,
            mode: str = "replay", sample: int = 1) -> RunRecord:
    """Run one case under one configuration. Never raises for model problems."""
    provider = SampledProvider(provider, sample)
    meta = RunMetadata(
        run_id=new_run_id(case.case_id, config.config_id, sample), case_id=case.case_id,
        config_id=config.config_id, condition=config.condition,
        provider=provider.name, model=provider.model, mode=mode,
        started_utc=_now())
    rec = RunRecord(meta=meta, config=dict(config.material(), sample=sample))
    t0 = time.time()
    try:
        _execute_inner(case, config, provider, rec)
    except MissingFixture as exc:
        rec.meta.terminal_status = "ERROR"
        rec.meta.error = f"missing replay fixture: {exc}"
    except MalformedModelOutput as exc:
        rec.meta.terminal_status = "MALFORMED"
        rec.meta.error = str(exc)
        _record_rejected_call(rec, provider, str(exc))
    except Exception as exc:                       # noqa: BLE001 - recorded, never hidden
        rec.meta.terminal_status = "ERROR"
        rec.meta.error = f"{type(exc).__name__}: {exc}"
    rec.meta.finished_utc = _now()
    rec.meta.wall_clock_s = round(time.time() - t0, 3)
    rec.save()
    return rec


def _record_rejected_call(rec: RunRecord, provider, error: str) -> None:
    """Append the model call whose output failed validation.

    Without this the trajectory of a fail-closed run shows every step that
    succeeded and nothing about the one that did not, which is precisely the
    evidence a reader needs.
    """
    last = getattr(provider, "last_call", None)
    if last is None:
        return
    scoped_role, prompt, resp = last
    rec.steps.append(Step(
        index=len(rec.steps) + 1, role=scoped_role, kind="rejected_output",
        prompt_sha256=resp.fixture_key or prompt_hash(scoped_role, rec.meta.model, prompt),
        rendered_prompt=prompt, response_text=resp.text, provenance=resp.provenance,
        ok=False, error=error,
        parsed_summary={"schema_validation": "REJECTED",
                        "action_taken": "run terminated MALFORMED; no repair attempted"},
        input_tokens=resp.input_tokens, output_tokens=resp.output_tokens))
    rec.meta.model_calls += 1


def _execute_inner(case: Case, config: Config, provider: Provider,
                   rec: RunRecord) -> None:
    claim_map: ClaimMap | None = None

    # ---- A1 -----------------------------------------------------------------
    if config.use_claim_map:
        claim_map, resp, prompt = a1_analyst.run(case, provider)
        _record_step(rec, a1_analyst.ROLE, "claim_map", prompt, resp, ok=True,
                     summary={"claims": len(claim_map.claims),
                              "embedded_instruction_text": len(claim_map.embedded_instruction_text)})
        rec.claim_map = a2_designer._claim_map_payload(claim_map)

    # ---- initial script (A2, or the direct baseline prompt) ------------------
    if config.use_designer and claim_map is not None:
        script, resp, prompt = a2_designer.run(case, claim_map, provider)
        _record_step(rec, a2_designer.ROLE, "script", prompt, resp, ok=True,
                     summary={"beats": len(script.beats)})
    else:
        prompt = _baseline_prompt(case)
        resp = provider.complete(role="baseline", prompt=prompt)
        script = a2_designer._parse(resp.text, "baseline.script")
        _record_step(rec, "baseline", "script", prompt, resp, ok=True,
                     summary={"beats": len(script.beats)}, model=provider.model)

    # ---- bounded correction loop --------------------------------------------
    terminal = "ACCEPT"
    unresolved: list[dict] = []
    max_cycles = max(config.max_correction_cycles, 0)

    for cycle_index in range(0, max_cycles + 1):
        cyc = Cycle(index=cycle_index)

        det: list[CheckFinding] = []
        if config.deterministic_checks and config.deterministic_owner == "code":
            det = _deterministic(case, script, claim_map)
        cyc.deterministic_findings = [d.as_dict() for d in det]

        verifier: VerifierResult | None = None
        if config.use_verifier:
            verifier, vresp, vprompt = a3_verifier.run(
                case, claim_map, script, cyc.deterministic_findings, provider,
                split_observation=config.split_observation,
                deterministic_owner=config.deterministic_owner,
                cycle=cycle_index)
            _record_step(rec, "a3", "verifier_result", vprompt, vresp, ok=True,
                         summary={"findings": len(verifier.findings),
                                  "recommendation": verifier.recommendation})
            cyc.verifier = {
                "recommendation": verifier.recommendation,
                "rationale": verifier.rationale,
                "findings": [f.__dict__ for f in verifier.findings],
            }

        blocking = [d.as_dict() for d in det if d.severity in BLOCKING]
        if verifier is not None:
            blocking += [f.__dict__ for f in verifier.blocking()]
        cyc.blocking_count = len(blocking)

        if not blocking:
            terminal = verifier.recommendation if verifier is not None else "ACCEPT"
            cyc.action = f"terminate:{terminal}"
            rec.cycles.append(cyc)
            break

        if cycle_index == max_cycles:
            # The bound. A counter running out is not evidence anybody fixed
            # anything, so the default is HOLD with the findings preserved.
            if config.allow_progress_at_bound:
                terminal = "ACCEPT"
                cyc.action = ("terminate:ACCEPT (removal experiment: progression "
                              "permitted at the correction bound)")
            else:
                terminal = "HOLD"
                cyc.action = "terminate:HOLD (correction limit reached, findings unresolved)"
            unresolved = blocking
            rec.cycles.append(cyc)
            break

        cyc.action = f"correct:cycle{cycle_index + 1}"
        rec.cycles.append(cyc)
        script, cresp, cprompt = a2_designer.run_correction(
            case, claim_map if claim_map is not None else _null_claim_map(case),
            script, blocking, cycle_index + 1, max_cycles, provider)
        _record_step(rec, f"a2-correction-{cycle_index + 1}", "script", cprompt,
                     cresp, ok=True, summary={"beats": len(script.beats)})
        rec.meta.correction_cycles = cycle_index + 1

    rec.meta.terminal_status = terminal
    rec.unresolved_findings = unresolved
    rec.final_script = script.to_dict()
    rec.final_narration = script.narration_text

    # ---- H1: human-only, and the absence blocks ------------------------------
    if config.requires_h1:
        # A freshly created run cannot have a bound approval yet; h1_status
        # reads the run-bound record (if any) and validates the full binding.
        approval, _why = gates.h1_status(rec.meta.run_id)
        rec.h1_gate = {
            "gate": "H1",
            "artifact_sha256": gates.artifact_sha256(rec.final_narration),
            "state": "APPROVED" if approval else "BLOCKED_AWAITING_HUMAN",
            "approver": approval.approver if approval else None,
            "approved_utc": approval.approved_utc if approval else None,
            "note": ("Production is blocked until a person approves this exact "
                     "script version. No agent status can open this gate."),
        }
    else:
        rec.h1_gate = {"gate": "H1", "state": "NOT_APPLICABLE",
                       "note": "This configuration has no human gate by design."}


class _NullClaimMap:
    """Placeholder used when a configuration has no A1 stage."""

    case_id = ""
    claims: tuple = ()
    source_limitations: tuple = ()
    prohibited_extensions: tuple = ()
    embedded_instruction_text: tuple = ()

    def claim_ids(self):
        return set()


def _null_claim_map(case: Case):
    nm = _NullClaimMap()
    nm.case_id = case.case_id
    return nm
