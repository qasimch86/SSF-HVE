"""Human-only approval gates, tamper-evident and bound to exact evidence.

H1 approves one exact candidate script **as produced by one exact run**. H2
approves one exact submission package. Three properties, each of which exists
because an earlier version of this module lacked it:

1. **An approval cannot be created by the workflow.** ``record_approval``
   requires a decision typed by a person at an interactive terminal, and the
   runner never imports it. An agent status, however confident, cannot open a
   gate.

2. **An approval cannot be forged by writing a file.** Every gate record
   carries an HMAC-SHA-256 signature over its own canonical content — every
   field, including the algorithm label and the schema version — keyed by a
   secret the owner holds outside the repository. Verification recomputes it
   with a constant-time comparison and refuses anything that does not verify.

3. **An approval cannot be moved.** The original H1 bound only the narration
   text, so a valid record copied beside a different run with identical
   narration was accepted, and a record from years ago stayed valid forever
   (re-verification finding AUD-002). An H1 record now binds the run id, the
   case, the configuration and sample, the narration hash, the byte-exact run
   record, the canonical trajectory derived from it, the candidate script and
   the configuration snapshot — and it expires. Verification recomputes every
   one of those from the run record on disk at check time. Copy the record to
   another run, edit the run record, regenerate the trajectory differently, or
   let the approval go stale, and it reads as *not approved*.

The secret is read from ``SSF_HVE_GATE_SECRET`` and is never written to disk,
never logged, and never included in a run record, trajectory or archive. If it
is not set, verification **fails closed**: an unverifiable approval is treated
as no approval. There is no flag to disable the check.

Threat model, stated honestly (see PROVENANCE.md, "What the gate signatures do
and do not defend against"): HMAC with an environment secret defends against
an adversary who can WRITE files but cannot read the owner's environment and
cannot replace the verification code itself. It does not defend against a
process running with the owner's environment (which can read the secret), nor
against an adversary who can edit this module, nor does it provide key
rotation or revocation beyond the expiry window. Those are the limits of the
mechanism, not an oversight in it.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ssf_hve.paths import GATES_DIR, run_record_path, validate_run_id
from ssf_hve.schemas import GateRecord

SECRET_ENV = "SSF_HVE_GATE_SECRET"

# Domain separation: a signature minted for one purpose must not verify for
# another, and a signature from a different project or schema generation must
# not verify here.
SIGNATURE_DOMAIN = "ssf-hve/gate-approval/v2"
SIGNATURE_ALGORITHM = "HMAC-SHA-256"
GATE_SCHEMA_VERSION = "ssf-hve/gate-record/v2"

# Fail closed on anything this code was not written to understand. A record
# announcing a different algorithm or schema version is refused BEFORE any
# cryptography happens: an unknown label is not an invitation to guess.
KNOWN_ALGORITHMS = (SIGNATURE_ALGORITHM,)
KNOWN_SCHEMA_VERSIONS = (GATE_SCHEMA_VERSION,)

# Fields covered by the signature: every field of the record except the
# signature itself. `signature_algorithm` and `gate_schema_version` are
# deliberately INSIDE the signed payload — an unsigned label could be edited
# to claim a different algorithm after the fact (AUD-002 / NEW-RA-05).
# `_signed_blob` asserts this list matches the record, so a field added to
# GateRecord without a decision here fails loudly instead of going unsigned.
SIGNED_FIELDS = ("gate", "gate_schema_version", "signature_algorithm",
                 "purpose", "artifact_sha256", "artifact_kind", "approver",
                 "approved_utc", "expires_utc", "note", "binding")

# Freshness policy for H1: an approval is evidence that a person read THIS
# candidate recently, so it expires. 30 days is the default window; the
# approver may shorten or extend it at approval time and the chosen window is
# itself signed. A record with no expiry, an unparsable expiry, or an expiry
# in the past is not an approval. There is no revocation mechanism beyond
# expiry and deleting the record file; that limit is documented, not hidden.
H1_DEFAULT_VALID_DAYS = 30
H1_PURPOSE = "h1-script-production-approval"
H2_PURPOSE = "h2-submission-package-approval"

# Binding fields an H1 record must carry. Missing any one of them fails
# closed: an approval that does not say what it approves approves nothing.
REQUIRED_H1_BINDING = ("run_id", "case_id", "config_id", "sample",
                       "narration_sha256", "run_record_sha256",
                       "trajectory_sha256", "trajectory_md_sha256",
                       "candidate_sha256", "config_sha256",
                       "exported_trajectory")
# The subset recomputed from the run record and compared for strict equality.
# `exported_trajectory` is deliberately NOT in it: the export may legitimately
# appear after approval, and its policy (below) is checked separately against
# the ACTUAL files on disk — final verification finding FV-001 showed that a
# hash recomputed from the run record proves nothing about the exported
# artifact a judge actually reads.
STRICT_H1_BINDING = tuple(k for k in REQUIRED_H1_BINDING
                          if k != "exported_trajectory")

_CLOCK_SKEW_S = 300


class GateNotApproved(RuntimeError):
    pass


class NotAHuman(RuntimeError):
    """Raised when an approval is attempted without an interactive person."""


class GateSecretMissing(RuntimeError):
    """Raised when no owner secret is configured. Verification fails closed."""


def artifact_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_sha256(obj) -> str:
    """Hash of an object's canonical JSON form (sorted keys, no whitespace)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _secret() -> bytes:
    raw = os.environ.get(SECRET_ENV, "")
    if not raw.strip():
        raise GateSecretMissing(
            f"{SECRET_ENV} is not set. Gate approvals are signed, and an "
            "unverifiable approval is treated as no approval. Set the owner "
            "secret in the environment; it is never stored in the repository.")
    return raw.encode("utf-8")


def _signed_blob(rec: "GateRecord") -> bytes:
    """The exact bytes the signature covers: canonical JSON, sorted keys."""
    present = set(rec.as_dict()) - {"signature"}
    assert present == set(SIGNED_FIELDS), (
        f"unsigned field(s) in the gate record: {sorted(present - set(SIGNED_FIELDS))}")
    body = {f: getattr(rec, f) for f in SIGNED_FIELDS}
    payload = {"domain": SIGNATURE_DOMAIN, "record": body}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sign(rec: "GateRecord", secret: bytes | None = None) -> str:
    return hmac.new(secret or _secret(), _signed_blob(rec), hashlib.sha256).hexdigest()


def verify(rec: "GateRecord", secret: bytes | None = None) -> bool:
    """Constant-time signature check. False on any doubt, never an exception.

    Unknown algorithm or schema labels are refused before any comparison: the
    label is part of the signed payload, but a verifier that proceeded on an
    unknown label would be executing a guess.
    """
    if rec.signature_algorithm not in KNOWN_ALGORITHMS:
        return False
    if rec.gate_schema_version not in KNOWN_SCHEMA_VERSIONS:
        return False
    try:
        expected = sign(rec, secret)
    except GateSecretMissing:
        return False
    except AssertionError:
        return False
    given = rec.signature or ""
    if len(given) != len(expected):
        # compare_digest is constant time only for equal-length inputs; a
        # length mismatch is already a rejection, so return before comparing.
        return False
    return hmac.compare_digest(given, expected)


def _now_utc(now: datetime | None = None) -> datetime:
    return now.astimezone(timezone.utc) if now else datetime.now(timezone.utc)


def _parse_utc(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _stamp(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ record files

def h1_record_path(run_id: str) -> Path:
    """H1 records are named by the run they bind. One run, one possible record."""
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    return GATES_DIR / f"H1_{validate_run_id(run_id)}.json"


def _h2_path(sha: str) -> Path:
    GATES_DIR.mkdir(parents=True, exist_ok=True)
    return GATES_DIR / f"H2_{sha[:16]}.json"


# ------------------------------------------------------------------ H1 binding

def exported_trajectory_state(run_id: str, run: dict) -> str:
    """What the ACTUAL exported trajectory files on disk say, right now.

    "absent"         — neither export exists (they are derivable on demand).
    "verified-match" — every export that exists is byte-identical to the
                       canonical text derived from the run record.
    "divergent"      — an export exists whose bytes differ. The judge-facing
                       evidence no longer matches the run; nothing may be
                       approved over it and no approval survives it (FV-001).
    """
    from ssf_hve.trajectory.export import (build_events, jsonl_text,
                                           markdown_text)
    from ssf_hve.paths import trajectory_path

    events = build_events(run)
    expected = {".jsonl": jsonl_text(events).encode("utf-8"),
                ".md": markdown_text(run, events).encode("utf-8")}
    seen_any = False
    for suffix, want in expected.items():
        p = trajectory_path(run_id, suffix)
        if not p.exists():
            continue
        seen_any = True
        if hashlib.sha256(p.read_bytes()).hexdigest() != hashlib.sha256(want).hexdigest():
            return "divergent"
    return "verified-match" if seen_any else "absent"


def h1_binding(run: dict, run_path: Path) -> dict:
    """Everything an H1 approval is bound to, computed from the run itself
    AND from the exported artifacts on disk.

    Two trajectory hashes are bound: the canonical JSONL and the canonical
    Markdown, both derived deterministically from the run record — the exact
    texts `export-trajectory` writes. `exported_trajectory` records what the
    files on disk actually contained at binding time; verification re-reads
    the files, so an export modified after approval is refused (FV-001).
    """
    from ssf_hve.trajectory.export import trajectory_md_sha256, trajectory_sha256

    meta = run["meta"]
    narration = run.get("final_narration") or ""
    return {
        "run_id": meta["run_id"],
        "case_id": meta["case_id"],
        "config_id": meta["config_id"],
        "sample": int(run.get("config", {}).get("sample", 1)),
        "narration_sha256": artifact_sha256(narration),
        "run_record_sha256": hashlib.sha256(run_path.read_bytes()).hexdigest(),
        "trajectory_sha256": trajectory_sha256(run),
        "trajectory_md_sha256": trajectory_md_sha256(run),
        "candidate_sha256": canonical_sha256(run.get("final_script")),
        "config_sha256": canonical_sha256(run.get("config", {})),
        "exported_trajectory": exported_trajectory_state(meta["run_id"], run),
    }


def h1_status(run_id: str, *, secret: bytes | None = None,
              now: datetime | None = None) -> tuple[GateRecord | None, str]:
    """The verified H1 approval for this exact run, or (None, why not).

    Every binding field is recomputed from the run record on disk at check
    time. Any mismatch, any missing field, any unknown label, any expiry and
    any signature failure reads as not approved, with the specific reason.
    """
    try:
        p = h1_record_path(run_id)
    except Exception as exc:                                     # noqa: BLE001
        return None, str(exc)
    if not p.exists():
        return None, f"no approval record exists for run {run_id}"
    try:
        rec = GateRecord.parse(json.loads(p.read_text(encoding="utf-8")))
    except Exception as exc:                                     # noqa: BLE001
        return None, f"the approval record is malformed and was refused: {exc}"
    if rec.gate != "H1":
        return None, f"the record is for gate {rec.gate}, not H1"
    if rec.gate_schema_version not in KNOWN_SCHEMA_VERSIONS:
        return None, ("the record declares gate schema "
                      f"{rec.gate_schema_version!r}, which this verifier does "
                      "not know. Unknown schemas fail closed.")
    if rec.signature_algorithm not in KNOWN_ALGORITHMS:
        return None, ("the record declares signature algorithm "
                      f"{rec.signature_algorithm!r}, which this verifier does "
                      "not know. Unknown algorithms fail closed.")
    if not rec.signature:
        return None, ("the record carries no signature. It was not written by "
                      "`approve`, or it was edited afterwards.")
    if not os.environ.get(SECRET_ENV, "").strip() and secret is None:
        return None, (f"{SECRET_ENV} is not set, so the signature cannot be "
                      "checked. An unverifiable approval is treated as no approval.")
    if not verify(rec, secret):
        return None, ("the signature does not verify. The record was altered "
                      "after it was signed, or it was signed with a different secret.")
    if rec.purpose != H1_PURPOSE:
        return None, f"the record's purpose is {rec.purpose!r}, not {H1_PURPOSE!r}"
    missing = [k for k in REQUIRED_H1_BINDING if k not in rec.binding]
    if missing:
        return None, (f"the record is missing binding field(s) {missing}; an "
                      "approval that does not say what it approves approves nothing")

    # ---- freshness ---------------------------------------------------------
    now_dt = _now_utc(now)
    approved = _parse_utc(rec.approved_utc)
    expires = _parse_utc(rec.expires_utc)
    if approved is None or expires is None:
        return None, "the record's timestamps are missing or unparsable"
    if approved > now_dt + timedelta(seconds=_CLOCK_SKEW_S):
        return None, f"the record claims to be approved in the future ({rec.approved_utc})"
    if now_dt >= expires:
        return None, (f"the approval expired at {rec.expires_utc}. Freshness "
                      "policy: an H1 approval is valid for the signed window "
                      f"chosen at approval time (default {H1_DEFAULT_VALID_DAYS} "
                      "days) and must then be re-issued against the same evidence.")

    # ---- recompute the binding from the run record on disk ----------------
    if rec.binding.get("run_id") != run_id:
        return None, (f"the record binds run {rec.binding.get('run_id')!r}, "
                      f"not {run_id!r}. An approval cannot be copied between runs.")
    try:
        rp = run_record_path(run_id)
    except Exception as exc:                                     # noqa: BLE001
        return None, str(exc)
    if not rp.exists():
        return None, f"the approved run record {run_id} no longer exists"
    try:
        run = json.loads(rp.read_text(encoding="utf-8"))
        actual = h1_binding(run, rp)
    except Exception as exc:                                     # noqa: BLE001
        return None, f"the run record could not be re-derived: {exc}"
    for key in STRICT_H1_BINDING:
        if rec.binding.get(key) != actual[key]:
            return None, (f"binding field {key!r} no longer matches the run "
                          "record. The evidence changed after approval, so the "
                          "approval no longer applies.")
    if rec.artifact_sha256 != actual["narration_sha256"]:
        return None, "the record approves a different narration than this run produced"

    # ---- the exported artifacts a judge actually reads (FV-001) -----------
    # Policy: an export that exists must be byte-identical to the canonical
    # text; an export that was verified at approval time must not vanish; an
    # export appearing later is fine exactly when it matches.
    state_now = actual["exported_trajectory"]
    if state_now == "divergent":
        return None, ("an exported trajectory file for this run no longer "
                      "matches the approved evidence. Re-export it "
                      "(python -m ssf_hve export-trajectory) or remove the "
                      "divergent file; an approval never covers evidence "
                      "that differs from its run record.")
    if rec.binding.get("exported_trajectory") == "verified-match" and state_now == "absent":
        return None, ("the exported trajectory that was verified at approval "
                      "time is missing. Re-export it; an approval bound to an "
                      "exported artifact does not survive its removal.")
    return rec, ""


def approve_h1(run_id: str, *, approver: str, note: str = "",
               valid_days: int = H1_DEFAULT_VALID_DAYS,
               stdin=None, stdout=None, secret: bytes | None = None,
               now: datetime | None = None) -> GateRecord:
    """Interactively approve one exact run's candidate script (gate H1)."""
    rp = run_record_path(run_id)
    if not rp.exists():
        raise GateNotApproved(f"no run record for {run_id}")
    run = json.loads(rp.read_text(encoding="utf-8"))
    narration = run.get("final_narration") or ""
    if not narration.strip():
        raise GateNotApproved(f"run {run_id} produced no script to approve")
    if int(valid_days) < 1:
        raise GateNotApproved("the freshness window must be at least one day")
    binding = h1_binding(run, rp)
    if binding["exported_trajectory"] == "divergent":
        raise GateNotApproved(
            f"the exported trajectory for {run_id} does not match its run "
            "record. Nothing may be approved over divergent evidence: "
            "re-export it (python -m ssf_hve export-trajectory --run "
            f"{run_id}) or remove the divergent file, then approve.")
    now_dt = _now_utc(now)
    return record_approval(
        "H1", narration, "verified script version", approver=approver,
        note=note, binding=binding, purpose=H1_PURPOSE,
        approved_utc=_stamp(now_dt),
        expires_utc=_stamp(now_dt + timedelta(days=int(valid_days))),
        stdin=stdin, stdout=stdout, secret=secret)


# ------------------------------------------------------------------ H2 lookups

def approval_for(gate: str, artifact_text: str, *,
                 secret: bytes | None = None) -> GateRecord | None:
    """Return the VERIFIED approval for this exact artifact text, or None.

    H2 only. H1 approvals are bound to a run, not to a text, and are checked
    with `h1_status`; looking one up by narration alone is exactly the
    transfer bug this module exists to prevent.
    """
    if gate != "H2":
        raise ValueError("approval_for is H2-only; use h1_status for H1")
    sha = artifact_sha256(artifact_text)
    p = _h2_path(sha)
    if not p.exists():
        return None
    try:
        rec = GateRecord.parse(json.loads(p.read_text(encoding="utf-8")))
    except Exception:                                            # noqa: BLE001
        return None
    if rec.artifact_sha256 != sha or rec.gate != gate:
        return None
    if rec.purpose != H2_PURPOSE:
        return None
    if not verify(rec, secret):
        return None
    return rec


def why_not_approved(gate: str, artifact_text: str, *,
                     secret: bytes | None = None) -> str:
    """A specific reason, for `gate-status` (H2). Never reveals the secret."""
    if gate != "H2":
        raise ValueError("why_not_approved is H2-only; h1_status returns its own reason")
    sha = artifact_sha256(artifact_text)
    p = _h2_path(sha)
    if not p.exists():
        return f"no approval record exists for {sha[:16]}..."
    try:
        rec = GateRecord.parse(json.loads(p.read_text(encoding="utf-8")))
    except Exception as exc:                                     # noqa: BLE001
        return f"the approval record is malformed and was refused: {exc}"
    if rec.gate != gate:
        return f"the record is for gate {rec.gate}, not {gate}"
    if rec.artifact_sha256 != sha:
        return "the record approves a different artifact"
    if not rec.signature:
        return ("the record carries no signature. It was not written by "
                "`approve-submission`, or it was edited afterwards.")
    if rec.gate_schema_version not in KNOWN_SCHEMA_VERSIONS:
        return f"unknown gate schema {rec.gate_schema_version!r}; fails closed"
    if rec.signature_algorithm not in KNOWN_ALGORITHMS:
        return f"unknown signature algorithm {rec.signature_algorithm!r}; fails closed"
    if not os.environ.get(SECRET_ENV, "").strip():
        return (f"{SECRET_ENV} is not set, so the signature cannot be checked. "
                "An unverifiable approval is treated as no approval.")
    if not verify(rec, secret):
        return ("the signature does not verify. The record was altered after "
                "it was signed, or it was signed with a different secret.")
    if rec.purpose != H2_PURPOSE:
        return f"the record's purpose is {rec.purpose!r}, not {H2_PURPOSE!r}"
    return ""


def require(gate: str, artifact_text: str, *, secret: bytes | None = None) -> GateRecord:
    rec = approval_for(gate, artifact_text, secret=secret)
    if rec is None:
        raise GateNotApproved(
            f"{gate} has no verified approval for this exact artifact "
            f"({artifact_sha256(artifact_text)[:16]}...). "
            f"{why_not_approved(gate, artifact_text, secret=secret)} "
            "A person must approve this version before it proceeds.")
    return rec


# ------------------------------------------------------------------ creation

def record_approval(gate: str, artifact_text: str, artifact_kind: str, *,
                    approver: str, note: str = "", binding: dict | None = None,
                    purpose: str = "", approved_utc: str = "",
                    expires_utc: str = "", stdin=None, stdout=None,
                    secret: bytes | None = None) -> GateRecord:
    """Write a signed gate approval. Interactive, human-only, by construction.

    `binding` records what this approval is bound to besides the artifact
    text. For H1 that is the full run evidence (REQUIRED_H1_BINDING); for H2,
    the archive digest, manifest digest, size, filename, commit evidence and
    video hash. It is covered by the signature, so nothing can be swapped
    underneath an approval that names it.
    """
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    if not hasattr(stdin, "isatty") or not stdin.isatty():
        raise NotAHuman(
            "gate approval requires an interactive terminal. There is no flag, "
            "environment variable or API that can approve a gate on a person's "
            "behalf, and that is the point.")
    if not approver.strip():
        raise NotAHuman("an approver name is required")
    binding = dict(binding or {})
    if gate == "H1":
        missing = [k for k in REQUIRED_H1_BINDING if k not in binding]
        if missing:
            raise GateNotApproved(
                f"an H1 approval must bind {missing}; refusing to record an "
                "approval that does not say what it approves")
        purpose = purpose or H1_PURPOSE
        path = h1_record_path(str(binding["run_id"]))
    else:
        purpose = purpose or H2_PURPOSE
        path = _h2_path(artifact_sha256(artifact_text))
    key = secret or _secret()          # fail before prompting if unset
    sha = artifact_sha256(artifact_text)
    now_dt = _now_utc()
    approved_utc = approved_utc or _stamp(now_dt)
    expires_utc = expires_utc or _stamp(now_dt + timedelta(days=H1_DEFAULT_VALID_DAYS))
    print(f"\nGate {gate}: approving {artifact_kind}", file=stdout)
    print(f"Artifact SHA-256: {sha}", file=stdout)
    print(f"Length: {len(artifact_text)} characters", file=stdout)
    print(f"Valid: {approved_utc} until {expires_utc}", file=stdout)
    for k, v in sorted(binding.items()):
        print(f"  bound {k}: {v}", file=stdout)
    print(f"\nType the word APPROVE to record approval as '{approver}'.", file=stdout)
    stdout.flush()
    typed = stdin.readline().strip()
    if typed != "APPROVE":
        raise GateNotApproved(f"{gate} not approved (received {typed!r})")
    unsigned = GateRecord(
        gate=gate, artifact_sha256=sha, artifact_kind=artifact_kind,
        approver=approver.strip(),
        approved_utc=approved_utc, expires_utc=expires_utc,
        note=note, binding=binding, purpose=purpose,
        gate_schema_version=GATE_SCHEMA_VERSION,
        signature_algorithm=SIGNATURE_ALGORITHM)
    # GateRecord is frozen, so the signed record is a new object rather than a
    # mutation. An approval that could be edited in place would not be evidence.
    rec = replace(unsigned, signature=sign(unsigned, key))
    with path.open("w", encoding="utf-8") as fh:
        json.dump(rec.as_dict(), fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return rec
