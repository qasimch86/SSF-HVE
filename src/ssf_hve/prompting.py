"""Prompt rendering.

Placeholders are ``{{NAME}}`` and are replaced by literal string substitution.
No ``str.format``, no f-strings, no templating engine: source text routinely
contains braces, and none of it should ever be interpreted.
"""
from __future__ import annotations

import json
from pathlib import Path

from ssf_hve.paths import PROMPTS_DIR

_CACHE: dict[str, str] = {}


def load_template(name: str) -> str:
    if name not in _CACHE:
        path: Path = PROMPTS_DIR / name
        if not path.exists():
            raise SystemExit(f"missing prompt template: {path}")
        _CACHE[name] = path.read_text(encoding="utf-8")
    return _CACHE[name]


def render(template_name: str, values: dict[str, str]) -> str:
    text = load_template(template_name)
    for key, val in values.items():
        text = text.replace("{{" + key + "}}", str(val))
    leftovers = [seg.split("}}")[0] for seg in text.split("{{")[1:]]
    if leftovers:
        raise SystemExit(f"{template_name}: unfilled placeholders {leftovers}")
    return text


def as_json(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)
