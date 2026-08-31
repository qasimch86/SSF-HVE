"""H2 binding: the commit claim must be a fact about the ARCHIVE, not about
whatever checkout happens to examine it (AUD-002 / NEW-RA-04).

The bypass: `collect_binding` used to report the ambient checkout HEAD as
`git_commit` for ANY zip handed to it. An old archive examined from a newer
checkout acquired the newer commit's identity. Now the commit is reported only
when every archived file is byte-identical to that file in the commit's tree.
"""
import io
import subprocess
import zipfile
from pathlib import Path

import pytest

from ssf_hve import gates
from ssf_hve.paths import ROOT
from ssf_hve.submission import (COMMIT_NOT_ESTABLISHED, binding_statement,
                                collect_binding, commit_of_archive)


def _git(*args):
    out = subprocess.run(("git", *args), cwd=str(ROOT), capture_output=True,
                         text=True, timeout=30)
    return out.stdout.strip() if out.returncode == 0 else ""


def _head_blob(rel: str) -> bytes:
    out = subprocess.run(("git", "show", f"HEAD:{rel}"), cwd=str(ROOT),
                         capture_output=True, timeout=30)
    assert out.returncode == 0, f"HEAD:{rel} unreadable"
    return out.stdout


needs_git = pytest.mark.skipif(not _git("rev-parse", "HEAD"),
                               reason="no git history available")


def _full_submission_zip(tmp_path) -> "Path":
    """The complete submission set of HEAD, built from the COMMIT's blobs —
    deterministic whatever the worktree looks like."""
    import io
    import tarfile

    from ssf_hve.packaging import select_relpaths
    out = subprocess.run(("git", "archive", "--format=tar", "HEAD"),
                         cwd=str(ROOT), capture_output=True, timeout=120)
    assert out.returncode == 0
    tf = tarfile.open(fileobj=io.BytesIO(out.stdout))
    blobs = {m.name: tf.extractfile(m).read()
             for m in tf.getmembers() if m.isfile()}
    selected = select_relpaths(blobs)
    z = tmp_path / "full.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for rel in sorted(selected):
            zf.writestr(f"ssf-hve/{rel}", blobs[rel])
    return z


def test_selection_includes_direct_children_of_doublestar_patterns():
    """The exact 17-file class the set-equality check caught: `**/*` must
    match direct children (pathlib semantics), and `*` must not cross `/`."""
    from ssf_hve.packaging import select_relpaths
    got = select_relpaths([
        "src/ssf_hve/cli.py",                 # direct child under **/*.py
        "src/ssf_hve/ui/app.py",              # nested child
        "samples/H1_CANDIDATE_script.txt",    # direct child under samples/**/*
        "prompts/a1_analyst.md",
        "prompts/nested/should_not_match.md", # single * must not cross /
        "results/gates/H1_x.json",            # denied
        "dist/anything.zip",                  # denied
    ])
    assert "src/ssf_hve/cli.py" in got
    assert "src/ssf_hve/ui/app.py" in got
    assert "samples/H1_CANDIDATE_script.txt" in got
    assert "prompts/a1_analyst.md" in got
    assert "prompts/nested/should_not_match.md" not in got
    assert "results/gates/H1_x.json" not in got
    assert "dist/anything.zip" not in got


@needs_git
def test_the_selection_rules_agree_between_tree_and_working_directory():
    """select_relpaths over the HEAD tree must equal collect() over the
    working directory whenever the worktree is clean — the two views of the
    same allow/deny rules cannot be allowed to drift apart silently."""
    import io
    import tarfile

    from ssf_hve.packaging import collect, select_relpaths
    if _git("status", "--porcelain"):
        pytest.skip("worktree not clean; comparison undefined")
    out = subprocess.run(("git", "archive", "--format=tar", "HEAD"),
                         cwd=str(ROOT), capture_output=True, timeout=120)
    tf = tarfile.open(fileobj=io.BytesIO(out.stdout))
    tree_sel = select_relpaths(m.name for m in tf.getmembers() if m.isfile())
    work_sel = {p.relative_to(ROOT).as_posix() for p in collect()}
    assert tree_sel == work_sel


@needs_git
def test_only_the_complete_byte_identical_submission_set_gets_the_commit(tmp_path):
    z = _full_submission_zip(tmp_path)
    got = commit_of_archive(z)
    assert got["archive_commit"] == _git("rev-parse", "HEAD")
    assert "set equality verified" in got["archive_commit_evidence"]


@needs_git
def test_a_strict_subset_archive_does_not_acquire_the_commit(tmp_path):
    """FV-002, verbatim: byte-identical entries, but only a subset of the
    submission set. The commit identity must be refused, naming the gap."""
    z = tmp_path / "subset.zip"
    with zipfile.ZipFile(z, "w") as zf:
        for rel in ("README.md", "pyproject.toml"):
            zf.writestr(f"ssf-hve/{rel}", _head_blob(rel))
    got = commit_of_archive(z)
    assert got["archive_commit"] == COMMIT_NOT_ESTABLISHED
    assert "missing" in got["archive_commit_evidence"]
    assert "never acquires a commit identity" in got["archive_commit_evidence"]


@needs_git
def test_an_archive_with_different_content_does_not_acquire_the_commit(tmp_path):
    """The AUD-002 case: full set, but one file's bytes are NOT this commit's."""
    z = _full_submission_zip(tmp_path)
    # tamper one entry, keep the set identical
    import shutil
    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(tampered, "w") as dst:
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == "ssf-hve/README.md":
                data += b"\n# a line HEAD does not have\n"
            dst.writestr(info.filename, data)
    got = commit_of_archive(tampered)
    assert got["archive_commit"] == COMMIT_NOT_ESTABLISHED
    assert "differing in content" in got["archive_commit_evidence"]
    binding = collect_binding(tampered)
    assert binding["archive_commit"] == COMMIT_NOT_ESTABLISHED
    # the checkout HEAD may appear, but only under its honest label
    assert binding["checkout_head"] == _git("rev-parse", "HEAD")
    stmt = binding_statement(binding)
    assert COMMIT_NOT_ESTABLISHED in stmt
    assert "not a claim about how the archive" in stmt


@needs_git
def test_a_renamed_entry_blocks_the_commit_claim(tmp_path):
    z = _full_submission_zip(tmp_path)
    renamed = tmp_path / "renamed.zip"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(renamed, "w") as dst:
        for info in src.infolist():
            name = info.filename
            if name == "ssf-hve/README.md":
                name = "ssf-hve/READ_ME.md"
            dst.writestr(name, src.read(info.filename))
    got = commit_of_archive(renamed)
    assert got["archive_commit"] == COMMIT_NOT_ESTABLISHED
    ev = got["archive_commit_evidence"]
    assert "missing" in ev and "not in the commit" in ev


@needs_git
def test_an_extra_file_blocks_the_commit_claim(tmp_path):
    z = _full_submission_zip(tmp_path)
    extra = tmp_path / "extra.zip"
    with zipfile.ZipFile(z) as src, zipfile.ZipFile(extra, "w") as dst:
        for info in src.infolist():
            dst.writestr(info.filename, src.read(info.filename))
        dst.writestr("ssf-hve/NOT_IN_ANY_COMMIT.txt", b"surprise")
    got = commit_of_archive(extra)
    assert got["archive_commit"] == COMMIT_NOT_ESTABLISHED
    assert "not in the commit" in got["archive_commit_evidence"]


def test_h2_statement_changes_when_the_archive_changes(tmp_path, monkeypatch):
    monkeypatch.setenv(gates.SECRET_ENV, "test-only-secret")
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("ssf-hve/x.txt", b"one")
    s1 = binding_statement(collect_binding(z))
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("ssf-hve/x.txt", b"two")
    s2 = binding_statement(collect_binding(z))
    assert gates.artifact_sha256(s1) != gates.artifact_sha256(s2)
