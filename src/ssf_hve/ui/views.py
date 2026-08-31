"""HTML rendering for the judge UI. Pure functions: data in, escaped HTML out.

No template engine and no external assets: everything a page needs is in the
returned string, so the UI works with no network exactly like the evaluation.
All dynamic content passes through `esc()`.
"""
from __future__ import annotations

import html
import json


def esc(value) -> str:
    return html.escape(str(value), quote=True)


_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
       color: #1c2128; background: #f4f5f7; }
header { background: #101418; color: #e8eaed; padding: 14px 22px; }
header .title { font-weight: 700; letter-spacing: .3px; }
header .sub { color: #9aa4af; font-size: 13px; }
nav { background: #1a2027; padding: 6px 22px; }
nav a { color: #cfd6dd; text-decoration: none; margin-right: 16px; font-size: 14px; }
nav a:hover { color: #fff; text-decoration: underline; }
main { max-width: 1080px; margin: 22px auto 60px; padding: 0 22px; }
h1 { font-size: 22px; margin: 6px 0 14px; }
h2 { font-size: 17px; margin: 26px 0 8px; }
section.card { background: #fff; border: 1px solid #dfe3e8; border-radius: 8px;
               padding: 16px 18px; margin: 14px 0; }
table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 6px 9px; border-bottom: 1px solid #e7eaee;
         vertical-align: top; }
th { background: #f0f2f5; font-weight: 600; }
code, pre { font: 12.5px/1.5 ui-monospace, "Cascadia Mono", Consolas, monospace; }
pre { background: #0f1318; color: #d7dde3; padding: 12px 14px; border-radius: 6px;
      overflow-x: auto; white-space: pre-wrap; word-break: break-word; }
.badge { display: inline-block; padding: 2px 10px; border-radius: 999px;
         font-size: 12.5px; font-weight: 700; letter-spacing: .4px; }
.badge.safe { background: #d8f3dc; color: #14532d; }
.badge.unsafe { background: #fde2e1; color: #7f1d1d; }
.badge.hold { background: #fef3c7; color: #78350f; }
.badge.neutral { background: #e5e7eb; color: #374151; }
.badge.blocked { background: #e0e7ff; color: #3730a3; }
.note { color: #57606a; font-size: 13.5px; }
.warn { background: #fff7ed; border: 1px solid #fdba74; border-radius: 6px;
        padding: 10px 12px; font-size: 13.5px; }
.error { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 6px;
         padding: 10px 12px; }
form.run label { display: block; margin: 10px 0 3px; font-weight: 600; font-size: 13.5px; }
select, button { font: inherit; padding: 6px 10px; border-radius: 6px;
                 border: 1px solid #c8cdd3; background: #fff; }
button.primary { background: #101418; color: #fff; border-color: #101418;
                 cursor: pointer; padding: 8px 18px; }
fieldset { border: 1px solid #dfe3e8; border-radius: 6px; margin: 12px 0; }
legend { font-weight: 600; font-size: 13.5px; padding: 0 6px; }
details summary { cursor: pointer; font-weight: 600; margin: 6px 0; }
.kv td:first-child { color: #57606a; width: 260px; }
a { color: #0b57d0; }
.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12.5px; }
"""


def layout(title: str, body: str, *, refresh: int | None = None) -> str:
    meta = (f'<meta http-equiv="refresh" content="{int(refresh)}">' if refresh else "")
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{meta}
<title>{esc(title)} — SSF-HVE</title><style>{_CSS}</style></head>
<body>
<header><div class="title">SSF-HVE — judge interface</div>
<div class="sub">research paper → verified script, evidence, trajectory and production package.
This tool produces and inspects evidence; it cannot approve gates, publish, or submit anything.</div></header>
<nav><a href="/">Run</a><a href="/runs">Runs</a><a href="/score">Score table</a>
<a href="/compare">Comparisons</a><a href="/provenance">Provenance</a>
<a href="/gates">Gates</a><a href="/providers">Providers</a></nav>
<main>{body}</main>
</body></html>"""


def verdict_badge(verdict: str) -> str:
    v = (verdict or "").lower()
    if v in ("clear", "safe"):
        return '<span class="badge safe">SAFE</span>'
    if v == "hold":
        return '<span class="badge hold">HOLD — human adjudication</span>'
    if v in ("asserted", "unsafe"):
        return '<span class="badge unsafe">UNSAFE</span>'
    return f'<span class="badge neutral">{esc(verdict.upper() or "N/A")}</span>'


def kv_table(rows: list[tuple[str, str]]) -> str:
    cells = "".join(f"<tr><td>{esc(k)}</td><td>{v}</td></tr>" for k, v in rows)
    return f'<table class="kv">{cells}</table>'


def pre(text: str) -> str:
    return f"<pre>{esc(text)}</pre>"


def pre_json(obj) -> str:
    return pre(json.dumps(obj, indent=2, ensure_ascii=False))
