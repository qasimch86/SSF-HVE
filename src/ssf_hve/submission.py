"""The H2 gate: approving one exact submission package.

H1 approves one run's candidate script. H2 has a harder job: the thing being
approved is a zip file, and a zip file can be rebuilt between the moment a
person reads it and the moment it is uploaded. An approval that says only
"the owner approved a submission" is worth nothing.

So the approved artifact here is not the archive; it is a **binding statement**
naming everything that identifies the archive at once:

  * the archive filename, byte size and SHA-256
  * the manifest digest — a hash of the arcnames and file contents, which is
    stable across rebuilds and changes if any shipped file changes
  * commit evidence for the archive's CONTENT (see below)
  * the SHA-256 of the video file, when one is submitted alongside

**Commit evidence, stated precisely.** An earlier version of this module put
the ambient checkout HEAD into the binding as "the commit the archive was
built from". That is not a fact about the archive — an old zip examined from
a newer checkout would have acquired the newer commit's identity
(re-verification finding AUD-002 / NEW-RA-04). What is provable is whether
every file inside the archive is byte-identical to that file in a commit's
tree. `commit_of_archive` performs that comparison against the checkout HEAD
and reports `archive_commit` ONLY when every archived file matches; otherwise
it reports `not established` with the mismatch count. The checkout HEAD is
still recorded separately, labelled as what it is: the state of the checkout
performing the check, not a property of the archive.

The statement is rendered as text, hashed, and that hash is what the person
types APPROVE against. Change any component and the hash changes, so the
approval no longer applies — which is the property the gate needs.

Nothing here uploads, publishes or submits anything.
"""
from __future__ import annotations

import hashlib
import subprocess
import tempfile
import zipfile
from pathlib import Path

from ssf_hve.paths import ROOT

BINDING_VERSION = "ssf-hve/h2-binding/v2"

COMMIT_NOT_ESTABLISHED = "not established from archive contents"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        out = subprocess.run(("git", *args), cwd=str(ROOT), capture_output=True,
                             text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _zip_entry_hashes(archive: Path) -> dict[str, str]:
    with zipfile.ZipFile(archive) as z:
        return {info.filename: hashlib.sha256(z.read(info.filename)).hexdigest()
                for info in z.infolist() if not info.is_dir()}


def _head_tree_hashes(commit: str) -> dict[str, str] | None:
    """Entry hashes of `git archive <commit>` with the ssf-hve/ prefix, or None."""
    with tempfile.TemporaryDirectory(prefix="ssf-hve-h2-") as td:
        out = Path(td) / "head.zip"
        try:
            proc = subprocess.run(
                ("git", "archive", "--format=zip", "--prefix=ssf-hve/",
                 "-o", str(out), commit),
                cwd=str(ROOT), capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0 or not out.exists():
            return None
        return _zip_entry_hashes(out)


def commit_of_archive(archive: Path) -> dict:
    """Evidence, not assertion: is this archive EXACTLY a commit's submission set?

    Final verification finding FV-002: a subset check ("every archived file
    matches the tree") let a one-file ZIP acquire the full commit's identity.
    The claim now requires SET EQUALITY: the archive's entry set must equal
    the submission set of the commit's tree — the tracked files selected by
    the packaging allow/deny rules — and every entry must be byte-identical.
    Missing files, extra files, renamed entries and changed bytes all block
    the claim, and the evidence sentence says which.

    Returns:
      archive_commit           the commit id, only under set equality;
                               otherwise COMMIT_NOT_ESTABLISHED or
                               "unavailable" (no git history here).
      archive_commit_evidence  one sentence saying what was compared.
    """
    from ssf_hve.packaging import select_relpaths

    head = _git("rev-parse", "HEAD")
    if not head:
        return {"archive_commit": "unavailable",
                "archive_commit_evidence":
                    "git history is not available here, so no commit claim is made"}
    entries = _zip_entry_hashes(archive)
    tree = _head_tree_hashes(head)
    if tree is None:
        return {"archive_commit": "unavailable",
                "archive_commit_evidence":
                    "the checkout tree could not be read, so no commit claim is made"}
    prefix = "ssf-hve/"
    expected = {prefix + rel for rel in
                select_relpaths(n[len(prefix):] for n in tree)}
    missing = sorted(expected - entries.keys())
    extra = sorted(entries.keys() - expected)
    changed = sorted(n for n in entries.keys() & expected
                     if tree.get(n) != entries[n])
    if not (missing or extra or changed):
        return {"archive_commit": head,
                "archive_commit_evidence":
                    (f"set equality verified: the archive's {len(entries)} "
                     f"entries are exactly the submission set of {head[:12]} "
                     "and every one is byte-identical to that tree")}
    parts = []
    if missing:
        parts.append(f"{len(missing)} expected file(s) missing (first: {missing[0]})")
    if extra:
        parts.append(f"{len(extra)} file(s) not in the commit's submission set "
                     f"(first: {extra[0]})")
    if changed:
        parts.append(f"{len(changed)} file(s) differing in content "
                     f"(first: {changed[0]})")
    return {"archive_commit": COMMIT_NOT_ESTABLISHED,
            "archive_commit_evidence":
                (f"against the submission set of the checkout HEAD {head[:12]}: "
                 + "; ".join(parts)
                 + ". A partial or altered archive never acquires a commit identity.")}


def collect_binding(archive: Path, video: Path | None = None) -> dict:
    """Everything the H2 approval is bound to. Reads; changes nothing."""
    from ssf_hve.packaging import manifest_digest_of_zip

    if not archive.exists():
        raise FileNotFoundError(f"no archive at {archive}")
    head = _git("rev-parse", "HEAD")
    binding = {
        "binding_version": BINDING_VERSION,
        "archive_filename": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha256_file(archive),
        "manifest_sha256": manifest_digest_of_zip(archive),
        # The state of the checkout PERFORMING this check. Informational; it
        # says nothing about where the archive came from.
        "checkout_head": head or "unavailable",
        "checkout_tree_state": (("dirty" if _git("status", "--porcelain")
                                 else "clean") if head else "unavailable"),
    }
    binding.update(commit_of_archive(archive))
    if video is not None:
        if not video.exists():
            raise FileNotFoundError(f"no video at {video}")
        binding["video_filename"] = video.name
        binding["video_bytes"] = video.stat().st_size
        binding["video_sha256"] = _sha256_file(video)
    return binding


def binding_statement(binding: dict) -> str:
    """The exact text a person approves. Deterministic given the binding."""
    lines = [
        "SSF-HVE submission package approval (gate H2)",
        "=" * 45,
        "",
        "By approving this statement I approve THIS package and no other.",
        "Any change to the archive, its contents, or the video submitted",
        "with it produces a different statement and a different hash, and",
        "this approval will not apply to it. The commit line below is a",
        "verified content comparison, not a claim about how the archive",
        "was built; 'not established' means exactly that.",
        "",
    ]
    for key in sorted(binding):
        lines.append(f"{key} = {binding[key]}")
    lines.append("")
    return "\n".join(lines)


def statement_sha256(binding: dict) -> str:
    return hashlib.sha256(binding_statement(binding).encode("utf-8")).hexdigest()
