"""Strict typed schemas for every structured object that crosses a boundary.

Design rule: model output is untrusted data. It is validated here, and validation
never repairs, coerces or guesses. A malformed structure raises
``MalformedModelOutput`` and the caller fails closed to a human.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------- errors


class SchemaError(ValueError):
    """A structure did not satisfy its schema."""


class MalformedModelOutput(SchemaError):
    """Model output could not be validated. Never coerced; always fails closed."""


# --------------------------------------------------------------------------- helpers


def _obj(value: Any, where: str) -> dict:
    if not isinstance(value, dict):
        raise SchemaError(f"{where}: expected object, got {type(value).__name__}")
    return value


def _req(d: dict, key: str, where: str) -> Any:
    if key not in d:
        raise SchemaError(f"{where}: missing required field '{key}'")
    return d[key]


def _str(d: dict, key: str, where: str, *, allow_empty: bool = False) -> str:
    v = _req(d, key, where)
    if not isinstance(v, str):
        raise SchemaError(f"{where}.{key}: expected string, got {type(v).__name__}")
    if not allow_empty and not v.strip():
        raise SchemaError(f"{where}.{key}: must not be empty")
    return v


def _opt_str(d: dict, key: str, where: str, default: str = "") -> str:
    if key not in d or d[key] is None:
        return default
    v = d[key]
    if not isinstance(v, str):
        raise SchemaError(f"{where}.{key}: expected string or null")
    return v


def _int(d: dict, key: str, where: str) -> int:
    v = _req(d, key, where)
    if isinstance(v, bool) or not isinstance(v, int):
        raise SchemaError(f"{where}.{key}: expected integer")
    return v


def _list(d: dict, key: str, where: str) -> list:
    v = _req(d, key, where)
    if not isinstance(v, list):
        raise SchemaError(f"{where}.{key}: expected list, got {type(v).__name__}")
    return v


def _enum(value: str, allowed: Iterable[str], where: str) -> str:
    allowed = tuple(allowed)
    if value not in allowed:
        raise SchemaError(f"{where}: {value!r} is not one of {allowed}")
    return value


def _no_extra(d: dict, allowed: Iterable[str], where: str) -> None:
    extra = sorted(set(d) - set(allowed))
    if extra:
        raise SchemaError(f"{where}: unexpected field(s) {extra}")


# --------------------------------------------------------------------------- vocabulary

RECOMMENDATIONS = ("ACCEPT", "EDIT", "REWORK", "HOLD")
SEVERITIES = ("BLOCKER", "MAJOR", "MINOR", "OBSERVATION")
EVIDENCE_LEVELS = (
    "randomised-controlled",
    "observational",
    "preclinical-animal",
    "in-vitro",
    "modelling",
    "review",
    "proposed-untested",
)
SCOPES = ("human", "animal-model", "in-vitro", "population-subgroup", "unspecified")
TERMINAL_STATUSES = ("ACCEPT", "EDIT", "REWORK", "HOLD", "MALFORMED", "ERROR")


# --------------------------------------------------------------------------- A1 output


@dataclass(frozen=True)
class Quantity:
    label: str
    value: str
    unit: str

    @staticmethod
    def parse(raw: Any, where: str) -> "Quantity":
        d = _obj(raw, where)
        _no_extra(d, ("label", "value", "unit"), where)
        return Quantity(
            label=_str(d, "label", where),
            value=_str(d, "value", where),
            unit=_opt_str(d, "unit", where),
        )


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    evidence_level: str
    evidence_refs: tuple[str, ...]
    quantities: tuple[Quantity, ...]
    limitations: tuple[str, ...]
    uncertainty: str
    scope: str

    @staticmethod
    def parse(raw: Any, where: str) -> "Claim":
        d = _obj(raw, where)
        allowed = (
            "id", "text", "evidence_level", "evidence_refs", "quantities",
            "limitations", "uncertainty", "scope",
        )
        _no_extra(d, allowed, where)
        cid = _str(d, "id", where)
        if not re.fullmatch(r"CL[0-9]{2}", cid):
            raise SchemaError(f"{where}.id: expected CLnn, got {cid!r}")
        refs = _list(d, "evidence_refs", where)
        if not refs:
            raise SchemaError(f"{where}.evidence_refs: a claim must cite at least one reference")
        for r in refs:
            if not isinstance(r, str) or not r.strip():
                raise SchemaError(f"{where}.evidence_refs: entries must be non-empty strings")
        quants = [Quantity.parse(q, f"{where}.quantities[{i}]")
                  for i, q in enumerate(_list(d, "quantities", where))]
        lims = _list(d, "limitations", where)
        for l in lims:
            if not isinstance(l, str):
                raise SchemaError(f"{where}.limitations: entries must be strings")
        return Claim(
            id=cid,
            text=_str(d, "text", where),
            evidence_level=_enum(_str(d, "evidence_level", where), EVIDENCE_LEVELS,
                                 f"{where}.evidence_level"),
            evidence_refs=tuple(refs),
            quantities=tuple(quants),
            limitations=tuple(lims),
            uncertainty=_str(d, "uncertainty", where, allow_empty=True),
            scope=_enum(_str(d, "scope", where), SCOPES, f"{where}.scope"),
        )


@dataclass(frozen=True)
class ClaimMap:
    case_id: str
    claims: tuple[Claim, ...]
    source_limitations: tuple[str, ...]
    prohibited_extensions: tuple[str, ...]
    embedded_instruction_text: tuple[str, ...]

    @staticmethod
    def parse(raw: Any, where: str = "claim_map") -> "ClaimMap":
        d = _obj(raw, where)
        allowed = ("case_id", "claims", "source_limitations",
                   "prohibited_extensions", "embedded_instruction_text")
        _no_extra(d, allowed, where)
        claims = [Claim.parse(c, f"{where}.claims[{i}]")
                  for i, c in enumerate(_list(d, "claims", where))]
        if not claims:
            raise SchemaError(f"{where}.claims: at least one claim is required")
        ids = [c.id for c in claims]
        if len(set(ids)) != len(ids):
            raise SchemaError(f"{where}.claims: duplicate claim ids")

        def _strlist(key: str) -> tuple[str, ...]:
            vals = _list(d, key, where)
            for v in vals:
                if not isinstance(v, str):
                    raise SchemaError(f"{where}.{key}: entries must be strings")
            return tuple(vals)

        return ClaimMap(
            case_id=_str(d, "case_id", where),
            claims=tuple(claims),
            source_limitations=_strlist("source_limitations"),
            prohibited_extensions=_strlist("prohibited_extensions"),
            embedded_instruction_text=_strlist("embedded_instruction_text"),
        )

    def claim_ids(self) -> set[str]:
        return {c.id for c in self.claims}


# --------------------------------------------------------------------------- A2 output


@dataclass(frozen=True)
class ScriptBeat:
    beat: str
    narration: str
    on_screen: str
    claim_refs: tuple[str, ...]

    @staticmethod
    def parse(raw: Any, where: str) -> "ScriptBeat":
        d = _obj(raw, where)
        _no_extra(d, ("beat", "narration", "on_screen", "claim_refs"), where)
        refs = _list(d, "claim_refs", where)
        for r in refs:
            if not isinstance(r, str):
                raise SchemaError(f"{where}.claim_refs: entries must be strings")
        return ScriptBeat(
            beat=_str(d, "beat", where),
            narration=_str(d, "narration", where),
            on_screen=_opt_str(d, "on_screen", where),
            claim_refs=tuple(refs),
        )


@dataclass(frozen=True)
class Script:
    case_id: str
    audience: str
    target_duration_s: int
    beats: tuple[ScriptBeat, ...]

    @staticmethod
    def parse(raw: Any, where: str = "script") -> "Script":
        d = _obj(raw, where)
        _no_extra(d, ("case_id", "audience", "target_duration_s", "beats"), where)
        beats = [ScriptBeat.parse(b, f"{where}.beats[{i}]")
                 for i, b in enumerate(_list(d, "beats", where))]
        if not beats:
            raise SchemaError(f"{where}.beats: at least one beat is required")
        return Script(
            case_id=_str(d, "case_id", where),
            audience=_str(d, "audience", where),
            target_duration_s=_int(d, "target_duration_s", where),
            beats=tuple(beats),
        )

    @property
    def narration_text(self) -> str:
        return "\n".join(b.narration for b in self.beats)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- A3 output


@dataclass(frozen=True)
class Finding:
    id: str
    severity: str
    claim_ref: str
    evidence_ref: str
    quoted_span: str
    observation: str
    explanation: str
    recommended_correction: str

    @staticmethod
    def parse(raw: Any, where: str, *, split_observation: bool) -> "Finding":
        d = _obj(raw, where)
        allowed = ["id", "severity", "claim_ref", "evidence_ref", "quoted_span",
                   "explanation", "recommended_correction"]
        if split_observation:
            allowed.append("observation")
        _no_extra(d, allowed, where)
        fid = _str(d, "id", where)
        if not re.fullmatch(r"F[0-9]{2}", fid):
            raise SchemaError(f"{where}.id: expected Fnn, got {fid!r}")
        observation = _str(d, "observation", where) if split_observation else ""
        return Finding(
            id=fid,
            severity=_enum(_str(d, "severity", where), SEVERITIES, f"{where}.severity"),
            claim_ref=_str(d, "claim_ref", where, allow_empty=True),
            evidence_ref=_str(d, "evidence_ref", where, allow_empty=True),
            quoted_span=_str(d, "quoted_span", where),
            observation=observation,
            explanation=_str(d, "explanation", where),
            recommended_correction=_str(d, "recommended_correction", where),
        )


@dataclass(frozen=True)
class VerifierResult:
    findings: tuple[Finding, ...]
    recommendation: str
    rationale: str

    @staticmethod
    def parse(raw: Any, where: str = "verifier_result", *,
              split_observation: bool = True) -> "VerifierResult":
        d = _obj(raw, where)
        _no_extra(d, ("findings", "recommendation", "rationale"), where)
        findings = [Finding.parse(f, f"{where}.findings[{i}]",
                                  split_observation=split_observation)
                    for i, f in enumerate(_list(d, "findings", where))]
        ids = [f.id for f in findings]
        if len(set(ids)) != len(ids):
            raise SchemaError(f"{where}.findings: duplicate finding ids")
        rec = _enum(_str(d, "recommendation", where), RECOMMENDATIONS,
                    f"{where}.recommendation")
        result = VerifierResult(
            findings=tuple(findings),
            recommendation=rec,
            rationale=_str(d, "rationale", where, allow_empty=True),
        )
        # Internal consistency: the verifier may not recommend ACCEPT while
        # reporting a blocking finding. This is a schema violation, not a
        # judgement call, and it fails closed rather than being rewritten.
        if rec == "ACCEPT" and any(f.severity in ("BLOCKER", "MAJOR") for f in findings):
            raise SchemaError(
                f"{where}: ACCEPT is inconsistent with a BLOCKER/MAJOR finding")
        return result

    def blocking(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity in ("BLOCKER", "MAJOR"))


# --------------------------------------------------------------------------- gates


@dataclass(frozen=True)
class GateRecord:
    gate: str
    artifact_sha256: str
    artifact_kind: str
    approver: str
    approved_utc: str
    note: str
    # What else this approval is bound to besides the artifact text. For H1:
    # the run id, case, configuration, sample, narration hash, byte-exact run
    # record hash, canonical trajectory hash, candidate-script hash and
    # configuration-snapshot hash. For H2: archive digest, manifest digest,
    # byte size, filename, commit evidence, video hash. Covered by the
    # signature, so nothing can be swapped underneath an approval that names it.
    binding: dict = field(default_factory=dict)
    # Approval purpose and record generation. Both are inside the signed
    # payload: an approval minted for one purpose must not serve another, and
    # a record claiming an unknown schema version fails closed.
    purpose: str = ""
    gate_schema_version: str = ""
    # Expiry of the approval (freshness window chosen at approval time).
    # Signed. A record without a parsable expiry is not an approval.
    expires_utc: str = ""
    # HMAC-SHA-256 over the canonical record, keyed by the owner secret. Not
    # part of the signed payload, obviously. Empty means unsigned, which
    # `gates.verify` treats as not approved.
    signature: str = ""
    # The declared algorithm. Inside the signed payload (see gates.SIGNED_FIELDS):
    # an unsigned label could be edited to claim a different algorithm.
    signature_algorithm: str = ""

    def as_dict(self) -> dict:
        return {"gate": self.gate, "artifact_sha256": self.artifact_sha256,
                "artifact_kind": self.artifact_kind, "approver": self.approver,
                "approved_utc": self.approved_utc, "expires_utc": self.expires_utc,
                "note": self.note, "binding": dict(self.binding),
                "purpose": self.purpose,
                "gate_schema_version": self.gate_schema_version,
                "signature": self.signature,
                "signature_algorithm": self.signature_algorithm}

    @staticmethod
    def parse(raw: Any, where: str = "gate_record") -> "GateRecord":
        d = _obj(raw, where)
        allowed = ("gate", "artifact_sha256", "artifact_kind", "approver",
                   "approved_utc", "expires_utc", "note", "binding", "purpose",
                   "gate_schema_version", "signature", "signature_algorithm")
        _no_extra(d, allowed, where)
        binding = d.get("binding", {})
        if not isinstance(binding, dict):
            raise SchemaError(f"{where}.binding must be an object")
        for k, v in binding.items():
            if not isinstance(k, str) or not isinstance(v, (str, int)):
                raise SchemaError(
                    f"{where}.binding must map strings to strings or integers")
        return GateRecord(
            gate=_enum(_str(d, "gate", where), ("H1", "H2"), f"{where}.gate"),
            artifact_sha256=_str(d, "artifact_sha256", where),
            artifact_kind=_str(d, "artifact_kind", where),
            approver=_str(d, "approver", where),
            approved_utc=_str(d, "approved_utc", where),
            expires_utc=_opt_str(d, "expires_utc", where),
            note=_opt_str(d, "note", where),
            binding=dict(binding),
            purpose=_opt_str(d, "purpose", where),
            gate_schema_version=_opt_str(d, "gate_schema_version", where),
            signature=_opt_str(d, "signature", where),
            signature_algorithm=_opt_str(d, "signature_algorithm", where),
        )


# --------------------------------------------------------------------------- runs


@dataclass
class RunMetadata:
    run_id: str
    case_id: str
    config_id: str
    condition: str
    provider: str
    model: str
    mode: str
    started_utc: str = ""
    finished_utc: str = ""
    model_calls: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    wall_clock_s: float = 0.0
    correction_cycles: int = 0
    terminal_status: str = "ERROR"
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- parsing


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json_object(text: str, *, where: str) -> dict:
    """Extract exactly one JSON object from model output.

    Accepts a bare object or a single fenced block. Anything else - prose with
    two objects, a truncated object, a list at the top level - is malformed.
    There is no repair path, on purpose.
    """
    if not isinstance(text, str) or not text.strip():
        raise MalformedModelOutput(f"{where}: empty model response")
    candidates: list[str] = []
    fenced = _FENCE.findall(text)
    if len(fenced) > 1:
        raise MalformedModelOutput(f"{where}: {len(fenced)} fenced blocks; expected 1")
    if fenced:
        candidates.append(fenced[0])
    stripped = text.strip()
    if stripped.startswith("{"):
        candidates.append(stripped)
    if not candidates:
        raise MalformedModelOutput(f"{where}: no JSON object found in model response")
    for cand in candidates:
        try:
            parsed = json.loads(cand)
        except json.JSONDecodeError as exc:
            last = exc
            continue
        if not isinstance(parsed, dict):
            raise MalformedModelOutput(
                f"{where}: top-level JSON is {type(parsed).__name__}, expected object")
        return parsed
    raise MalformedModelOutput(f"{where}: JSON did not parse ({last})")


def parse_or_fail_closed(text: str, parser, where: str):
    """Parse model output; any schema problem becomes MalformedModelOutput."""
    obj = extract_json_object(text, where=where)
    try:
        return parser(obj, where)
    except MalformedModelOutput:
        raise
    except SchemaError as exc:
        raise MalformedModelOutput(f"{where}: {exc}") from exc
