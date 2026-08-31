"""Nothing in the repository may carry a credential, a private path or
commercial source. This test is also the pre-submission scanner."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# `.workspace/` is the owner's local scratch directory: git-ignored, excluded
# from the archive denylist, and never shipped. Scanning it made this test fail
# in any working tree that had one, while telling a reader nothing about what
# the submission contains. `test_the_scanner_covers_exactly_what_ships` keeps
# that skip honest by asserting the directory really is excluded from both.
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache",
             "node_modules", ".workspace", "dist"}

SECRET_PATTERNS = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "provider API key"),
    (re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"(?i)\b(password|passwd|secret_key|client_secret)\s*[:=]\s*"
                r"['\"][^'\"\s]{6,}['\"]"), "hard-coded credential"),
    (re.compile(r"postgres(?:ql)?://[^\s'\"]*:[^\s'\"@]+@"), "database URL with password"),
]

# Marks of the pre-existing commercial tree. None may appear here.
COMMERCIAL_MARKERS = [
    "app/services/review_agent", "app/ssf/definitions", "dev-data/recovered.db",
    "SSF-00", "SSF-13", "BRD-SSF-001", "PKG-R1-SSF-001", "RTM-SSF-001",
    "WeliAI", "Spyder Science",
]

PRIVATE_PATH = re.compile(r"[A-Za-z]:\\\\Users\\\\|/Users/[a-z]|/home/[a-z]+/mnt/")


def repo_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix in {".png", ".jpg", ".mp4", ".wav", ".zip", ".pdf"}:
            continue
        yield p


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return ""


def test_no_credentials_anywhere():
    hits = []
    for p in repo_files():
        text = read(p)
        for pattern, label in SECRET_PATTERNS:
            if pattern.search(text):
                hits.append(f"{p.relative_to(ROOT)}: {label}")
    assert not hits, hits


def test_no_env_files_are_tracked():
    offenders = [p.relative_to(ROOT) for p in repo_files()
                 if p.name == ".env" or p.name.startswith(".env.")]
    assert not offenders, offenders


def test_no_commercial_source_markers():
    hits = []
    for p in repo_files():
        if p.name in {"test_secrets.py", "PRE_EXISTING_WORK.md",
                      "SCOPE_FREEZE.md", "IMPROVEMENT_CHANGELOG.md", "README.md"}:
            continue          # these name the boundary on purpose, in prose
        text = read(p)
        for marker in COMMERCIAL_MARKERS:
            if marker in text:
                hits.append(f"{p.relative_to(ROOT)}: {marker}")
    assert not hits, hits


def test_no_private_filesystem_paths_leak():
    hits = []
    for p in repo_files():
        if p.name == "test_secrets.py":
            continue
        if PRIVATE_PATH.search(read(p)):
            hits.append(str(p.relative_to(ROOT)))
    assert not hits, hits


def test_fixtures_carry_no_secrets():
    from ssf_hve.paths import FIXTURES_DIR
    for p in sorted(FIXTURES_DIR.glob("*.json")):
        text = read(p)
        for pattern, label in SECRET_PATTERNS:
            assert not pattern.search(text), f"{p.name}: {label}"


def test_the_scanner_covers_exactly_what_ships():
    """A skip is only safe if the skipped directory cannot reach a judge.

    This test exists because the previous version of SKIP_DIRS was chosen for
    convenience. `.workspace/` and `dist/` are skipped above; that is defensible
    only while both are excluded from git AND from the submission archive, so
    both facts are asserted here rather than assumed.
    """
    from ssf_hve.packaging import ALLOWLIST, DENYLIST, collect

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip().rstrip("/") for line in gitignore if line.strip()}
    for skipped in (".workspace", "dist"):
        assert skipped in ignored, f"{skipped}/ is scanned by nothing and tracked by git"
        assert any(skipped in pattern for pattern in DENYLIST), (
            f"{skipped}/ is skipped by the scanner but not denied by the packager")

    shipped = {p.relative_to(ROOT).as_posix() for p in collect()}
    for rel in shipped:
        first = rel.split("/")[0]
        assert first not in SKIP_DIRS, (
            f"{rel} ships but the secret scanner skips its directory")


def test_every_shipped_file_is_scanned():
    """The scanner must see at least everything the archive contains."""
    from ssf_hve.packaging import collect

    scanned = {p.relative_to(ROOT).as_posix() for p in repo_files()}
    shipped = {p.relative_to(ROOT).as_posix() for p in collect()}
    binary = {p for p in shipped
              if Path(p).suffix in {".png", ".jpg", ".mp4", ".wav", ".zip", ".pdf"}}
    missed = shipped - scanned - binary
    assert not missed, f"shipped but never scanned for secrets: {sorted(missed)[:10]}"
