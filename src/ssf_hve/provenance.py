"""Provenance verification.

Answers one question a judge or auditor should not have to take on trust:
*which case set, which scorer policy and which gold table produced the numbers
in `results/`, and does the repository's own history support what the files
claim about themselves?*

It checks relationships, not intentions. Where the evidence is weaker than a
claim printed in the documents, this module says so in the output rather than
leaving the reader to discover it.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ssf_hve import CASE_SET_ID, __version__
from ssf_hve.paths import (CASES_DIR, FIXTURES_DIR, GOLD_DIR, GOLD_TABLE,
                           PROMPTS_DIR, RESULTS_DIR, ROOT, RUNS_DIR)
from ssf_hve.scoring.scorer import SCORING_POLICY_VERSION

# ---------------------------------------------------------------- active binding
#
# Re-verification finding NEW-RA-01: the previous verifier proved that gold
# tables self-hash and that results carry the right stamps, but an ACTIVE case
# file could be edited — changing every score — while `verify-provenance`
# still exited 0. The binding below closes that: one self-hashed manifest
# freezes the SHA-256 of every input that can change a published number, and
# verification fails on any drift.

BINDING_FILE = ROOT / "evaluation" / "provenance_binding.json"
BINDING_SCHEMA = "ssf-hve/provenance-binding/1"

# Every file whose content can change a published score or its meaning:
# active cases (detectors), the active gold table, every prompt template,
# the scorer/normaliser/report source, case parsing and configuration, the
# deterministic checks, the fixture semantics, the fixture inventory and the
# run-record inventory.
_BOUND_GLOBS = (
    "evaluation/cases/*.json",
    "evaluation/adjudication_*.json",
    "prompts/*",
    "src/ssf_hve/__init__.py",
    "src/ssf_hve/cases.py",
    "src/ssf_hve/config.py",
    "src/ssf_hve/schemas.py",
    "src/ssf_hve/checks/deterministic.py",
    "src/ssf_hve/scoring/scorer.py",
    "src/ssf_hve/scoring/normalise.py",
    "src/ssf_hve/scoring/report.py",
    "src/ssf_hve/replay/store.py",
    "fixtures/replay/*.json",
)


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound_file_map() -> dict[str, str]:
    files: dict[str, str] = {}
    for pattern in _BOUND_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = _sha_file(path)
    files[GOLD_TABLE.relative_to(ROOT).as_posix()] = _sha_file(GOLD_TABLE)
    # Published run records: bound by content so that a rescoring, deletion or
    # addition is visible. (RUNS_DIR honours SSF_HVE_RESULTS_DIR; the binding
    # is only about the PUBLISHED records, so bind the repository's own.)
    for path in sorted((ROOT / "results" / "runs").glob("*.json")):
        files[path.relative_to(ROOT).as_posix()] = _sha_file(path)
    return files


def _results_content_sha() -> str | None:
    """Hash of results.json content, excluding only the generation timestamp.

    `score` is deterministic apart from `generated_utc`; binding the content
    minus that one field means a regenerated-but-identical results file still
    verifies, while any changed number fails.
    """
    rf = ROOT / "results" / "results.json"
    if not rf.exists():
        return None
    doc = json.loads(rf.read_text(encoding="utf-8"))
    doc.pop("generated_utc", None)
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def build_binding() -> dict:
    payload = {
        "schema": BINDING_SCHEMA,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "case_set_id": CASE_SET_ID,
        "scoring_policy_version": SCORING_POLICY_VERSION,
        "harness_version": __version__,
        "active_gold_table": GOLD_TABLE.relative_to(ROOT).as_posix(),
        "bound_files": _bound_file_map(),
        "results_content_sha256": _results_content_sha(),
        "statement": (
            "This binding freezes the SHA-256 of every active input that can "
            "change a published number: case definitions and detectors, the "
            "active gold table, prompt templates, scorer, normaliser, report "
            "generator, case parsing, configuration, deterministic checks, "
            "fixture semantics, the complete fixture inventory and the "
            "complete run-record inventory, plus the content of "
            "results.json. verify-provenance FAILS if any of them changes. "
            "Regenerating this file is a deliberate act recorded in git; see "
            "PROVENANCE.md."),
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return {"binding_sha256": hashlib.sha256(blob).hexdigest(),
            "payload": payload}


def write_binding() -> Path:
    doc = build_binding()
    with BINDING_FILE.open("w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return BINDING_FILE


def _verify_binding(r: "Report") -> None:
    r.head("0. Active provenance binding (cases, scorer, prompts, fixtures, runs)")
    if not BINDING_FILE.exists():
        r.fail("evaluation/provenance_binding.json is missing",
               "run `python -m ssf_hve bind-provenance` and commit the result")
        return
    doc = json.loads(BINDING_FILE.read_text(encoding="utf-8"))
    payload = doc.get("payload", {})
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    if hashlib.sha256(blob).hexdigest() != doc.get("binding_sha256"):
        r.fail("binding file self-hash", "the binding file itself was edited")
        return
    if payload.get("case_set_id") != CASE_SET_ID:
        r.fail("binding case_set_id", f"{payload.get('case_set_id')} vs {CASE_SET_ID}")
    if payload.get("scoring_policy_version") != SCORING_POLICY_VERSION:
        r.fail("binding scoring_policy_version",
               f"{payload.get('scoring_policy_version')} vs {SCORING_POLICY_VERSION}")
    bound = payload.get("bound_files", {})
    current = _bound_file_map()
    changed = sorted(k for k in bound if k in current and current[k] != bound[k])
    missing = sorted(k for k in bound if k not in current)
    unbound = sorted(k for k in current if k not in bound)
    for k in changed:
        r.fail(f"bound file changed: {k}",
               "an active case, prompt, scorer or evidence file no longer "
               "matches the binding")
    for k in missing:
        r.fail(f"bound file missing: {k}")
    for k in unbound:
        r.fail(f"active file not bound: {k}",
               "a new case, prompt, fixture or run record exists that no "
               "binding covers; regenerate the binding deliberately")
    res_sha = _results_content_sha()
    if payload.get("results_content_sha256") != res_sha:
        r.fail("results.json content",
               "the published results no longer match the binding "
               "(generated_utc excluded from the comparison)")
    if not (changed or missing or unbound) and payload.get("results_content_sha256") == res_sha:
        r.ok(f"all {len(bound)} bound files and results.json match the binding",
             doc["binding_sha256"][:16] + "...")


def _payload_hash(doc: dict) -> str:
    blob = json.dumps(doc["payload"], sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(("git", *args), cwd=str(ROOT), capture_output=True,
                             text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _first_commit_iso(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    out = _git("log", "--diff-filter=A", "--date=iso-strict", "--pretty=%ad", "--", rel)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    return lines[-1] if lines else ""


def _parse(ts: str):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None



def _case_from_gold(entry: dict):
    """Rebuild a Case from a gold table's own frozen copy of it.

    Used to rescore shipped run records under a superseded table's detectors,
    so that a historical claim about a number can be checked instead of
    believed. `source` is empty: scoring reads the run's narration, never the
    packet.
    """
    from ssf_hve.cases import Case, CleanClaim, Detector, PlantedDefect

    def det(d: dict) -> "Detector":
        return Detector(mode=d["mode"], patterns=tuple(d.get("patterns", ())),
                        unless=tuple(d.get("unless", ())),
                        document_unless=tuple(d.get("document_unless", ())))

    return Case(
        case_id=entry["case_id"], title=entry.get("title", ""),
        defect_class=entry.get("defect_class", ""), audience=entry.get("audience", ""),
        target_duration_s=entry.get("target_duration_s", 60), source={},
        clean_claims=tuple(
            CleanClaim(id=c["id"], text=c.get("text", ""),
                       evidence_ref=c.get("evidence_ref", ""),
                       protected_patterns=tuple(c.get("protected_patterns", ())))
            for c in entry.get("clean_claims", ())),
        planted_defects=tuple(
            PlantedDefect(id=p["id"], defect_class=p["class"],
                          description=p.get("description", ""),
                          rationale=p.get("rationale", ""),
                          expected_evidence_refs=tuple(p.get("expected_evidence_refs", ())),
                          detector=det(p["detector"]))
            for p in entry.get("planted_defects", ())),
        gold_unsafe_criteria=entry.get("gold_unsafe_criteria", ""),
        human_notes=entry.get("human_notes", ""))


def baseline_under_every_gold_table() -> list[tuple[str, int, int, list[str]]]:
    """Rescore the shipped baseline run records under each v3-family gold table.

    Returns (case_set_id, unsafe, total, unsafe_case_ids) per table, oldest
    first. Nothing is re-run: the same 30 baseline records are read each time
    and only the detectors change.
    """
    from ssf_hve.scoring import scorer

    # Deduplicated the same way `score` does it: one record per case and
    # sample, most recent wins. Globbing the directory instead would let a
    # single demonstration re-run change the denominator.
    runs = list(scorer.latest_per_case(scorer.load_runs("baseline")).values())
    out = []
    # Only tables whose detectors were written against the packets these run
    # records actually used. CS-10-v1 and CS-10-v2 detectors target earlier,
    # differently worded packets, so rescoring these runs under them would
    # produce a number that means nothing.
    order = ["CS-10-v3", "CS-10-v3.1", "CS-10-v3.2", "CS-10-v4-postaudit",
             "CS-10-v5-stance"]
    tables = {}
    for path in GOLD_DIR.glob("gold_table_*.json"):
        pl = json.loads(path.read_text(encoding="utf-8"))["payload"]
        if pl.get("case_set_id") in order:
            tables[pl["case_set_id"]] = pl
    for case_set in order:
        pl = tables.get(case_set)
        if pl is None:
            continue
        cases = {c["case_id"]: _case_from_gold(c) for c in pl["cases"]}
        unsafe = []
        for run in runs:
            cid = run["meta"]["case_id"]
            if cid not in cases:
                continue
            s = scorer.score_run(run, cases[cid])
            if s.unsafe:
                unsafe.append(s.case_id)
        out.append((case_set, len(unsafe), len(runs), unsafe))
    return out


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures: list[str] = []
        self.notes: list[str] = []

    def ok(self, label: str, detail: str = "") -> None:
        self.lines.append(f"  OK       {label}" + (f"  [{detail}]" if detail else ""))

    def fail(self, label: str, detail: str = "") -> None:
        self.lines.append(f"  MISMATCH {label}" + (f"  [{detail}]" if detail else ""))
        self.failures.append(label)

    def note(self, label: str, detail: str = "") -> None:
        self.lines.append(f"  NOTE     {label}" + (f"  [{detail}]" if detail else ""))
        self.notes.append(label)

    def head(self, title: str) -> None:
        self.lines.append("")
        self.lines.append(title)


def verify(results_file: Path | None = None) -> Report:
    r = Report()
    gold = json.loads(GOLD_TABLE.read_text(encoding="utf-8"))
    pl = gold["payload"]

    _verify_binding(r)

    r.head("1. Active gold table")
    r.lines.append(f"     file  {GOLD_TABLE.relative_to(ROOT)}")
    computed = _payload_hash(gold)
    if computed == gold["gold_table_sha256"]:
        r.ok("payload hash matches the value recorded in the file", computed[:16] + "...")
    else:
        r.fail("payload hash", f"recorded {gold['gold_table_sha256'][:16]}... "
                               f"computed {computed[:16]}...")
    r.lines.append(f"     case set             {pl.get('case_set_id')}")
    r.lines.append(f"     scoring policy       v{pl.get('scoring_policy_version', 1)}")
    r.lines.append(f"     retrospective        {bool(pl.get('retrospective', False))}")

    r.head("2. Code agrees with the active gold table")
    if CASE_SET_ID == pl.get("case_set_id"):
        r.ok("ssf_hve.CASE_SET_ID == gold table case_set_id", CASE_SET_ID)
    else:
        r.fail("ssf_hve.CASE_SET_ID", f"{CASE_SET_ID} vs {pl.get('case_set_id')}")
    gold_policy = int(pl.get("scoring_policy_version", 1))
    if SCORING_POLICY_VERSION == gold_policy:
        r.ok("scorer.SCORING_POLICY_VERSION == gold table scoring_policy_version",
             f"v{SCORING_POLICY_VERSION}")
    else:
        r.fail("SCORING_POLICY_VERSION",
               f"code v{SCORING_POLICY_VERSION} vs table v{gold_policy}")

    r.head("3. Published results were produced by this table and this policy")
    rf = results_file or (RESULTS_DIR / "results.json")
    if not rf.exists():
        r.note("results.json not present - nothing to cross-check", str(rf))
    else:
        res = json.loads(rf.read_text(encoding="utf-8"))
        if res.get("gold_table_sha256") == gold["gold_table_sha256"]:
            r.ok("results.json gold_table_sha256 == active gold table")
        else:
            r.fail("results.json gold_table_sha256",
                   "published results were scored against a different table; re-run `score`")
        bad = [cid for cid, c in res.get("configs", {}).items()
               if c.get("case_set_id") != pl.get("case_set_id")
               or int(c.get("scoring_policy_version", 1)) != gold_policy]
        if bad:
            r.fail("per-config case set / policy stamp", ", ".join(sorted(bad)))
        else:
            r.ok(f"all {len(res.get('configs', {}))} configurations stamped "
                 f"{pl.get('case_set_id')} / policy v{gold_policy}")

    r.head("4. No superseded gold table has been edited in place")
    for path in sorted(GOLD_DIR.glob("gold_table_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        if _payload_hash(doc) == doc["gold_table_sha256"]:
            r.ok(path.name)
        else:
            r.fail(path.name, "payload no longer hashes to its recorded value")

    r.head("5. What the repository history does and does not support")
    if not _git("rev-parse", "HEAD"):
        r.note("git history unavailable here (not a repository, or git absent)",
               "the commit-time comparison in this section is skipped")
    _timeline(r)
    _baseline_section(r)
    return r


def _timeline(r: Report) -> None:
    if not _git("rev-parse", "HEAD"):
        return
    r.lines.append("     Declared `created_utc` values in the gold tables are labels written")
    r.lines.append("     by their author. Commit timestamps are recorded by git. Where a")
    r.lines.append("     declared time is LATER than the commit that introduced the file, the")
    r.lines.append("     declared value cannot be a clock reading, and any ordering claim")
    r.lines.append("     resting on it is unsupported.")
    r.lines.append("")
    for path in sorted(GOLD_DIR.glob("gold_table_*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        declared = doc["payload"].get("created_utc", "")
        commit = _first_commit_iso(path)
        if not commit:
            r.note(f"{path.name}: untracked", f"declared {declared}")
            continue
        d, c = _parse(declared), _parse(commit)
        if d and c and d > c:
            r.note(f"{path.name}: declared time postdates its own commit",
                   f"declared {declared} > committed {commit}")
        else:
            r.ok(f"{path.name}: declared time is consistent with its commit",
                 f"declared {declared} <= committed {commit}")


def _baseline_section(r: Report) -> None:
    r.head("6. The baseline number under every gold table on disk "
           "(a later-code counterfactual)")
    r.lines.append("     The same 30 shipped baseline run records, rescored under each table's")
    r.lines.append("     own frozen detectors BY THE CURRENT scorer and normaliser. Nothing is")
    r.lines.append("     re-run; only the detectors change. Read it as a counterfactual under")
    r.lines.append("     today's code, NOT as the historical sequence: the historically observed")
    r.lines.append("     figures, reproduced by exact extraction of the commits themselves, are")
    r.lines.append("     2/30 at c788282 (v3.2 active, C01 s2+s3) and 0/30 from 5ecaa1b onward.")
    r.lines.append("     See PROVENANCE.md section 4.")
    r.lines.append("")
    try:
        for case_set, unsafe, total, ids in baseline_under_every_gold_table():
            detail = ", ".join(ids) if ids else "none"
            r.lines.append(f"     {case_set:22s} baseline unsafe = {unsafe}/{total}   ({detail})")
    except Exception as exc:                                   # noqa: BLE001
        r.note("baseline could not be rescored here", str(exc)[:120])


def render(r: Report) -> str:
    out = ["SSF-HVE provenance verification", "=" * 31, *r.lines, ""]
    if r.failures:
        out.append(f"RESULT: {len(r.failures)} MISMATCH(es) - "
                   "the published numbers and the files disagree.")
        for f in r.failures:
            out.append(f"  - {f}")
    else:
        out.append("RESULT: all checked relationships hold.")
    if r.notes:
        out.append("")
        out.append(f"{len(r.notes)} note(s) above are disclosures, not failures. They record")
        out.append("where a claim in the documents rests on a self-assertion rather than on")
        out.append("evidence. See PROVENANCE.md.")
    return "\n".join(out)
