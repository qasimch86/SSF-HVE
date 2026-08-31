"""Submission archive: built from an explicit allowlist, then inspected.

A folder zip ships whatever happens to be in the folder. This builds the archive
from a list of things we intend to ship, refuses on anything that looks like a
credential, and prints the complete file list so a person can read it before the
archive goes anywhere. Nothing here uploads, publishes or submits.
"""
from __future__ import annotations

import fnmatch
import hashlib
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ssf_hve.paths import ROOT

# Everything the submission is intended to contain. Nothing else is included,
# whatever else happens to be sitting in the working directory.
ALLOWLIST = [
    "README.md", "EVAL_PROTOCOL.md", "IMPROVEMENT_CHANGELOG.md",
    "REPRODUCTION.md", "PRE_EXISTING_WORK.md", "SCOPE_FREEZE.md",
    "PROVENANCE.md",
    # The engineering document set. Documentation a judge cannot open is not
    # documentation; tests/test_rtm.py asserts every file here ships.
    "docs/*.md",
    "docs/adr/*.md",
    "pyproject.toml", ".gitignore", ".gitattributes",
    "src/ssf_hve/**/*.py",
    "prompts/*",
    "evaluation/cases/*.json",
    "evaluation/gold/*",
    "evaluation/provenance_binding.json",
    "evaluation/adjudication_*.json",
    "evaluation/archive/**/*",
    "fixtures/replay/*.json",
    "results/RESULTS.md", "results/results.json",
    "results/RESULTS_baseline_only.md",
    "results/runs/*.json",
    "results/archive/**/*",
    "trajectories/solution/*",
    "trajectories/coding/*",
    "samples/**/*",
    "tests/*.py",
]

# Refused outright, even if some pattern above would otherwise match.
DENYLIST = [
    "**/.env", "**/.env.*", "**/*.key", "**/*.pem", "**/secrets.*",
    "**/credentials*", "**/.venv/**", "**/venv/**", "**/__pycache__/**",
    "**/.pytest_cache/**", "**/.git/**", "**/.workspace/**",
    # An archive must never contain a previous archive, and dist/ is where they
    # are written. Denied explicitly rather than relying on the allowlist's
    # silence; tests/test_secrets.py asserts the deny exists.
    "dist/**", "**/dist/**", "**/*.zip",
    "**/results/pending_capture/**", "**/results/gates/**", "**/tmp/**",
]

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "provider API key"),
    (re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"postgres(?:ql)?://[^\s'\"]*:[^\s'\"@]+@"), "database URL with password"),
]
PRIVATE_PATH = re.compile(r"[A-Za-z]:\\Users\\|/Users/[a-z]|/home/[a-z]+/mnt/|/sessions/")


@dataclass
class PackageReport:
    files: list[Path] = field(default_factory=list)
    refused: list[str] = field(default_factory=list)
    archive: Path | None = None
    sha256: str = ""
    manifest_sha256: str = ""
    total_bytes: int = 0

    @property
    def ok(self) -> bool:
        return not self.refused


MANIFEST_DOMAIN = "ssf-hve/archive-manifest/v1"


def manifest_digest(entries: "list[tuple[str, bytes]]") -> str:
    """A digest of the archive's CONTENT, independent of how it was zipped.

    The archive SHA-256 covers the zip file, so it changes with compression
    level, entry order and embedded timestamps. This covers only the arcnames
    and the bytes under them, so two archives built from identical content
    agree here even when their zip bytes differ - and any change to a shipped
    file changes it, which is what an approval needs to be bound to.
    """
    h = hashlib.sha256()
    h.update(MANIFEST_DOMAIN.encode("utf-8"))
    for name, data in sorted(entries):
        h.update(b"\x00")
        h.update(name.encode("utf-8"))
        h.update(b"\x00")
        h.update(hashlib.sha256(data).hexdigest().encode("ascii"))
    return h.hexdigest()


def manifest_digest_of_zip(archive: Path) -> str:
    """Recompute the manifest digest by reading a built archive."""
    with zipfile.ZipFile(archive) as z:
        entries = [(info.filename, z.read(info.filename))
                   for info in z.infolist() if not info.is_dir()]
    return manifest_digest(entries)


def _denied(rel: str) -> bool:
    return any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch("/" + rel, pat)
               for pat in DENYLIST)


def _glob_to_regex(pattern: str):
    """Translate one ALLOWLIST glob to a regex with PATHLIB semantics.

    fnmatch is the wrong tool here: its `*` crosses `/` and it reads `**/`
    as requiring a directory level, so `samples/**/*` missed the direct
    children of samples/ that `Path.glob` includes — 17 files, caught by the
    H2 set-equality check the moment it was turned on. Here `**/` matches
    zero or more directory levels and `*` stays within one segment, exactly
    as `Path.glob` behaves for these patterns.
    """
    parts = pattern.split("/")
    out = []
    for i, part in enumerate(parts):
        if part == "**":
            out.append("(?:[^/]+/)*")
            continue
        seg = "".join("[^/]*" if ch == "*" else
                      "[^/]" if ch == "?" else re.escape(ch)
                      for ch in part)
        out.append(seg + ("/" if i < len(parts) - 1 else ""))
    return re.compile("^" + "".join(out) + "$")


_ALLOW_REGEXES = [_glob_to_regex(p) for p in ALLOWLIST]


def select_relpaths(relpaths) -> set[str]:
    """The submission set among `relpaths`, by the same allow/deny rules.

    A pure function over path strings so the SAME selection can be applied to
    a git tree listing (H2 commit evidence) as to the working directory.
    Tests assert it agrees with `collect()` and includes/excludes the exact
    cases the fnmatch version got wrong.
    """
    selected = set()
    for rel in relpaths:
        rel = rel.replace("\\", "/")
        if _denied(rel):
            continue
        if any(rx.match(rel) for rx in _ALLOW_REGEXES):
            selected.add(rel)
    return selected


def collect(root: Path | None = None) -> list[Path]:
    root = root or ROOT
    seen: dict[str, Path] = {}
    for pattern in ALLOWLIST:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if _denied(rel):
                continue
            seen[rel] = path
    return [seen[k] for k in sorted(seen)]


def inspect(files: list[Path], root: Path | None = None) -> list[str]:
    """Read every file that is about to ship. Refuse on anything alarming."""
    root = root or ROOT
    problems: list[str] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                problems.append(f"{rel}: {label}")
        if rel not in ("tests/test_secrets.py", "src/ssf_hve/packaging.py"):
            if PRIVATE_PATH.search(text):
                problems.append(f"{rel}: private filesystem path")
    return problems


def build(out_path: Path, root: Path | None = None,
          dry_run: bool = False) -> PackageReport:
    root = root or ROOT
    files = collect(root)
    report = PackageReport(files=files)
    report.refused = inspect(files, root)
    report.total_bytes = sum(f.stat().st_size for f in files)
    if report.refused or dry_run:
        return report
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            z.write(f, arcname=f"ssf-hve/{f.relative_to(root).as_posix()}")
    report.archive = out_path
    report.sha256 = hashlib.sha256(out_path.read_bytes()).hexdigest()
    report.manifest_sha256 = manifest_digest(
        [(f"ssf-hve/{f.relative_to(root).as_posix()}", f.read_bytes()) for f in files])
    return report
