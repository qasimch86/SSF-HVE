"""A4 - Deterministic Producer.

A4 assembles. It does not generate, and it does not alter one word of verified
scientific wording: narration strings are copied byte-for-byte from the approved
script. Production is gated on H1, and a rendering failure never blocks
evaluation, documentation or the submission.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from ssf_hve import gates
from ssf_hve.paths import (SAMPLES_DIR, InvalidRunId, run_record_path,
                           validate_run_id)

WORDS_PER_SECOND = 2.4
MIN_BEAT_S = 2.0


@dataclass
class RenderResult:
    run_id: str
    ok: bool
    package_dir: str = ""
    video_path: str = ""
    messages: list[str] = field(default_factory=list)

    def summary(self) -> str:
        head = "production package written" if self.ok else "production not produced"
        lines = [f"{head} for run {self.run_id}"]
        if self.package_dir:
            lines.append(f"  package: {self.package_dir}")
        if self.video_path:
            lines.append(f"  video  : {self.video_path}")
        lines.extend(f"  - {m}" for m in self.messages)
        return "\n".join(lines)


def _timing(script: dict) -> list[dict]:
    cards, t = [], 0.0
    for i, beat in enumerate(script["beats"], start=1):
        words = len(beat["narration"].split())
        dur = max(MIN_BEAT_S, round(words / WORDS_PER_SECOND, 2))
        cards.append({
            "index": i, "beat": beat["beat"],
            "start_s": round(t, 2), "end_s": round(t + dur, 2), "duration_s": dur,
            "narration": beat["narration"],          # copied verbatim, never edited
            "on_screen": beat.get("on_screen", ""),
            "claim_refs": beat.get("claim_refs", []),
        })
        t += dur
    return cards


def _citation_frames(claim_map: dict | None, cards: list[dict]) -> list[dict]:
    if not claim_map:
        return []
    by_id = {c["id"]: c for c in claim_map.get("claims", [])}
    frames = []
    for card in cards:
        refs = [by_id[r] for r in card["claim_refs"] if r in by_id]
        if not refs:
            continue
        frames.append({
            "at_s": card["start_s"], "beat": card["beat"],
            "citations": [{"claim_id": c["id"], "evidence_level": c["evidence_level"],
                           "scope": c["scope"], "evidence_refs": c["evidence_refs"]}
                          for c in refs],
        })
    return frames


def _srt(cards: list[dict]) -> str:
    def ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    out = []
    for c in cards:
        out.append(str(c["index"]))
        out.append(f"{ts(c['start_s'])} --> {ts(c['end_s'])}")
        out.extend(textwrap.wrap(c["narration"], 42) or [""])
        out.append("")
    return "\n".join(out)


# --------------------------------------------------------------- render spec
#
# One source of truth. The JSON instructions and the ffmpeg preview used to
# carry independent literals and had drifted apart: the instructions declared
# 1920x1080 while the preview rendered 1280x720, so the package described a
# production it did not produce. They are derived from these constants now, and
# `tests/test_render_spec.py` fails if they diverge again.
#
# The preview is deliberately smaller. It exists to prove the timing and
# caption pipeline runs end to end on a laptop without ffmpeg filters that
# need fonts installed; it is not the production render and is labelled as
# such in render_instructions.json.
PRODUCTION_RESOLUTION = "1920x1080"
PRODUCTION_FPS = 30
PRODUCTION_CAPTION_PX = 48
PRODUCTION_CITATION_PX = 28
PREVIEW_SCALE = 0.5


def _scaled(resolution: str, scale: float) -> str:
    w, h = (int(v) for v in resolution.lower().split("x"))
    return f"{int(w * scale)}x{int(h * scale)}"


PREVIEW_RESOLUTION = _scaled(PRODUCTION_RESOLUTION, PREVIEW_SCALE)
# ASS FontSize is in points against the rendered height, so the preview font
# scales with the preview frame rather than being chosen independently.
PREVIEW_CAPTION_PT = int(PRODUCTION_CAPTION_PX * PREVIEW_SCALE * 0.92)


def preview_command(ffmpeg: str, pkg: "Path", out: "Path", total: float) -> list[str]:
    """The exact ffmpeg invocation for the preview. Built here so a test can
    read it without needing ffmpeg installed."""
    return [ffmpeg, "-y", "-f", "lavfi", "-i",
            f"color=c=0x101418:s={PREVIEW_RESOLUTION}:d={total}", "-vf",
            f"subtitles={(pkg / 'captions.srt').as_posix()}"
            f":force_style='FontSize={PREVIEW_CAPTION_PT},"
            "PrimaryColour=&H00F2F2F2&'",
            "-r", str(PRODUCTION_FPS), "-pix_fmt", "yuv420p", str(out)]


def render_run(run_id: str, *, allow_missing_ffmpeg: bool = True) -> RenderResult:
    try:
        path = run_record_path(run_id)
    except InvalidRunId as exc:
        return RenderResult(run_id, False, messages=[str(exc)])
    if not path.exists():
        return RenderResult(run_id, False, messages=[f"no such run: {run_id}"])
    run = json.loads(path.read_text(encoding="utf-8"))
    res = RenderResult(run_id, False)

    status = run["meta"]["terminal_status"]
    if status in ("HOLD", "REWORK", "MALFORMED", "ERROR"):
        res.messages.append(
            f"run terminated {status}; production is not attempted on an "
            "unresolved script. This is the designed behaviour, not a failure.")
        return res

    narration = run.get("final_narration") or ""
    approval, why = gates.h1_status(run_id)
    if approval is None:
        res.messages.append(
            "H1 is not approved for this exact run and script version. "
            f"Reason: {why} Production requires an approval bound to this run: "
            f"narration {gates.artifact_sha256(narration)[:16]}…  "
            "Run: python -m ssf_hve approve --run "
            f"{run_id} --approver \"<your name>\"")
        return res

    script = run["final_script"]
    cards = _timing(script)
    frames = _citation_frames(run.get("claim_map"), cards)
    pkg = SAMPLES_DIR / validate_run_id(run_id)
    pkg.mkdir(parents=True, exist_ok=True)

    (pkg / "narration_timing.json").write_text(
        json.dumps({"total_duration_s": round(cards[-1]["end_s"], 2) if cards else 0,
                    "cards": cards}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8")
    (pkg / "captions.srt").write_text(_srt(cards), encoding="utf-8")
    (pkg / "citation_frames.json").write_text(
        json.dumps(frames, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (pkg / "script.txt").write_text(narration + "\n", encoding="utf-8")
    (pkg / "render_instructions.json").write_text(json.dumps({
        "fps": PRODUCTION_FPS,
        "resolution": PRODUCTION_RESOLUTION,
        "caption_font": f"system sans, {PRODUCTION_CAPTION_PX}px, bottom third, "
                        "80% opacity plate",
        "citation_font": f"system sans, {PRODUCTION_CITATION_PX}px, top right",
        "preview": {
            "resolution": PREVIEW_RESOLUTION,
            "caption_font_size": PREVIEW_CAPTION_PT,
            "what_it_is": (
                "demo.mp4 in this directory, when ffmpeg is available. It is a "
                "half-scale proof that the timing and caption pipeline runs "
                "end to end, NOT the production render. The production spec is "
                "the resolution and font sizes above; the preview is derived "
                "from them by PREVIEW_SCALE and is labelled so the two are not "
                "confused."),
            "scale": PREVIEW_SCALE,
        },
        "cards": [{"index": c["index"], "start_s": c["start_s"],
                   "end_s": c["end_s"], "on_screen": c["on_screen"]} for c in cards],
        "note": ("Narration strings are copied verbatim from the H1-approved "
                 "script. A4 never edits scientific wording."),
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    res.package_dir = str(pkg)
    res.ok = True
    res.messages.append(f"{len(cards)} caption cards, {len(frames)} citation frames")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        msg = "ffmpeg not found; the production package is complete without the MP4."
        res.messages.append(msg)
        return res if allow_missing_ffmpeg else RenderResult(run_id, False, str(pkg), messages=[msg])

    total = cards[-1]["end_s"] if cards else 1.0
    out = pkg / "demo.mp4"
    cmd = preview_command(ffmpeg, pkg, out, total)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as exc:                                   # noqa: BLE001
        res.messages.append(f"ffmpeg did not run ({type(exc).__name__}); package is complete without the MP4.")
        return res
    if proc.returncode != 0 or not out.exists():
        tail = (proc.stderr or "").strip().splitlines()[-3:]
        res.messages.append("ffmpeg failed; package is complete without the MP4. "
                            + " / ".join(tail))
        return res
    res.video_path = str(out)
    res.messages.append(f"rendered {out.name} ({round(total, 1)} s)")
    return res
