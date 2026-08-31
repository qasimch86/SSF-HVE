# Reconstructed work log — SSF-HVE

**This is a reconstruction, not a native transcript export.** Timestamps come from git
commits, file modification times and run records; none is invented. Assembled after the
fact from the artifacts this repository contains.

**Agent:** Claude (Claude Agent SDK / Cowork), configured model `claude-opus-5`.
**Human:** the owner, who set scope and holds both approval gates.
**Event window:** 2026-08-29 to 2026-08-31. Deadline 2026-08-31 18:00 UTC.

## Commit trail

| Commit | Time (UTC) | Work |
|---|---|---|
| `eea0ba9f` | 2026-08-29 18:57 UTC | chore: initialise SSF-HVE hackathon edition repository (ignore rules, secret protection) |
| `3a6745ec` | 2026-08-29 18:58 UTC | docs: freeze scope against SSF-HVE-002 and the official brief |
| `483f547b` | 2026-08-29 19:04 UTC | eval: add ten synthetic research packets C01-C10 with planted, enumerated defects |
| `49c41619` | 2026-08-29 19:05 UTC | eval: freeze dated gold table CS-10-v1 before any run |
| `1e635bf5` | 2026-08-29 19:06 UTC | docs: add EVAL_PROTOCOL.md, dated ahead of any run |
| `70204256` | 2026-08-29 19:10 UTC | feat: package skeleton, strict schemas, case loader, provider and replay layers, role prompts |
| `0529ca31` | 2026-08-29 19:17 UTC | feat: deterministic checks, runner with bounded correction loop, human gates, scorer, reports, CLI, trajectory export, A4 producer |
| `031444c2` | 2026-08-29 19:24 UTC | eval: archive CS-10-v1 with its measured baseline and the diagnosis of why it cannot discriminate |
| `5988d6d6` | 2026-08-29 19:28 UTC | eval: CS-10-v2 - packets keep the evidence and lose the coaching; freeze v2 gold table; number-word normalisation in scorer and checks |
| `c788282c` | 2026-08-29 19:41 UTC | eval: CS-10-v3 final case set (prose source, 60s target, 3-sample baseline); three disclosed scorer-fidelity corrections; baseline measured at 0/30 unsafe |
| `5ecaa1b7` | 2026-08-29 19:42 UTC | eval: fold cannot/can't to one spelling in normalisation; baseline measured 0/30 unsafe on 30 samples |
| `1fd425f1` | 2026-08-29 19:54 UTC | eval: capture blinded model responses for the final advanced configuration on CS-10-v3.2 |
| `905d5261` | 2026-08-29 20:11 UTC | eval: complete replay capture for all eight configurations on CS-10-v3.2 — 122 fixtures, per `git ls-tree -r 905d526` [corrected 2026-08-30: this line originally said 121, another from-memory figure] |
| `ca3717d6` | 2026-08-29 20:23 UTC | test: schemas, fail-closed parsing, deterministic checks, gates, replay invalidation, scoring denominators, CLI exit codes, trajectory redaction, repository secret scan |

## Phases, in the order they happened

### Phase 0 — boundary and repository
Read the controlling assessment in full. Retrieved the official micro1 problem statement
(10 pp.) from the live challenge page and confirmed the rubric, the ten ground rules, the
four deliverables and the 18:00 UTC deadline against it. Inventoried the supplied working
copy: 92 root entries including a 12 KB `.env`, `dev-data/*.db`, a virtualenv and 2.4 MB of
pytest logs — all treated as read-only evidence and none of it copied. Established that the
supplied copy is **not** a git repository, so the commit referenced in an earlier internal
document could not be verified; recorded that limitation rather than asserting a tag.
Created this repository, ignore rules first, and froze scope in writing.

### Phase 1 — evaluation before implementation
Wrote `EVAL_PROTOCOL.md` and the ten synthetic packets, then froze the gold table **before**
any run. This ordering is the reason the later revisions are auditable at all.

### Phase 2 — baseline, and the discovery that broke the plan
Built the package skeleton, CLI, provider abstraction, prompt-hash replay store, baseline
runner and deterministic scorer. Captured the first baseline. It scored 0/10 unsafe: the
packets were announcing their own defects. Archived that case set with its numbers and its
diagnosis rather than deleting it, and revised — twice more — until the task was realistic.
The baseline prompt was never touched.

### Phase 3 — the advanced workflow
A1, A2, A3, deterministic pre-checks, the bounded correction loop, fail-closed parsing, H1
gate state. Agent-boundary tests written alongside, not afterwards.

### Phase 4 — ablations and results
Eight configurations over the same ten cases. Captures were sequenced stage by stage: each
`evaluate` pass surfaced the next set of unseen prompts, which were sent to isolated agent
sessions and ingested as fixtures. 122 fixtures in total, and 100 published run records. [Corrected 2026-08-30: an earlier draft of this line said 140, a from-memory figure that never matched the shipped repository; the documented-count tests now pin every such number to the filesystem.]
Both removal experiments produced their intended evidence, one of them decisively.

### Phase 5 — audit
Eight solution trajectories exported, including the fail-closed run and the HOLD/ACCEPT pair [corrected 2026-08-30: this line said 'Six' while eight stems ship — the third spelled-out from-memory count these tests have now caught; the documented-count scan now parses number words too]
that carries the `rm-bound-ok` argument. This log written.

### Phase 6 — submission preparation
Five judge-facing documents, clean-room replay from a fresh environment, secret scan,
allowlisted archive, then a stop for owner approval. No upload or submission is performed
by any agent.

## Decisions the agent made, and the ones it did not

| Decision | Made by |
|---|---|
| Library choices, module layout, test framework, naming | Agent (reversible defaults) |
| Case content, detector design, metric definitions | Agent, frozen in dated tables before use |
| Revising the case set when it could not discriminate | Agent, disclosed in full with all prior numbers retained |
| Retaining `final` over the numerically better `iter-2` | Agent, flagged in the changelog as a judgement rather than a measurement |
| Accepting the participation and ownership terms | **Owner only** |
| Including any pre-existing evidence | **Owner only** — not granted, so none included |
| H1 approval of an exact script version | **Owner only** — enforced in code |
| H2 approval of the archive, and submission itself | **Owner only** |

## Honest notes

- Three scorer corrections were made after seeing results. All three lowered the headline
  number. Each is recorded with its reason in the gold table that introduced it.
- Test runs were, briefly, writing run records into the published results directory. This was
  caught, isolated behind `SSF_HVE_RESULTS_DIR`, and the affected results were regenerated
  from the fixtures. The fix is itself under test.
- One deterministic check (`CHECK-Q`) caused a correction cycle to delete a true sentence,
  because number-word normalisation did not yet cover decimals spoken as "three point six".
  The correcting agent noticed and said so in its response; the trajectory retains it. The
  finding is reported in `IMPROVEMENT_CHANGELOG.md` under iter-1 rather than quietly fixed.
