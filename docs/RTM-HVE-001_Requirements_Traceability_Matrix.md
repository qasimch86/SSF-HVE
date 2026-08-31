# RTM-HVE-001 — Requirements Traceability Matrix

| | |
|---|---|
| **Document** | RTM-HVE-001 |
| **Version** | 1.0 · 2026-08-30 · as-built |
| **Traces** | BRD-HVE-001 → SRD-HVE-001 → HLD/ADD → code → test |

> **Provenance.** Built by reading the code and the test suite. See [`README.md`](README.md).
>
> **This matrix is executable.** `tests/test_rtm.py` parses every row below and fails the build
> if it cites a module that does not exist or a test function that does not exist. It cannot
> rot silently as the code moves — which is the only thing that separates a traceability matrix
> from decoration.

**Reading the columns.** *Module* is where the behaviour lives. *Verified by* names a test
function that fails if the requirement stops holding. Where a requirement is **not** enforced,
the row says so in bold and appears again in §4.

---

## 1. Functional requirements

| Req | Design | Module | Verified by |
|---|---|---|---|
| FR-001 | HLD §5 | `cases.py` | `test_unknown_case_is_reported_clearly`, `test_claim_requires_evidence_reference` |
| FR-002 | HLD §3 | `cases.py` | `test_a2_never_sees_the_raw_source_in_its_prompt` |
| FR-003 | HLD §6 b1 | `cases.py` | `test_the_rendered_source_packet_excludes_the_answer_key`, `test_only_C10_has_a_detector_phrase_that_appears_in_its_own_packet` |
| FR-004 | HLD §5 | `runner.py` | `test_baseline_makes_exactly_one_model_call`, `test_baseline_replay_succeeds_without_a_key` |
| FR-005 | HLD §3 | `agents/a1_analyst.py` | `test_advanced_calls_roles_in_order`, `test_embedded_instruction_obeyed_is_a_blocker` |
| FR-006 | HLD §3 | `agents/a2_designer.py` | `test_a2_never_sees_the_raw_source_in_its_prompt` — **source confinement only; nothing enforces claim-map confinement** |
| FR-007 | ADR-0004 | `checks/deterministic.py` | `test_quantity_not_in_source_is_flagged`, `test_unit_change_is_flagged`, `test_missing_material_limitation_is_flagged`, `test_citation_to_missing_claim_is_flagged`, `test_embedded_instruction_obeyed_is_a_blocker`, `test_source_instruction_quoted_as_a_finding_is_not_obedience` |
| FR-008 | ADR-0004 | `checks/deterministic.py` | `test_checks_never_read_the_gold_table` |
| FR-009 | HLD §6 b3 | `agents/` | `test_agents_never_read_the_planted_defects_or_detectors` |
| FR-010 | ADR-0003 | `agents/a3_verifier.py` | `test_valid_verifier_result_parses`, `test_unknown_recommendation_rejected`, `test_empty_quoted_span_rejected`, `test_duplicate_finding_ids_rejected` |
| FR-011 | ADR-0002 | `schemas.py` | `test_accept_with_blocking_finding_rejected`, `test_verifier_cannot_approve_while_reporting_a_blocker` |
| FR-012 | ADR-0002 | `schemas.py` | `test_malformed_output_fails_closed`, `test_parse_or_fail_closed_converts_schema_error`, `test_extra_field_rejected`, `test_malformed_verifier_output_fails_closed` |
| FR-013 | ADR-0003 | `runner.py` | `test_bounded_correction_loop_stops_at_two_cycles` |
| FR-014 | ADR-0005 | `runner.py`, `config.py` | `test_reaching_the_bound_is_not_success`, `test_removal_experiment_makes_the_bound_look_like_success`, `test_hold_is_unsafe_even_when_every_detector_stays_silent` |
| FR-015 | ADD §4.3 | `runner.py` | `test_run_record_is_written_even_on_failure`, `test_exported_trajectory_keeps_unresolved_findings` |
| FR-016 | ADR-0006 | `providers/replay.py`, `replay/store.py` | `test_hash_changes_with_prompt`, `test_hash_changes_with_role`, `test_hash_changes_with_model`, `test_edited_prompt_invalidates_the_fixture`, `test_missing_fixture_returns_exit_code_3` |
| FR-017 | ADR-0006 | `replay/store.py` | `test_unknown_provenance_is_refused`, `test_tampered_fixture_is_refused`, `test_shipped_fixtures_declare_honest_provenance`, `test_fixture_integrity_command` |
| FR-018 | SEC-005 | `providers/live.py` | `test_live_mode_requires_an_explicit_key`, `test_a_non_https_endpoint_is_refused_even_with_opt_in`, `test_a_custom_https_endpoint_requires_explicit_opt_in` |
| FR-019 | HLD §5 | `scoring/scorer.py` | `test_causal_claim_is_detected`, `test_absent_mode_detects_an_omission`, `test_absent_mode_accepts_paraphrase`, `test_document_scoped_disclaimer_redeems` |
| FR-020 | ADR-0009 | `scoring/scorer.py` | `test_policy_version_is_recorded`, `test_scorer_matches_the_declared_policy`, `test_protocol_still_declares_the_hold_rule`, `test_hold_appears_in_the_unsafe_terminal_states` |
| FR-021 | EVAL_PROTOCOL §5 | `scoring/scorer.py` | `test_denominator_is_the_declared_case_set_not_the_successful_runs`, `test_malformed_run_counts_as_unsafe_and_stays_in_the_denominator`, `test_error_run_counts_as_unsafe` |
| FR-022 | BRD §6 | `scoring/report.py` | `test_clean_claim_retention_counts_retained_material` |
| FR-023 | NFR-003 | `scoring/report.py` | `test_published_results_are_derived_and_deterministic`, `test_the_published_score_table_matches_results_json` |
| FR-024 | ADR-0004, ADR-0005 | `config.py` | `test_removal_experiment_makes_the_bound_look_like_success` |
| FR-025 | HLD §5 | `trajectory/export.py` | `test_api_keys_are_redacted`, `test_authorization_header_is_redacted`, `test_findings_and_failures_survive_redaction` |
| FR-026 | HLD §3 | `rendering/render.py` | `test_the_preview_is_labelled_as_not_the_production_render`, `test_the_instructions_distinguish_production_from_preview`, `test_the_ffmpeg_command_uses_the_declared_preview_resolution`, `test_render_refuses_without_h1` |
| FR-027 | ADR-0005, ADR-0007 | `gates.py` | `test_absence_of_approval_blocks`, `test_non_interactive_approval_is_refused`, `test_wrong_word_is_not_approval`, `test_h1_gate_is_blocked_by_default`, `test_runner_cannot_reach_record_approval`, `test_record_approval_refuses_an_h1_without_binding` |
| FR-028 | ADR-0007 | `submission.py`, `gates.py` | `test_h2_absence_blocks`, `test_h2_statement_changes_when_the_archive_changes`, `test_the_cli_has_no_legacy_narration_h2_route`, `test_only_the_complete_byte_identical_submission_set_gets_the_commit` |
| FR-029 | ADR-0007 | `gates.py` | `test_a_real_approval_verifies_and_binds`, `test_an_unsigned_record_is_not_an_approval`, `test_a_handwritten_record_is_not_an_approval`, `test_editing_any_signed_field_breaks_the_signature`, `test_a_signature_from_a_different_secret_is_refused`, `test_an_unknown_signature_algorithm_fails_closed_even_when_resigned`, `test_a_stale_approval_is_refused_by_the_freshness_policy` |
| FR-030 | ADR-0010 | `provenance.py` | `test_the_binding_exists_and_covers_the_active_surfaces` |
| FR-031 | ADR-0010 | `provenance.py` | `test_the_audit_probe_editing_active_c05_now_fails_verification`, `test_editing_the_scorer_fails_verification`, `test_editing_a_prompt_template_fails_verification`, `test_an_unbound_extra_fixture_fails_verification`, `test_editing_the_binding_file_itself_fails_its_self_hash` |
| FR-032 | ADD §5 | `packaging.py` | `test_the_scanner_covers_exactly_what_ships`, `test_every_shipped_file_is_scanned`, `test_selection_includes_direct_children_of_doublestar_patterns` |
| FR-033 | HLD §8 | `ui/` | `test_ui_startup_serves_the_home_page`, `test_the_ui_offers_no_gate_approval_control`, `test_the_ui_has_no_key_entry_form`, `test_run_page_renders_the_full_evidence`, `test_gate_status_is_presented_with_the_reason` |
| FR-034 | ADD §5 | `cli.py` | `test_hold_returns_exit_code_2`, `test_malformed_returns_exit_code_2`, `test_missing_fixture_returns_exit_code_3`, `test_gate_status_reports_not_approved`, `test_unknown_command_is_a_usage_error` |

## 2. Non-functional requirements

| Req | Module | Verified by |
|---|---|---|
| NFR-001 | `pyproject.toml` | `test_the_ui_imports_only_stdlib_and_ssf_hve`, `test_the_ui_carries_no_foreign_framework_or_asset_references` |
| NFR-002 | `providers/` | `test_only_the_live_provider_can_reach_the_network`, `test_the_replay_provider_reaches_only_the_filesystem`, `test_replay_provider_does_no_network_io`, `test_the_documented_offline_claim_names_its_exceptions` |
| NFR-003 | `scoring/report.py` | `test_published_results_are_derived_and_deterministic` |
| NFR-004 | `packaging.py` | `test_only_the_complete_byte_identical_submission_set_gets_the_commit` + the release procedure in TSP §5 |
| NFR-005 | `providers/replay.py` | Measured, not asserted: wall-clock totals in `results/results.json` |
| NFR-006 | `scoring/report.py` | `test_the_published_score_table_matches_results_json`, `test_model_call_total_matches_the_published_results` |
| NFR-007 | — | `test_every_count_claim_in_every_shipped_document_is_true`, `test_test_count_is_stated_correctly`, `test_run_record_count_is_stated_correctly`, `test_fixture_count_is_stated_correctly` |

## 3. Security requirements

| Req | Module | Verified by |
|---|---|---|
| SEC-001 | `providers/live.py`, `gates.py` | `test_live_mode_requires_an_explicit_key`, `test_no_env_files_are_tracked`, `test_the_ui_has_no_key_entry_form` |
| SEC-002 | `trajectory/export.py`, `gates.py` | `test_api_keys_are_redacted`, `test_the_signature_is_not_the_secret`, `test_the_secret_is_never_written_to_disk_by_this_module`, `test_fixtures_carry_no_secrets`, `test_no_secret_value_ever_reaches_a_page`, `test_the_refusal_message_never_contains_a_key` |
| SEC-003 | `gates.py` | `test_verification_fails_closed_when_no_secret_is_configured`, `test_an_empty_secret_is_the_same_as_no_secret`, `test_comparison_is_constant_time`, `test_a_copied_record_does_not_approve_another_run_with_identical_narration`, `test_a_modified_run_record_invalidates_the_approval` |
| SEC-004 | `paths.py` | `test_path_traversal_is_refused`, `test_malformed_identifiers_are_refused`, `test_refusal_never_returns_a_sanitised_value`, `test_run_id_traversal_is_refused_everywhere`, `test_download_paths_are_contained` |
| SEC-005 | `providers/live.py` | `test_a_non_https_endpoint_is_refused_even_with_opt_in`, `test_an_https_url_without_a_host_is_refused`, `test_a_non_affirmative_opt_in_does_not_count` |
| SEC-006 | `ui/` | `test_the_ui_server_binds_localhost_only`, `test_posts_without_the_csrf_token_are_refused`, `test_live_mode_requires_the_server_flag`, `test_the_ui_writes_runs_only_to_the_session_directory` |
| SEC-007 | `tests/test_secrets.py` | `test_no_credentials_anywhere`, `test_no_private_filesystem_paths_leak`, `test_the_scanner_covers_exactly_what_ships`, `test_every_shipped_file_is_scanned` |
| SEC-008 | — | `test_no_commercial_source_markers` |

## 4. Constraints, and the four rows with no test behind them

| Req | Verified by |
|---|---|
| CON-001 | `test_the_cli_has_no_legacy_narration_h2_route`; no network module outside `providers/live.py` (`test_only_the_live_provider_can_reach_the_network`) |
| CON-002 | `test_live_mode_is_never_reached_by_omission`, `test_only_the_cli_can_ask_for_live_and_only_behind_the_flag` |
| CON-003 | `test_the_ui_has_no_key_entry_form`, `test_the_ui_uses_no_database` |
| CON-004 | Not testable. The case set is synthetic by construction; the claim is a disclosure, not a property. |

**Requirements with no enforcement, listed so nobody has to find them:**

| Req | What is untested, and why |
|---|---|
| **FR-006** | A2's confinement to the claim map. The prompt instructs it; nothing checks the output against the claim map. The system's largest unenforced boundary. |
| **FR-017** | That a capture session saw only the rendered prompt. Provenance is a declared value; no test can verify it after the fact. |
| **FR-026** | That A4 never alters scientific wording. A design property of the assembler, not a checked invariant of its output. |
| **SEC-003** | Key compromise. Approvals are tamper-*evident*; anyone holding the secret can mint one, and there is no rotation or revocation. |

## 5. Coverage summary

| Category | Requirements | With a named test | Without |
|---|---|---|---|
| Functional | 34 | 34 | 0 |
| Non-functional | 7 | 7 | 0 |
| Security | 8 | 8 | 0 |
| Constraints | 4 | 3 | 1 (CON-004, not testable) |

Every requirement has at least one test that fails if it stops holding. That is a statement
about *the requirements as written* — which were written from the code. It is not evidence that
the requirements are the right ones, and §4 is where the honest gaps are.
