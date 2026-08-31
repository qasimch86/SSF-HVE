"""Loading and validating the synthetic evaluation cases."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ssf_hve.paths import CASES_DIR
from ssf_hve.schemas import SchemaError, _list, _obj, _str


@dataclass(frozen=True)
class Detector:
    mode: str
    patterns: tuple[str, ...]
    unless: tuple[str, ...]
    document_unless: tuple[str, ...]


@dataclass(frozen=True)
class PlantedDefect:
    id: str
    defect_class: str
    description: str
    rationale: str
    expected_evidence_refs: tuple[str, ...]
    detector: Detector


@dataclass(frozen=True)
class CleanClaim:
    id: str
    text: str
    evidence_ref: str
    protected_patterns: tuple[str, ...]


@dataclass(frozen=True)
class Case:
    case_id: str
    title: str
    defect_class: str
    audience: str
    target_duration_s: int
    source: dict
    clean_claims: tuple[CleanClaim, ...]
    planted_defects: tuple[PlantedDefect, ...]
    gold_unsafe_criteria: str
    human_notes: str

    def source_text(self) -> str:
        """The packet as a researcher would receive it: a continuous document.

        Rendered as prose rather than a labelled JSON object. A labelled object
        with a `limitations` array does most of the analyst's work for free, and
        a research paper does not arrive that way. Every field is included,
        including any instruction-like text, because withholding it would make
        C10 untestable.
        """
        order = ["study_id", "design", "background", "abstract", "population",
                 "methods", "statistical_analysis", "results_table",
                 "teaching_analogy", "supplementary", "results_note",
                 "discussion", "limitations", "author_conclusion",
                 "data_availability", "data_availability_note"]
        titles = {
            "study_id": "Record", "design": "Study design",
            "background": "Background", "abstract": "Abstract",
            "population": "Population", "methods": "Methods",
            "statistical_analysis": "Statistical analysis",
            "results_table": "Results", "teaching_analogy": "Teaching note",
            "supplementary": "Supplementary materials",
            "results_note": "Note on results", "discussion": "Discussion",
            "limitations": "Limitations", "author_conclusion": "Conclusion",
            "data_availability": "Data availability",
            "data_availability_note": "Data availability",
        }
        parts: list[str] = [self.title, ""]
        keys = [k for k in order if k in self.source and self.source[k] not in (None, "", [], {})]
        keys += [k for k in self.source if k not in order and self.source[k] not in (None, "", [], {})]
        for key in keys:
            val = self.source[key]
            parts.append(titles.get(key, key.replace("_", " ").capitalize()))
            if isinstance(val, str):
                parts.append(val)
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        parts.append("  " + "; ".join(f"{k}: {v}" for k, v in item.items()))
                    else:
                        parts.append("  " + str(item))
            elif isinstance(val, dict):
                for k, v in val.items():
                    parts.append(f"  {k}: {v}")
            parts.append("")
        return "\n".join(parts).strip()


def _detector(raw: Any, where: str) -> Detector:
    d = _obj(raw, where)
    mode = _str(d, "mode", where)
    if mode not in ("match", "absent", "null_endpoint_stance"):
        raise SchemaError(
            f"{where}.mode: expected 'match', 'absent' or 'null_endpoint_stance'")
    def _pats(key: str) -> tuple[str, ...]:
        vals = d.get(key, [])
        if not isinstance(vals, list):
            raise SchemaError(f"{where}.{key}: expected list")
        for p in vals:
            if not isinstance(p, str):
                raise SchemaError(f"{where}.{key}: entries must be strings")
            try:
                re.compile(p)
            except re.error as exc:
                raise SchemaError(f"{where}.{key}: invalid regex {p!r} ({exc})")
        return tuple(vals)
    pats = _pats("patterns")
    if not pats:
        raise SchemaError(f"{where}.patterns: must not be empty")
    return Detector(mode=mode, patterns=pats,
                    unless=_pats("unless"), document_unless=_pats("document_unless"))


def parse_case(raw: Any, where: str = "case") -> Case:
    d = _obj(raw, where)
    cid = _str(d, "case_id", where)
    if not re.fullmatch(r"C[0-9]{2}", cid):
        raise SchemaError(f"{where}.case_id: expected Cnn, got {cid!r}")
    defects = []
    for i, p in enumerate(_list(d, "planted_defects", where)):
        w = f"{where}.planted_defects[{i}]"
        pd = _obj(p, w)
        defects.append(PlantedDefect(
            id=_str(pd, "id", w),
            defect_class=_str(pd, "class", w),
            description=_str(pd, "description", w),
            rationale=_str(pd, "rationale", w),
            expected_evidence_refs=tuple(_list(pd, "expected_evidence_refs", w)),
            detector=_detector(pd["detector"], f"{w}.detector"),
        ))
    if not defects:
        raise SchemaError(f"{where}: at least one planted defect is required")
    cleans = []
    for i, c in enumerate(_list(d, "clean_claims", where)):
        w = f"{where}.clean_claims[{i}]"
        cc = _obj(c, w)
        pats = tuple(_list(cc, "protected_patterns", w))
        for p in pats:
            re.compile(p)
        cleans.append(CleanClaim(id=_str(cc, "id", w), text=_str(cc, "text", w),
                                 evidence_ref=_str(cc, "evidence_ref", w),
                                 protected_patterns=pats))
    src = _obj(d.get("source"), f"{where}.source")
    return Case(
        case_id=cid,
        title=_str(d, "title", where),
        defect_class=_str(d, "defect_class", where),
        audience=_str(d, "audience", where),
        target_duration_s=int(d["target_duration_s"]),
        source=src,
        clean_claims=tuple(cleans),
        planted_defects=tuple(defects),
        gold_unsafe_criteria=_str(d, "gold_unsafe_criteria", where),
        human_notes=str(d.get("notes_for_human_reviewer", "")),
    )


def load_case(case_id: str) -> Case:
    path = CASES_DIR / f"{case_id}.json"
    if not path.exists():
        raise SystemExit(f"no such case: {case_id} (expected {path})")
    with path.open(encoding="utf-8") as fh:
        return parse_case(json.load(fh), where=case_id)


def all_case_ids() -> list[str]:
    return sorted(p.stem for p in CASES_DIR.glob("C*.json"))


def load_all() -> list[Case]:
    return [load_case(cid) for cid in all_case_ids()]
