"""Every count printed in a judge-facing document must match the repository.

A stale count is a small lie that costs a reader's trust in the large ones. The
documents had drifted: 140 run records when there are 100, six trajectories when
there are eight, 98 tests, five prompts, four gold tables. None of it changed a
result; all of it was wrong on the page.

Counting by hand is what produced the drift, so this counts from the filesystem
and fails when a document disagrees. Re-verification finding NEW-RA-06 showed
the first version of this file checked only selected documents, which let stale
claims survive in the ones it skipped — so the final test below scans EVERY
shipped document for the count-shaped claims and validates each occurrence.
"""
import glob
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from ssf_hve.paths import ROOT


def _read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


# --------------------------------------------------------------- the evidence

def count_run_records() -> int:
    return len(list((ROOT / "results" / "runs").glob("*.json")))


def count_fixtures() -> int:
    return len(list((ROOT / "fixtures" / "replay").glob("*.json")))


def count_cases() -> int:
    return len(list((ROOT / "evaluation" / "cases").glob("C*.json")))


def count_gold_tables() -> int:
    return len(list((ROOT / "evaluation" / "gold").glob("gold_table_*.json")))


def count_prompts() -> int:
    return len([p for p in (ROOT / "prompts").iterdir() if p.is_file()])


def count_trajectories() -> int:
    d = ROOT / "trajectories" / "solution"
    return len({p.stem for p in d.glob("*") if p.suffix in (".jsonl", ".md")})


def count_test_files() -> int:
    return len(list((ROOT / "tests").glob("test_*.py")))


def count_tests() -> int:
    """Ask pytest, so the number cannot drift from what actually runs."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", str(ROOT / "tests")],
        capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    total = 0
    for line in out.stdout.splitlines():
        m = re.match(r"^tests[/\\]test_\w+\.py: (\d+)$", line.strip())
        if m:
            total += int(m.group(1))
    assert total, f"could not collect tests:\n{out.stdout[-2000:]}\n{out.stderr[-2000:]}"
    return total


# --------------------------------------------------------------- the claims

def test_run_record_count_is_stated_correctly():
    n = count_run_records()
    assert f"{n} run records" in _read("PRE_EXISTING_WORK.md"), (
        f"there are {n} run records; PRE_EXISTING_WORK.md says otherwise")


def test_fixture_count_is_stated_correctly():
    n = count_fixtures()
    for doc in ("REPRODUCTION.md", "README.md"):
        text = _read(doc)
        if "fixture" not in text:
            continue
        assert str(n) in text, f"{doc} does not state the real fixture count ({n})"


def test_gold_table_count_is_stated_correctly():
    n = count_gold_tables()
    words = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
    text = _read("PRE_EXISTING_WORK.md") + _read("README.md")
    assert f"{words.get(n, str(n))} dated gold tables" in text, (
        f"there are {n} gold tables; the documents say otherwise")


def test_trajectory_count_is_stated_correctly():
    n = count_trajectories()
    words = {6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}
    word = words.get(n, str(n))
    assert f"{word} solution trajectories" in _read("PRE_EXISTING_WORK.md").lower(), (
        f"there are {n} solution trajectories")
    assert f"{word} representative" in _read("REPRODUCTION.md").lower(), (
        f"there are {n} solution trajectories; REPRODUCTION.md says otherwise")


def test_prompt_count_is_stated_correctly():
    n = count_prompts()
    words = {4: "four", 5: "five", 6: "six", 7: "seven"}
    assert f"{words.get(n, str(n))} newly written prompt files" in _read("PRE_EXISTING_WORK.md"), (
        f"there are {n} files in prompts/")


def test_case_count_is_ten_everywhere_it_is_claimed():
    assert count_cases() == 10, "the documents all say ten cases"


@pytest.mark.slow
def test_test_count_is_stated_correctly():
    n = count_tests()
    files = count_test_files()
    assert f"{n} tests" in _read("PRE_EXISTING_WORK.md"), (
        f"pytest collects {n} tests; PRE_EXISTING_WORK.md says otherwise")
    assert f"{n} tests" in _read("README.md"), (
        f"pytest collects {n} tests; README.md says otherwise")
    assert f"{files} files" in _read("README.md")


def test_model_call_total_matches_the_published_results():
    res = json.loads((ROOT / "results" / "results.json").read_text(encoding="utf-8"))
    total = sum(c["model_calls_total"] for c in res["configs"].values())
    text = _read("README.md") + _read("IMPROVEMENT_CHANGELOG.md") + _read("REPRODUCTION.md")
    stated = re.findall(r"\b(\d{3})\s+model calls\b", text)
    for value in stated:
        assert int(value) == total, (
            f"a document claims {value} model calls; the run records total {total}")


def test_the_published_score_table_matches_results_json():
    """REPRODUCTION.md prints the expected `score` output. It must be current."""
    res = json.loads((ROOT / "results" / "results.json").read_text(encoding="utf-8"))
    text = _read("REPRODUCTION.md")
    for cid, c in res["configs"].items():
        n = c["n_cases"]
        line = (f"{cid:16s} UOR={c['unsafe_output_rate']:.2f} "
                f"({c['unsafe_count']}/{n})  "
                f"clean-claim retention={c['clean_claim_retention']:.2f}  "
                f"malformed={c['malformed_runs']} errors={c['error_runs']}")
        assert line in text, f"REPRODUCTION.md's expected output is stale:\n  {line}"


# ------------------------------------------------- every shipped occurrence
# NEW-RA-06: checking selected documents lets the unselected ones lie.
# FV-004: matching only digits let spelled-out counts lie ("Six solution
# trajectories" shipped while eight existed), so the scan parses number words.

_WORD_NUMS = {w: i for i, w in enumerate(
    ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
     "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
     "sixteen", "seventeen", "eighteen", "nineteen", "twenty"])}
_NUM = r"(\d+|" + "|".join(_WORD_NUMS) + r")"


def _as_int(token: str) -> int:
    return _WORD_NUMS.get(token.lower(), -1) if not token.isdigit() else int(token)


def _shipped_documents():
    from ssf_hve.packaging import collect
    for p in collect():
        if p.suffix.lower() in (".md", ".txt"):
            yield p


@pytest.mark.slow
def test_every_count_claim_in_every_shipped_document_is_true():
    n_tests = count_tests()
    n_runs = count_run_records()
    n_fixtures = count_fixtures()
    newest_zip = max((ROOT / "dist").glob("ssf-hve-submission*.zip"),
                     key=lambda p: p.stat().st_mtime, default=None)
    problems = []
    for doc in _shipped_documents():
        rel = doc.relative_to(ROOT).as_posix()
        text = doc.read_text(encoding="utf-8")
        checks = [
            (r"\b" + _NUM + r"\s+tests\b", n_tests, "tests (pytest collects {})"),
            (r"\b" + _NUM + r"\s+passed\b", n_tests, "passed (pytest collects {})"),
            (r"\b" + _NUM + r"\s+(?:published\s+)?run\s+records\b", n_runs,
             "run records (there are {})"),
            (r"\b" + _NUM + r"\s+(?:replay\s+)?fixtures?\b", n_fixtures,
             "fixtures (there are {})"),
            (r"\b" + _NUM + r"\s+(?:representative\s+)?solution\s+trajector(?:y|ies)\b",
             count_trajectories(), "solution trajectories (there are {})"),
            (r"\b" + _NUM + r"\s+dated\s+gold\s+tables?\b",
             count_gold_tables(), "dated gold tables (there are {})"),
            (r"\b" + _NUM + r"\s+newly\s+written\s+prompt\s+files?\b",
             count_prompts(), "prompt files (there are {})"),
        ]
        lines = text.splitlines()
        offsets, pos = [], 0
        for ln in lines:
            offsets.append(pos)
            pos += len(ln) + 1

        def _line_of(start: int) -> str:
            import bisect
            return lines[bisect.bisect_right(offsets, start) - 1]

        for pattern, truth, label in checks:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                # A quoted WITHDRAWN claim is a record of what used to be
                # said, not a live claim; the line must mark itself as such.
                if "withdrawn" in _line_of(m.start()).lower():
                    continue
                if _as_int(m.group(1)) != truth:
                    problems.append(f"{rel}: claims {m.group(1)} "
                                    + label.format(truth))
        for m in re.finditer(r"\b(\d+)\s+files\s+extracted\b", text):
            if newest_zip is None:
                continue          # no archive on disk to compare against
            import zipfile
            entries = sum(1 for i in zipfile.ZipFile(newest_zip).infolist()
                          if not i.is_dir())
            if int(m.group(1)) != entries:
                problems.append(f"{rel}: claims {m.group(1)} files extracted; "
                                f"{newest_zip.name} holds {entries}")
    assert not problems, "stale counts survive in shipped documents:\n" + "\n".join(problems)
