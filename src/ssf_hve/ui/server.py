"""Serving the judge UI locally. The ONLY module in ssf_hve.ui that touches a
socket, and it binds 127.0.0.1 exclusively.

Session isolation: runs started from the UI must never land in the published
`results/runs/`. Result paths are resolved at import time from
SSF_HVE_RESULTS_DIR, so when that variable is unset this module re-launches
the same command in a child process with it pointed at a throwaway session
directory — the one honest way to guarantee isolation without re-plumbing
every module that already imported the paths.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from wsgiref.simple_server import WSGIRequestHandler, make_server

HOST = "127.0.0.1"          # never configurable: this UI is local-only


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):                           # noqa: D102
        sys.stderr.write("ui: %s\n" % (fmt % args))


def serve(port: int = 8765, allow_live: bool = False) -> int:
    if not os.environ.get("SSF_HVE_RESULTS_DIR"):
        session = tempfile.mkdtemp(prefix="ssf-hve-ui-session-")
        env = dict(os.environ, SSF_HVE_RESULTS_DIR=session)
        print(f"session results directory: {session}")
        print("(runs started in the UI are written there, never into the "
              "published results/)")
        return subprocess.call([sys.executable, "-m", "ssf_hve", "ui",
                                "--port", str(port)]
                               + (["--allow-live"] if allow_live else []),
                               env=env)
    from ssf_hve.ui.app import build_app
    app = build_app(allow_live=allow_live, background=True)
    with make_server(HOST, port, app, handler_class=_QuietHandler) as httpd:
        print(f"SSF-HVE judge UI listening on {HOST}:{port} — open http://127.0.0.1:%d/ (Ctrl+C stops)" % port)
        print("replay mode is the default and needs no API key; live mode is "
              + ("ENABLED (--allow-live) and still requires SSF_HVE_API_KEY"
                 if allow_live else "disabled"))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0
