"""The engineering documents must cite things that exist.

A traceability matrix nobody executes is decoration. It is written once, the
code moves, and within a week it names tests that were renamed and modules that
were split — while still looking authoritative. That failure mode is worse than
having no matrix, because a reader trusts it.

So the matrix is parsed. Every `test_*` name and every `module.py` reference in
`docs/` must resolve to something in this repository, and every requirement the
SRD defines must appear in the RTM. If a test is renamed, this fails and names
the row that has to change.
"""
import re
from pathlib import Path

import pytest

from ssf_hve.paths import ROOT

DOCS = ROOT / "docs"
RTM = DOCS / "RTM-HVE-001_Requirements_Traceability_Matrix.md"
SRD = DOCS / "SRD-HVE-001_Software_Requirements.md"

# `test_foo` in prose or backticks, anywhere in the document set.
_TEST_NAME = re.compile(r"\b(test_[a-z0-9_]+)\b")
# A module path like `scoring/scorer.py` or `cli.py`, always inside backticks.
_MODULE = re.compile(r"`([a-z0-9_]+(?:/[a-z0-9_]+)*\.py)`")
# Requirement identifiers.
_REQ = re.compile(r"\b((?:FR|NFR|SEC|CON|BO|BC|BA)-\d{3})\b")


def _docs():
    return sorted(p for p in DOCS.rglob("*.md"))


def _defined_test_names() -> set[str]:
    """Every test function, plus every test module's stem.

    Documents legitimately cite both: a function when they mean one assertion,
    a module when they mean a suite. Both must still exist.
    """
    names: set[str] = set()
    for path in (ROOT / "tests").glob("test_*.py"):
        names.add(path.stem)
        names.update(re.findall(r"^def (test_[a-zA-Z0-9_]+)",
                                path.read_text(encoding="utf-8"), re.M))
    return names


def _source_modules() -> set[str]:
    """Every module, by every suffix a document might reasonably cite."""
    out: set[str] = set()
    for path in (ROOT / "src" / "ssf_hve").rglob("*.py"):
        rel = path.relative_to(ROOT / "src" / "ssf_hve").as_posix()
        out.add(rel)                       # scoring/scorer.py
        out.add(path.name)                 # scorer.py
    for path in (ROOT / "tests").glob("*.py"):
        out.add(path.name)
        out.add(f"tests/{path.name}")
    out.add("pyproject.toml")
    return out


def test_the_docs_directory_is_present_and_indexed():
    assert DOCS.is_dir(), "docs/ is missing"
    assert (DOCS / "README.md").exists(), "docs/README.md is the index; it must exist"
    index = (DOCS / "README.md").read_text(encoding="utf-8")
    for doc in _docs():
        if doc.parent == DOCS and doc.name != "README.md":
            assert doc.name in index, f"{doc.name} is not listed in docs/README.md"


def test_every_test_cited_by_the_documents_exists():
    """A renamed test must not leave a document quietly lying about coverage."""
    defined = _defined_test_names()
    missing = {}
    for doc in _docs():
        cited = set(_TEST_NAME.findall(doc.read_text(encoding="utf-8")))
        gone = sorted(cited - defined)
        if gone:
            missing[doc.relative_to(ROOT).as_posix()] = gone
    assert not missing, (
        "documents cite tests that do not exist (rename the citation, or "
        f"restore the test): {missing}")


def test_every_module_cited_by_the_documents_exists():
    known = _source_modules()
    missing = {}
    for doc in _docs():
        cited = set(_MODULE.findall(doc.read_text(encoding="utf-8")))
        gone = sorted(c for c in cited if c not in known
                      and c.removeprefix("src/ssf_hve/") not in known)
        if gone:
            missing[doc.relative_to(ROOT).as_posix()] = gone
    assert not missing, f"documents cite modules that do not exist: {missing}"


def test_every_requirement_the_srd_defines_appears_in_the_rtm():
    """A requirement with no row has no traceability, whatever the SRD says."""
    srd = SRD.read_text(encoding="utf-8")
    rtm = RTM.read_text(encoding="utf-8")
    # Requirements are *defined* in the SRD in bold or in a table's first cell.
    defined = set(re.findall(r"\*\*((?:FR|NFR|SEC|CON)-\d{3})", srd))
    defined |= set(re.findall(r"^\| \*\*((?:FR|NFR|SEC|CON)-\d{3})\*\*", srd, re.M))
    assert len(defined) >= 40, f"only {len(defined)} requirements parsed; the parser is broken"
    traced = set(_REQ.findall(rtm))
    untraced = sorted(defined - traced)
    assert not untraced, f"SRD requirements with no RTM row: {untraced}"


def test_the_rtm_traces_no_requirement_the_srd_does_not_define():
    srd_ids = set(_REQ.findall(SRD.read_text(encoding="utf-8")))
    rtm_ids = set(_REQ.findall(RTM.read_text(encoding="utf-8")))
    invented = sorted(i for i in rtm_ids - srd_ids
                      if i.startswith(("FR-", "NFR-", "SEC-", "CON-")))
    assert not invented, f"RTM traces requirements the SRD does not define: {invented}"


def test_the_unenforced_boundaries_are_stated_in_both_documents():
    """The honest gaps must not be quietly dropped from one document.

    FR-006, FR-017, FR-026 and SEC-003 describe boundaries nothing enforces.
    They are the rows a reader most needs, and the easiest to lose in an edit.
    """
    srd = SRD.read_text(encoding="utf-8")
    rtm = RTM.read_text(encoding="utf-8")
    for req in ("FR-006", "FR-017", "FR-026", "SEC-003"):
        assert req in srd and req in rtm, f"{req} vanished from a document"
    for doc, text in (("SRD", srd), ("RTM", rtm)):
        assert "unenforced" in text.lower(), (
            f"the {doc} no longer collects the unenforced boundaries in one place")


def test_the_documents_declare_that_they_are_retrospective():
    """Every document must carry its provenance statement, or inherit one.

    These are as-built documents. A reader who opens one directly, without the
    index, must still be told that it was written after the code rather than
    before it. This is the same class of claim the project has already had to
    withdraw elsewhere, so it is pinned rather than trusted.

    Each top-level document states it on its own front page. The ADRs inherit
    the statement in their index, which is therefore required to carry one.
    """
    adr_index = (DOCS / "adr" / "README.md").read_text(encoding="utf-8")
    assert "Provenance" in adr_index, (
        "the ADR index no longer carries the provenance statement the ADRs "
        "inherit; either restore it or give every ADR its own")

    missing = []
    for doc in _docs():
        if doc.parent.name == "adr" and doc.name != "README.md":
            continue                       # inherits the index statement
        text = doc.read_text(encoding="utf-8")
        if "Provenance" not in text and "as-built" not in text.lower():
            missing.append(doc.relative_to(ROOT).as_posix())
    assert not missing, f"documents with no provenance statement: {missing}"


def test_every_adr_is_listed_in_the_adr_index():
    adr_dir = DOCS / "adr"
    index = (adr_dir / "README.md").read_text(encoding="utf-8")
    for path in sorted(adr_dir.glob("ADR-*.md")):
        assert path.name in index, f"{path.name} is not in the ADR index"


def test_the_documents_ship_in_the_archive():
    """Documentation a judge cannot open is not documentation."""
    from ssf_hve.packaging import collect

    shipped = {p.relative_to(ROOT).as_posix() for p in collect()}
    for doc in _docs():
        rel = doc.relative_to(ROOT).as_posix()
        assert rel in shipped, f"{rel} is not in the submission archive"
