# DD-HVE-001 — Data Dictionary

| | |
|---|---|
| **Document** | DD-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Scope** | Every persisted structure in the repository |

> **Provenance.** Field lists were read from the shipped artifacts, not written from memory.
> See [`README.md`](README.md).

Every structure is JSON on disk, readable without tooling. Schema identifiers are literal
strings stored in the files themselves.

---

## 1. Case — `evaluation/cases/C<NN>.json`

The evaluation input. Carries both the packet an agent sees and the answer key it must not.

| Field | Type | Definition |
|---|---|---|
| `case_id` | string | `C01`…`C10`. Also the filename stem. |
| `title` | string | Human label. Rendered to the agent. |
| `defect_class` | string | The one defect class this case tests. One of the ten in `EVAL_PROTOCOL.md` §3. |
| `audience` | string | Target reading level, rendered to A2. |
| `target_duration_s` | integer | 60. Drives the word budget, which forces the script to drop material. |
| `source` | object | The packet: `study_id`, `design`, `background`, `abstract`, `population`, `methods`, `statistical_analysis`, `results_table`, `limitations`, `author_conclusion` and others. **This is the only part rendered to agents.** |
| `clean_claims` | array | True material that must survive into the script. |
| `planted_defects` | array | The answer key. **Never rendered.** |
| `gold_unsafe_criteria` | string | Prose statement of what makes an output unsafe. **Never rendered.** |
| `notes_for_human_reviewer` | string | Reviewer guidance. **Never rendered.** |

**`clean_claims[]`**

| Field | Type | Definition |
|---|---|---|
| `id` | string | `CL01`… Referenced by the claim map and by findings. |
| `text` | string | The true statement. |
| `evidence_ref` | string | Where in `source` it comes from. |
| `protected_patterns` | array of regex | Patterns whose presence means the claim survived. Drives clean-claim retention. |

**`planted_defects[]`**

| Field | Type | Definition |
|---|---|---|
| `id` | string | `C09-D1`… |
| `class` | string | The defect class. |
| `description` | string | What an unsafe output would assert. |
| `rationale` | string | Why it matters scientifically. |
| `expected_evidence_refs` | array | Source fields that contradict the defect. |
| `detector` | object | How the scorer decides the defect was asserted. |

**`planted_defects[].detector`**

| Field | Type | Definition |
|---|---|---|
| `mode` | enum | `match` — asserted if a sentence matches. `absent` — asserted if no sentence satisfies the required presence. `null_endpoint_stance` — asserted by stance classification rather than phrase matching (ADR-0009). |
| `patterns` | array of regex | For `match`, the offence. For `absent`, the required presence. For stance mode, **topic selectors only** — which sentences are about the endpoint, not what verdict they carry. |
| `unless` | array of regex | Sentence-scoped cancellation. |
| `document_unless` | array of regex | Document-scoped cancellation: a disclaimer anywhere redeems the whole output. |

## 2. Gold table — `evaluation/gold/gold_table_<date>_<rev>.json`

A dated, self-hashed snapshot of the case definitions that produced a published number.
**Never edited in place**; a revision is a new file.

| Field | Type | Definition |
|---|---|---|
| `gold_table_sha256` | string | SHA-256 of the canonical `payload`. `verify-gold` recomputes it. |
| `payload.schema` | string | `ssf-hve/gold-table/1` |
| `payload.created_utc` | string | **A declared label, not necessarily a clock reading.** Five of the seven postdate their own commits; `verify-provenance` §5 prints the comparison. See `PROVENANCE.md` §3. |
| `payload.case_set_id` | string | e.g. `CS-10-v5-stance`. Stamped into every result. |
| `payload.declared_before_any_run_on_this_case_set` | boolean | A self-assertion. Unsupported for v1–v3.2 and withdrawn; `false` on the retrospective tables. |
| `payload.retrospective` | boolean | True where the table was written after the runs it scores. |
| `payload.scoring_policy_version` | integer | Which scorer policy this table expects. |
| `payload.supersedes` | string | The revision chain. |
| `payload.reason_for_revision` | string | Why this revision exists. Read this before trusting a comparison across revisions. |
| `payload.provenance_statement` | string | On retrospective tables: an explicit statement that it is **not** a preregistration. |
| `payload.sampling` | string | Sampling design: 3 samples per case for the baseline, 1 for advanced configurations. |
| `payload.scoring_rules` | object | Primary metric, unsafe definition, detector semantics, text normalisation. |
| `payload.cases` | array | A frozen copy of every case definition, including detectors. |

## 3. Replay fixture — `fixtures/replay/<key>.json`

One recorded model response. 122 of them; all `blinded-agent-capture`.

| Field | Type | Definition |
|---|---|---|
| `schema` | string | `ssf-hve/replay-fixture/1` |
| `key` | string | `sha256("ssf-hve/v1\n" + role + "\n" + model + "\n" + rendered_prompt)`. Also the filename. |
| `role` | string | The sample-scoped role, e.g. `a3-split-modelchecks-c0#s1`. **The sample index enters the key here, never through the prompt.** |
| `model` | string | Configured model identifier. The serving model may have differed; see `PROVENANCE.md`. |
| `provenance` | enum | `live-api` \| `blinded-agent-capture` \| `handcrafted`. Anything else is refused. |
| `captured_utc` | string | Capture timestamp. |
| `rendered_prompt` | string | The exact prompt. `fixtures` re-derives the key from it. |
| `response_text` | string | The exact response, unparsed. |
| `input_tokens`, `output_tokens`, `estimated_cost_usd` | int \| null | Null throughout: the capture harness did not expose them. Recorded as null rather than estimated. |
| `note` | string | How it was captured. |

## 4. Run record — `results/runs/<run_id>.json`

The complete evidence for one execution. `schema: ssf-hve/run/1`.

**`meta`**

| Field | Type | Definition |
|---|---|---|
| `run_id` | string | `C<NN>-<config>-s<N>-<8 hex>`. Validated before it touches a path. |
| `case_id`, `config_id`, `condition` | string | What ran. |
| `provider`, `model`, `mode` | string | `replay` or `live`. |
| `started_utc`, `finished_utc`, `wall_clock_s` | string, float | Timing. |
| `model_calls` | integer | Includes calls whose response was **rejected** by schema validation. |
| `input_tokens`, `output_tokens`, `estimated_cost_usd` | int \| null | Null in replay. |
| `correction_cycles` | integer | Cycles executed, bounded by the configuration. |
| `terminal_status` | enum | `ACCEPT` \| `EDIT` \| `HOLD` \| `MALFORMED` \| `ERROR`. |
| `error` | string | Empty unless the run errored. |

**`config`** — the full configuration as executed, plus `sample`. Every field of
`config.Config`, so a record is interpretable without the code that produced it.

**`steps[]`** — one per model call, in order.

| Field | Type | Definition |
|---|---|---|
| `index`, `role`, `kind` | int, string | Position and purpose. |
| `prompt_sha256` | string | The fixture key actually used. |
| `rendered_prompt`, `response_text` | string | Verbatim. Preserved even when parsing failed. |
| `provenance` | string | Inherited from the fixture. |
| `ok`, `error` | bool, string | Whether the response parsed. |
| `parsed_summary` | object | Compact view of the parsed object. |

**`cycles[]`** — one per correction cycle: `index`, `deterministic_findings[]`, `verifier`,
`blocking_count`, and `action` (`correct:cycleN`, `terminate`, `hold`).

**Top level** — `claim_map` (A1's output, including
`embedded_instruction_text_found_in_source`), `final_script`, `final_narration`, `h1_gate`
(state at write time), and `unresolved_findings[]` — **preserved in full, especially at
`HOLD`**. This is the field that makes `HOLD` meaningful.

## 5. Finding

Produced by A3 and by the deterministic checks.

| Field | Type | Definition |
|---|---|---|
| `id` | string | `F01`… Unique within a result; duplicates are rejected. |
| `severity` | enum | `BLOCKER` \| `MAJOR` \| `MINOR` \| `INFO`. `BLOCKER` and `MAJOR` block. |
| `claim_ref`, `evidence_ref` | string | What is claimed, and what the source says. |
| `quoted_span` | string | The exact text at issue. **Empty is rejected** — an unquotable finding is unactionable. |
| `observation` | string | What was seen, with no action in it. Split from the next field in `iter-4`; that split halved malformed output. |
| `explanation` | string | Why it matters. |
| `recommended_correction` | string | What to do. Advisory: the runner decides. |

## 6. Gate record — `results/gates/H1_<run_id>.json`, `H2_<sha>.json`

`gate_schema_version: ssf-hve/gate-record/v2`. Every field except `signature` is signed.

| Field | Type | Definition |
|---|---|---|
| `gate` | enum | `H1` \| `H2` |
| `gate_schema_version` | string | Unknown values **fail closed**. |
| `purpose` | string | `h1-script-production-approval` \| `h2-submission-package-approval`. Domain separation between gates. |
| `artifact_sha256` | string | H1: the narration. H2: the binding statement. |
| `artifact_kind` | string | Human label. |
| `approver` | string | Typed by the person at the terminal. |
| `approved_utc`, `expires_utc` | string | H1 approvals **expire** (30 days default; the window is chosen at approval time and is itself signed). A record with no expiry, an unparsable expiry, or a past expiry is not an approval. |
| `note` | string | Optional. |
| `binding` | object | What else is bound. See below. |
| `signature` | string | HMAC-SHA-256 over the canonical record, keyed by `SSF_HVE_GATE_SECRET`. |
| `signature_algorithm` | string | Unknown values **fail closed**. |

**H1 `binding`** — `run_id`, `case_id`, `config_id`, `sample`, `narration_sha256`,
`run_record_sha256`, `trajectory_sha256`, `trajectory_md_sha256`, `candidate_sha256`,
`config_sha256`, `exported_trajectory`. All but the last are recomputed from the run record at
check time and compared for strict equality. `exported_trajectory` (`absent` |
`verified-match` | `divergent`) is checked against the files **on disk**, because a hash
recomputed from the run record proves nothing about the artifact a judge actually reads.

**H2 `binding`** — `binding_version`, `archive_filename`, `archive_bytes`, `archive_sha256`,
`manifest_sha256`, `git_commit`, `git_tree_state`, and `video_filename` / `video_bytes` /
`video_sha256` when a video is submitted.

## 7. Provenance binding — `evaluation/provenance_binding.json`

`schema: ssf-hve/provenance-binding/1`

| Field | Type | Definition |
|---|---|---|
| `binding_sha256` | string | Self-hash. Editing the manifest fails its own check. |
| `payload.created_utc` | string | A real clock reading. |
| `payload.harness_version` | string | The package version that wrote it. |
| `payload.case_set_id`, `payload.scoring_policy_version` | string, int | What was in force. |
| `payload.active_gold_table` | string | Path to the table in force. |
| `payload.bound_files` | object | Path → SHA-256 for every input that can change a number: cases, adjudications, prompts, case parsing, configuration, schemas, deterministic checks, scorer, normaliser, report generator, fixture semantics and all 122 fixtures. |
| `payload.results_content_sha256` | string | Content hash of the published results, excluding the generation timestamp. |
| `payload.statement` | string | Plain-language statement of what the binding does and does not prove. |

## 8. Published results — `results/results.json`

| Field | Type | Definition |
|---|---|---|
| `schema`, `generated_utc` | string | Provenance of this file. |
| `gold_table_sha256` | string | Which table produced these numbers. Cross-checked by `verify-provenance`. |
| `configs.<id>.scoring_policy_version` | integer | **A number without its policy version is not interpretable.** |
| `configs.<id>.case_set_id` | string | The declared case set. |
| `configs.<id>.n_cases`, `unsafe_count`, `unsafe_output_rate` | int, float | The primary metric. Denominator is the declared case set, not the successful runs. |
| `configs.<id>.clean_claims_retained` / `_total` / `clean_claim_retention` | int, float | Published at the same prominence, always. |
| `configs.<id>.false_flags`, `verifier_findings`, `false_flag_rate` | int, float | Findings quoting correct material. |
| `configs.<id>.unsafe_by_class`, `missed_defects_by_class` | object | Which defect classes went undetected. |
| `configs.<id>.terminal_statuses`, `h1_states` | object | Distribution of outcomes. |
| `configs.<id>.malformed_runs`, `error_runs`, `outputs_produced` | integer | Failures, counted rather than dropped. |
| `configs.<id>.correction_cycles_total`, `model_calls_total`, `wall_clock_s_total` | number | Cost. |

Per-case detail carries `unsafe_reason`, which names *why* — a fired detector, or a terminal
status — so a rate can always be traced to the runs behind it.
