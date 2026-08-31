"""The production package must describe the production it actually performs.

`render_instructions.json` declared 1920x1080 with 48px captions while the
ffmpeg call rendered 1280x720 with a 22pt font. Two independent literals in one
module, drifted apart, and the package therefore described a render nobody had
run. A judge reading the JSON would have been told something untrue.

The fix is not to pick one number; it is to have one number. These tests fail
if the declaration and the invocation can disagree again.
"""
import json
from pathlib import Path

from ssf_hve.rendering import render


def test_the_preview_resolution_is_derived_from_the_production_spec():
    w, h = (int(v) for v in render.PRODUCTION_RESOLUTION.split("x"))
    pw, ph = (int(v) for v in render.PREVIEW_RESOLUTION.split("x"))
    assert pw == int(w * render.PREVIEW_SCALE)
    assert ph == int(h * render.PREVIEW_SCALE)


def test_the_ffmpeg_command_uses_the_declared_preview_resolution():
    """The invocation and the declaration read the same constant."""
    cmd = render.preview_command("ffmpeg", Path("/pkg"), Path("/pkg/demo.mp4"), 10.0)
    joined = " ".join(cmd)
    assert f"s={render.PREVIEW_RESOLUTION}" in joined
    assert f"FontSize={render.PREVIEW_CAPTION_PT}" in joined
    assert f"-r {render.PRODUCTION_FPS}" in joined


def test_no_resolution_literal_survives_in_the_module():
    """A hard-coded frame size is how the two drifted apart the first time."""
    import inspect
    import re

    source = inspect.getsource(render)
    # Strip the constant block: it is allowed to contain the one literal.
    body = source.split("PREVIEW_CAPTION_PT = ", 1)[-1]
    sizes = re.findall(r"\b\d{3,4}x\d{3,4}\b", body)
    assert not sizes, f"a frame size is hard-coded outside the spec block: {sizes}"


def test_the_instructions_distinguish_production_from_preview():
    """A reader must not mistake the half-scale proof for the deliverable."""
    import inspect

    source = inspect.getsource(render.render_run)
    assert '"resolution": PRODUCTION_RESOLUTION' in source, (
        "the declared resolution must come from the spec constant")
    assert '"preview"' in source and "PREVIEW_RESOLUTION" in source, (
        "render_instructions.json must declare the preview separately")
    assert render.PRODUCTION_RESOLUTION != render.PREVIEW_RESOLUTION, (
        "if the preview ever equals production, drop the distinction rather "
        "than implying a downscale that is not happening")


def test_the_preview_is_labelled_as_not_the_production_render():
    import inspect
    source = inspect.getsource(render.render_run)
    assert "NOT the production render" in source, (
        "the package must say plainly that demo.mp4 is a pipeline proof")
