"""Judge UI for SSF-HVE — a small, newly written local web interface.

Written during the post-audit remediation (branch `audit-remediation-ui`) so a
judge can run the existing workflow and read its evidence without learning the
CLI. Design rules, all tested in `tests/test_ui.py`:

* **Thin.** Every route calls the existing domain services — `runner.execute`,
  `scoring.score_run`, `provenance.verify`, `gates.h1_status`,
  `rendering.render_run`, `trajectory.export` — and duplicates none of their
  logic. The UI cannot change a score, a gate or a binding.
* **Replay by default, no key anywhere.** Live mode exists only behind an
  explicit server flag AND the environment variable the CLI already uses.
  There is no key-entry form, no storage of keys, and no place a key is shown.
* **Standard library only.** No third-party web framework, no database, no
  styling framework, no JavaScript dependency — nothing to install and nothing
  imported from any other application. The whole interface is one WSGI app served by wsgiref
  on 127.0.0.1.
* **Session-isolated.** Runs started from the UI land in a throwaway session
  results directory, never in the published `results/runs/`.
* **Honest about output.** The workflow produces a verified script, evidence,
  trajectories and a production/render package — not a finished video — and
  the UI says so. Rendering refuses without a real H1 approval, and the UI
  cannot create one: gates remain deliberate owner actions at a terminal.

Clean-room note: this package is newly written for this remediation. It shares
no code, templates, styling or assets with any prior application, and a test
enforces that its imports are standard-library or ssf_hve only.
"""
