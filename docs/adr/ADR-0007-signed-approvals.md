# ADR-0007 — Cryptographically signed, fail-closed gate records

**Status:** Accepted · **Date:** 2026-08-30 · **Origin:** audit finding

## Context

ADR-0005 established human-only gates. An independent audit pointed out what that had actually
achieved: `record_approval` was guarded, but a gate *record* is a JSON file, and nothing
guarded the file. Any process able to write into `results/gates/` could mint an approval —
including the agent the gate exists to constrain — and nothing in the audit trail would show
it.

Property one (an approval cannot be *created* by the workflow) without property two (an
approval cannot be *forged*) is theatre.

## Options

1. **Filesystem permissions.** Not portable, not verifiable from inside the archive, and
   defeated by the same process that writes the run records.
2. **Sign approvals with an asymmetric key.** Stronger, and needs a key distribution story
   this project does not have.
3. **HMAC-SHA-256 over the canonical record, keyed by an environment secret, verified with a
   constant-time comparison, failing closed.**

## Decision

Option 3, with domain separation (`ssf-hve/gate-approval/v2`), a versioned record schema, a
signed expiry, and every field except the signature inside the signed payload.

**Fail closed means:** an unsigned record, an edited field, a signature from a different key,
an unknown algorithm, an unknown schema version, an expired record, a malformed file, and the
absence of a configured secret all read as *not approved*. There is no flag that disables the
check.

**H1 binds the whole evidence set, not a string.** An H1 record is named by its run and binds
`run_id`, `case_id`, `config_id`, `sample`, and the hashes of the narration, the run record,
the canonical JSONL and Markdown trajectories, the candidate script and the configuration.
Every one except the export state is recomputed from the run record at check time and compared
for strict equality. An approval that does not say what it approves approves nothing, so a
record missing any binding field fails closed.

**H1 approvals expire.** An approval is evidence that a person read *this* candidate
*recently*. The default window is 30 days; the approver may choose another at approval time and
the chosen window is itself signed. No expiry, an unparsable expiry, or a past expiry is not an
approval.

**The export a judge actually reads is verified against disk.** A later finding (FV-001) showed
that a trajectory hash recomputed from the run record proves nothing about the exported file
someone opens. `exported_trajectory_state` re-reads the files: a divergent export blocks
approval and invalidates an existing one; an export verified at approval time may not later
vanish; an export appearing afterwards is fine exactly when it matches.

**H2 binds one package**: archive filename, size, SHA-256, manifest digest, git commit, tree
state and video hash — because a zip can be rebuilt between the moment a person reads it and
the moment it is uploaded, so approving "a submission" would be worth nothing. There is exactly
one route to an H2 approval, and `test_the_cli_has_no_legacy_narration_h2_route` keeps it that
way.

## Consequences

**Good.** `tests/test_gate_signatures.py` writes every forgery an attacker or a careless script
would write and asserts each is refused. The secret is never written to disk, never logged,
never in a run record, trajectory or archive, and never in a test — tests generate their own
throwaway values.

**Bad, and unmitigated.** This is **tamper-evident, not unforgeable**. Anyone holding the owner
secret can mint a valid approval. There is no rotation, no revocation and no way to invalidate
past approvals if the secret leaks. Judged out of scope for a hackathon submission; recorded
here because a reviewer is entitled to disagree.

**Operational cost.** Approving now requires `SSF_HVE_GATE_SECRET` in the environment. If it is
absent, approval refuses *before prompting*, so nobody types `APPROVE` into something that
cannot record it.
