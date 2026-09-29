# IntentBond requirements

**The maintainer has accepted these requirements and the root checking scope.**

This is the maintained product contract. Its initial 35 requirements were
recovered from commit `4fe67034f02cbf977e0aa0b5708ba9b921d6cd60`.
Each requirement retains its origin. The root [scope](../scope.json) selects the
checking policy, including `examples/` as additional review paths outside the
product trace graph.

Recovery provenance is retained in Git history at adoption commit
`48fe9f4aa9d5718c35407443dd772b7f7b78f26f`: the
[source and claims records](https://github.com/kbak/intentbond/commit/48fe9f4aa9d5718c35407443dd772b7f7b78f26f)
preserve the original source identity, quotations, locations, and recovery notes.
They are archived evidence and are no longer kept in the current tree.
Acceptance records a review decision; structural links and suite outcomes provide
supporting evidence within the limits described below.

## Checking scope

The root scope imports runtime code, all Python tests, maintained guides,
packaged skills and build/test configuration. `examples/` is selected through
`review_paths`; its files are captured and used by existing tests, while its
illustrative requirements stay outside the product graph. Recovery records retain
provenance separately from the live trace links.
The command runs the existing Python suite with the committed opt-in pytest 9.1.1
adapter and a fresh JUnit report. The scope governs ordinary `ib check` runs;
CI automation is configured separately in [.github/workflows/ci.yml](../.github/workflows/ci.yml).

The recovery was checked using a matching installed wheel outside the repository.
Checker and subject share a code lineage, so self-application provides integration
evidence rather than independent certification. Retained results identify the
exact source checked and the tests run.

The recovery added standalone coverage comments to existing code and assertions.
These links make the accepted promises navigable without changing executable
behavior. Assertion adequacy, completeness, and future maintenance cost remain
subjects for ongoing review.

## Maintaining requirements

For each commit, keep affected promises, reference documentation, implementation,
and test assertions consistent through the [development workflow](../CONTRIBUTING.md#make-a-change).
Update this contract as behavior evolves. The archived recovery claims preserve
the original source evidence; ongoing caveats and follow-ups belong in this
maintained contract.

Keep IDs stable for continuing promises, including document moves. Several clauses
can describe the outcomes or exceptions of one operation. Consider a split when
one promise needs to evolve independently, following the
[granularity guide](requirement-granularity.md).

## Feature map

Each mapped requirement is accepted and has supporting implementation and test
links. The map also identifies deferred areas and evidence limits. All IDs use
`req~ib-…~1`.

| Capability | Accepted mapping | Boundary or review focus |
| --- | --- | --- |
| Baseline and policy | policy-source, baseline-selection | External-policy trust; further ambiguous-merge-base and schema cases. |
| Tracing and revisions | coverage, revision-policy, empty-scope, python-annotations | Real Python comments only; other languages keep OFT recognition. |
| Source capture | source-identity, safe-symlinks, source-stability | Preserve exclusions and the change-then-restore observation limit. |
| Test results | junit-completion, fresh-reports, report-merge, command-results, pytest-subtests | Parent/subtest counts are separate; pin and plugin compatibility remain explicit. |
| Individual execution | execution-associations, required-execution | No individual execution metadata is authored in this exercise. |
| Evidence and review | evidence-verification, change-review, boundary-report, review-selection | Review fixtures without importing their illustrative requirements; producer trust remains external. |
| Inspection and impact | explain-context, impact-report, draft-reporting | Draft/coverage/trace/review states stay separate; no review-time benefit measured. |
| Recovery | recovery-preservation, recovery-clean-start, recovery-citations, recovery-edits, recovery-lineage, recovery-draft-status, recovery-preflight | Citation validity does not prove faithful or complete extraction. |
| Alloy | alloy-assertions, alloy-witness | Native bounds; remaining manifest/input-binding/error contracts need decomposition. |
| SMT | smt-assumptions, smt-outcomes | Results concern the encoding, not automatic equivalence to application behavior. |
| CHC/Spacer | chc-certificates | Invariant/trace obligations do not establish liveness or application equivalence. |
| Packaging, installation and platforms | Deferred | Existing CI jobs are not replaced by this local Python check. |
| Agent extraction and semantic review | Deferred | Review preserved exceptions and unsupported wording against original citations. |
| Example applications / external IntentMade integration | Outside product requirement graph | Examples remain captured and selected for review; external integration is a separate project. |

## Existing properties and follow-ups

These are discovery notes. No new tests, generators or formal proofs are authored.
Any follow-up requires reviewed intent and subsequent development.

| Requirement(s) | Existing checks and domain | Potential follow-up |
| --- | --- | --- |
| source-identity | Snapshot properties: 1–4 selected paths, bytes up to 32, executable modes; 30 examples per property. | Medium: broader path/link combinations while retaining deterministic symlink cases. |
| junit-completion, report-merge, pytest-subtests | Generated merges: 1–4 reports, 1–12 final outcomes each; 100 examples. New serial producer regressions cover repeated contexts, failures, skips and setup/teardown errors. | Medium: decide supported parallel/retry/plugin combinations before extending producer guarantees; preserve omission rejection. |
| revision-policy, change-review, review-selection | Generated revisions and bounded lifecycle edits; review-only fixture selection and trusted-policy mismatch regressions. | Medium: assess mixed policy changes and file moves; keep trust and review scope explicit. |
| python-annotations, recovery-edits | Comment/string, physical-line, encoding, malformed-input and source-preservation regressions. | Medium: review additional supported Python lexical forms and executable-document boundaries before broadening guarantees. |
| draft-reporting | Native OFT checks cover linked drafts with no uncovered types and drafts with a genuinely missing test link. | Review whether wording makes the distinction clear to maintainers; no user-study result is claimed. |
| recovery-citations, recovery-lineage | Exact citation and original-ID accounting regressions. | High: inspect the map for omitted exceptions, combined clauses and unjustified links; automation cannot perform this semantic review. |

## Requirements

The initial requirements are documented in the original source at the fixes
commit. Their selection and wording have been accepted. `Needs: impl, utest` requires
structural links; it does not mean one assertion proves the whole statement.
Exact source quotations and line ranges are retained in the archived claims record
linked above.

### Use the selected baseline policy
`req~ib-policy-source~1`

Ordinary checks and verification use scope.json from the resolved baseline commit. Candidate policy edits do not change those rules. An explicit --scope selects the supplied file as-is; a missing or invalid baseline scope must not fall back to the working copy.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/config.py](../intentbond/config.py), [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_cli_default_scope_cannot_be_weakened_by_candidate_edits](../tests/test_workflow.py); [test_cli_missing_baseline_scope_does_not_fall_back_to_worktree](../tests/test_workflow.py); [test_cli_invalid_baseline_scope_does_not_fall_back_to_valid_worktree_file](../tests/test_workflow.py).

Evidence limit: Trust in the caller-selected external policy remains an assumption, not a filesystem-location guarantee.

### Resolve the default comparison baseline
`req~ib-baseline-selection~1`

Without --base, use existing refs to select the unique merge base of HEAD and the default branch, preferring its local tip when available. On that branch or detached HEAD use HEAD. Require an explicit baseline when the default branch or a unique merge base cannot be determined; do not fetch refs.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/cli.py](../intentbond/cli.py).

Existing assertions: [test_cli_branch_default_includes_commits_and_edits_using_original_scope](../tests/test_workflow.py); [test_cli_remote_default_branch_uses_local_tip_when_available](../tests/test_workflow.py); [test_cli_unknown_default_branch_requires_explicit_base](../tests/test_workflow.py); [test_cli_detached_head_defaults_to_checked_out_commit](../tests/test_workflow.py).

Evidence limit: The documented main/master fallback and ambiguous-merge-base cases still need a dedicated evidence review.

### Validate both graphs and the required coverage
`req~ib-coverage~1`

Both selected versions must pass OFT tracing and the configured coverage floors. Missing implementation/test links and stale requirement revisions remain defects; a candidate cannot waive required Needs by editing its scope.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/runner.py](../intentbond/runner.py), [intentbond/oft.py](../intentbond/oft.py).

Existing assertions: [test_missing_implementation_reference](../tests/test_workflow.py); [test_missing_test_reference](../tests/test_workflow.py); [test_stale_revision_reference](../tests/test_workflow.py); [test_removed_needs_cannot_turn_green_by_editing_candidate_policy](../tests/test_workflow.py); [test_inherited_baseline_defect_is_not_silently_absorbed](../tests/test_workflow.py).

Evidence limit: The Python comment-token importer isolates fixture text; structural links still do not establish assertion adequacy.

### Enforce the optional revision policy
`req~ib-revision-policy~1`

When require_revision_increase is true, changed imported requirement content needs a higher revision and revisions must not decrease. When false, revision changes are left to review; OFT reference revisions are still checked.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/review.py](../intentbond/review.py).

Existing assertions: [test_changed_promise_remains_reviewable_and_needs_higher_revision](../tests/test_revision_properties.py); [test_prose_change_is_pending_review_without_mandatory_revision_bump](../tests/test_workflow.py).

### Keep selected semantic changes pending review
`req~ib-change-review~1`

If automated checks pass, changes within selected specification paths, test paths or additional review_paths require external review, including prose and file changes beyond requirement metadata. Passing tests and --allow-pending-review do not clear that review requirement.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/review.py](../intentbond/review.py), [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_passing_test_edit_stays_reviewable_without_an_approval_file](../tests/test_workflow.py); [test_pending_review_cannot_be_relabelled_as_success](../tests/test_workflow.py); [test_review_only_fixtures_trigger_bound_review_without_importing_examples](../tests/test_boundaries.py).

### Never report empty scope as successful coverage
`req~ib-empty-scope~1`

An empty selected candidate normally fails. With allow_empty enabled it may report empty (exit 3) only when no other check fails; it does not establish successful coverage or test execution.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_empty_scope_requires_explicit_non_success](../tests/test_workflow.py).

### Bind checks to captured paths, modes and bytes
`req~ib-source-identity~1`

Capture commit source from Git blobs and working-tree source from tracked files plus nonignored untracked files, including files outside trace inputs. Identify the sorted path/mode/content manifest with the documented canonical SHA-256 digest. Tracing and tests consume the captured candidate; ignored untracked files, Git metadata and external environment inputs are excluded.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/snapshot.py](../intentbond/snapshot.py).

Existing assertions: [test_git_and_archive_agree_before_and_after_staging](../tests/test_snapshot_properties.py); [test_path_bytes_and_mode_each_change_identity_and_restore_exactly](../tests/test_snapshot_properties.py); [test_ignored_noise_is_excluded_but_tracked_ignored_source_is_retained](../tests/test_snapshot_properties.py); [test_git_export_ignore_does_not_omit_source](../tests/test_workflow.py).

Evidence limit: Existing generated cases use 1–4 selected paths and byte strings of at most 32 bytes. Symlinks and concurrent writers are outside that generator.

### Preserve internal symlinks and reject unsafe targets
`req~ib-safe-symlinks~1`

Preserve relative internal symlink target bytes and mode 120000, including dangling internal links. Reject absolute, escaping, cyclic and Git-metadata targets. OFT must import actual files without following aliases; explicitly selected aliases require selection of their actual source paths.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/snapshot.py](../intentbond/snapshot.py), [intentbond/oft.py](../intentbond/oft.py).

Existing assertions: [test_snapshots_preserve_link_bytes_and_modes_including_dangling_links](../tests/test_symlinks.py); [test_unsafe_and_cyclic_links_fail_in_commit_and_worktree_snapshots](../tests/test_symlinks.py); [test_checks_run_with_links_but_trace_each_actual_file_once](../tests/test_symlinks.py); [test_explicit_alias_input_requests_the_actual_path](../tests/test_symlinks.py).

### Reject detected source changes during checking
`req~ib-source-stability~1`

Check captured source and the original candidate around execution. Detected mutations reject the check, and changed or unchecked source suppresses the test attestation. A mutation restored before the final observation is outside this guarantee.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_test_command_repair_cannot_attest_original_broken_candidate_passed](../tests/test_workflow.py); [test_unchecked_source_cannot_produce_a_test_attestation](../tests/test_workflow.py); [test_original_candidate_changes_during_validation](../tests/test_workflow.py).

### Require complete passing JUnit execution
`req~ib-junit-completion~1`

JUnit success requires command exit 0, at least one passing case, and no failures or errors, including suite-level failures. Empty and entirely skipped suites fail. Mixed skips are allowed by default and rejected when allow_skipped_tests is false. Inconsistent reports cannot supply missing execution evidence. Reject XML DTDs and entity declarations regardless of encoding.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/testing.py](../intentbond/testing.py).

Existing assertions: [test_merge_preserves_outcomes_and_completion_policy](../tests/test_report_properties.py); [test_suite_failure_survives_passing_cases_and_merge](../tests/test_report_properties.py); [test_missing_reported_cases_are_rejected](../tests/test_report_properties.py); [test_zero_discovered_tests](../tests/test_workflow.py); [test_skipped_test](../tests/test_workflow.py); [test_doctype_is_rejected_in_supported_xml_encodings](../tests/test_reports.py); [test_supported_xml_encodings_and_predefined_entities_remain_valid](../tests/test_reports.py).

Evidence limit: The generated merge domain is 1–4 reports with 1–12 final outcomes each; it does not cover arbitrary XML or every producer dialect.

### Require fresh reports inside the captured candidate
`req~ib-fresh-reports~1`

Every configured JUnit report must be a fresh regular file within the captured candidate. A pre-existing report or a missing output cannot establish a successful run, even if the command exits zero.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/testing.py](../intentbond/testing.py).

Existing assertions: [test_stale_report_is_rejected](../tests/test_workflow.py); [test_missing_report_even_when_command_returns_zero](../tests/test_workflow.py); [test_missing_or_stale_report_is_rejected](../tests/test_mixed_reports.py).

### Retain and combine all configured reports
`req~ib-report-merge~1`

For multiple configured JUnit outputs, retain each original and a combined report, preserving failures and completion information. Verification must reject a missing retained report or a combined report inconsistent with its retained originals.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/testing.py](../intentbond/testing.py), [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_reports_are_retained_combined_and_verified](../tests/test_mixed_reports.py); [test_failure_or_incomplete_second_report_cannot_hide_behind_first](../tests/test_mixed_reports.py).

### Distinguish command success from counted test execution
`req~ib-command-results~1`

Command-format checks record the configured command outcome and logs. Exit zero may satisfy command-format completion, but must not invent case counts or individual skip results.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/testing.py](../intentbond/testing.py).

Existing assertions: [test_command_adapter_uses_real_execution_without_claiming_case_counts](../tests/test_workflow.py); [test_command_results_do_not_gain_test_counts](../tests/test_explain.py).

### Keep linked execution distinct from suite success
`req~ib-execution-associations~1`

With the optional JUnit execution-link profile, associate observations with exact OFT test-artifact revisions and reject invalid supplied identities. Missing observations stay visible; a passing suite alone does not establish that a linked test ran.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/execution.py](../intentbond/execution.py).

Existing assertions: [test_unknown_stale_requirement_and_out_of_scope_ids_are_invalid](../tests/test_execution.py); [test_passing_suite_cannot_hide_a_missing_linked_test](../tests/test_execution.py).

Evidence limit: The self-recovery scope does not add execution metadata to existing tests: its added links are structural, while JUnit evidence describes the suite.

### Enforce required linked test observations
`req~ib-required-execution~1`

Each configured required execution key must resolve to exactly one selected candidate test-artifact revision and have a passing observation. Missing, skipped, ambiguous or nonpassing observations reject the check; verification enforces the retained rule as well.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/execution.py](../intentbond/execution.py), [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_required_execution_rejects_nonpassing_observations](../tests/test_execution.py); [test_required_identity_follows_one_revision_but_rejects_missing_or_multiple](../tests/test_execution.py); [test_verify_rechecks_required_execution_after_top_level_outcome_is_forged](../tests/test_execution.py).

### Match retained evidence to policy and source
`req~ib-evidence-verification~1`

Verification checks retained artifacts and outcomes against the selected trusted scope, baseline and candidate contents without rerunning tests. Changed artifacts, policy or source invalidate the match. Matching hashes do not authenticate the unsigned producer.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_evidence_detects_dependency_scope_base_and_artifact_changes](../tests/test_workflow.py); [test_valid_dirty_candidate_can_match_later_exported_commit](../tests/test_workflow.py); [identity_and_evidence_follow_contents](../tests/test_lifecycle_properties.py).

Evidence limit: This exercise uses the same project lineage for checker and subject, so agreement is not independent validation. Producer trust remains external.

### Explain retained graph context without rerunning the project
`req~ib-explain-context~1`

Explain validates retained source/scope bindings and asks pinned OFT for graph relationships. It reports exact requested IDs, immediate links and recorded result context without requiring the source checkout or rerunning project tests. Coverage and suite success must remain distinct from individual execution.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/explain.py](../intentbond/explain.py).

Existing assertions: [test_cli_uses_relocated_bundle_without_repo_or_test_execution](../tests/test_explain.py); [test_oft_reports_both_directions_and_keeps_execution_separate](../tests/test_explain.py); [test_base_selection_does_not_attribute_candidate_tests_to_old_requirement](../tests/test_explain.py).

### Report structural change without claiming adequacy or saved effort
`req~ib-impact-report~1`

Impact compares retained declarations and exact edges, distinguishing normative text changes from link/revision-only changes. Recorded source classifications distinguish recognized annotation-only edits from implementation or test-body edits. These counts do not establish assertion adequacy or reduced human review effort.

Needs: impl, utest

Original documentation: [docs/requirement-granularity.md](requirement-granularity.md).

Implementation: [intentbond/impact.py](../intentbond/impact.py).

Existing assertions: [test_policy_change_affects_only_cap_promise_and_consumers](../tests/test_impact.py); [test_revision_only_annotations_are_distinct_and_do_not_establish_adequacy](../tests/test_impact.py); [test_test_body_edit_cannot_be_hidden_by_relinking](../tests/test_impact.py).

### Expose source paths outside selected review boundaries
`req~ib-boundary-report~1`

Report changed captured paths and their membership in tracing and selected review roots. A captured file outside those roots still contributes to source identity; editing it invalidates matching evidence without implying its meaning was reviewed.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/boundaries.py](../intentbond/boundaries.py).

Existing assertions: [test_outside_docs_are_counted_hashed_and_reject_stale_evidence](../tests/test_boundaries.py).

### Preserve the original and leave recovery uncommitted
`req~ib-recovery-preservation~1`

Recovery retains original source and inventory for citations. In-place preparation leaves HEAD and branch unchanged, saves review records and leaves changes uncommitted. Isolated mode prepares a separate draft. Preparation does not execute project tests.

In-place records use `.intentbond/recovery/`, which stays outside the live trace
graph. Records are required during recovery checks and review, but ordinary
checks and verification after adoption do not require them in the current tree.
Retain provenance in Git history or durable artifact storage before cleanup.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_default_preparation_preserves_snapshot_and_leaves_git_review_records](../tests/test_recovery_in_place.py); [test_prepare_preserves_source_and_records_inventory_without_tests](../tests/test_recovery.py); [test_recovery_records_can_be_archived_outside_the_adopted_tree](../tests/test_recovery_in_place.py); [test_historical_quoted_annotations_cannot_supply_live_coverage](../tests/test_recovery_in_place.py).

### Require a clean HEAD checkout for in-place recovery
`req~ib-recovery-clean-start~1`

In-place recovery requires a clean index and working tree, including untracked files, with source matching HEAD. Existing local changes are preserved on rejection; another source version requires isolated recovery.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md), [intentbond/skills/recover-baseline/SKILL.md](../intentbond/skills/recover-baseline/SKILL.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_dirty_checkouts_fail_before_writing_recovery_files](../tests/test_recovery_in_place.py); [test_other_source_version_requires_isolation](../tests/test_recovery_in_place.py).

### Validate claims against original source quotations
`req~ib-recovery-citations~1`

Every selected recovered item requires provenance. A documented claim requires an intent citation; each citation identifies inventoried original text with matching complete line quotations. Generated wording cannot be its own historical source. Citation validation does not establish semantic support or approval.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_citations_cannot_be_invented_or_self_supporting](../tests/test_recovery.py); [test_missing_provenance_and_duplicate_claims_fail](../tests/test_recovery.py).

### Preserve executable source and existing tests during recovery
`req~ib-recovery-edits~1`

Outside selected editable specification documents, recovery permits only standalone coverage-comment changes and preserves existing files and modes. It rejects added executable tests as historical evidence. Specification rewrites require cited document-change records.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_logic_or_document_changes_are_not_hidden_by_recovery](../tests/test_recovery.py); [test_new_tests_cannot_manufacture_existing_evidence](../tests/test_recovery.py); [test_unstructured_readme_can_be_rewritten_with_original_citations](../tests/test_recovery_documents.py); [test_recovery_rejects_changed_string_contents_but_accepts_comment_changes](../tests/test_python_annotations.py); [test_review_only_markdown_does_not_grant_recovery_rewrite_permission](../tests/test_annotation_diagnostics.py).

Evidence limit: Python annotation-looking string contents remain protected. Review-only Markdown does not gain specification rewrite permission. Other languages and executable Markdown still need contextual review; comment edits can change source line numbers.

### Account for changed original requirement identities
`req~ib-recovery-lineage~1`

Account for original authored OFT IDs within inventoried specification documents. Unchanged identity/content may map automatically; rewrites, revisions, splits, merges and removals require valid explicit mappings and reasons. A mapping does not grant semantic acceptance.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_reworded_requirement_needs_explicit_accounting_even_with_same_id](../tests/test_recovery_documents.py); [test_split_requires_complete_valid_targets](../tests/test_recovery_documents.py); [test_removed_original_design_id_cannot_disappear_through_coverage_policy](../tests/test_recovery_documents.py).

### Keep optional item status separate from recovery review
`req~ib-recovery-draft-status~1`

Requirement status is optional; explicit statuses and full coverage obligations are preserved during validation. Successful recovery remains review_required; neither a documented origin nor passing checks approves the recovered promise or adopts the baseline.

Needs: impl, utest

Original documentation: [intentbond/skills/recover-baseline/references/recovery.md](../intentbond/skills/recover-baseline/references/recovery.md).

Implementation: [intentbond/recovery.py](../intentbond/recovery.py).

Existing assertions: [test_documented_and_inferred_drafts_remain_pending_review_after_checks](../tests/test_recovery_status.py); [test_draft_status_does_not_hide_missing_test_coverage](../tests/test_recovery_status.py).

### Keep preflight distinct from passing validation
`req~ib-recovery-preflight~1`

Recovery preflight checks edits, citations and tracing without running tests. An otherwise clean preflight is incomplete (exit 5), produces no passing test attestation and cannot be verified as successful evidence even with pending review allowed.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/runner.py](../intentbond/runner.py).

Existing assertions: [test_preflight_validates_provenance_without_tests_or_passing_evidence](../tests/test_recovery_feedback.py).

### Interpret Alloy assertion results under native bounds
`req~ib-alloy-assertions~1`

For an Alloy assertion check, a satisfiable result is a counterexample and fails even when the analyzer process exits zero. An unsatisfiable result means no counterexample within the recorded native bounds, not an unbounded proof about application code.

Needs: impl, utest

Original documentation: [docs/model-checking.md](model-checking.md).

Implementation: [intentbond/alloy.py](../intentbond/alloy.py).

Existing assertions: [test_counterexample_is_a_failure_even_when_alloy_exits_zero](../tests/test_alloy.py); [test_completed_checks_and_self_contained_junit](../tests/test_alloy.py).

### Reject unsatisfiable required Alloy witnesses
`req~ib-alloy-witness~1`

A selected Alloy witness run must be satisfiable. An impossible witness fails even when assertion checks find no counterexample; witnesses alone do not establish model adequacy.

Needs: impl, utest

Original documentation: [docs/model-checking.md](model-checking.md).

Implementation: [intentbond/alloy.py](../intentbond/alloy.py).

Existing assertions: [test_impossible_witness_is_not_vacuous_success](../tests/test_alloy.py).

### Require satisfiable SMT assumptions
`req~ib-smt-assumptions~1`

Before treating an SMT obligation as established, require satisfiable assumptions. Unsatisfiable preconditions must fail instead of yielding a vacuous proof.

Needs: impl, utest

Original documentation: [docs/model-checking.md](model-checking.md).

Implementation: [intentbond/smt.py](../intentbond/smt.py).

Existing assertions: [test_unsatisfiable_preconditions_cannot_prove_anything](../tests/test_smt.py).

### Distinguish SMT proof, counterexample, witness and unknown
`req~ib-smt-outcomes~1`

Under satisfiable assumptions, UNSAT for a negated check goal establishes the goal under its encoding; SAT is a failing counterexample. Required witness queries need SAT. An unknown result is inconclusive and an error, with native query/result evidence retained.

Needs: impl, utest

Original documentation: [docs/model-checking.md](model-checking.md).

Implementation: [intentbond/smt.py](../intentbond/smt.py).

Existing assertions: [test_real_proof_witness_and_retained_queries](../tests/test_smt.py); [test_counterexample_is_failure_even_when_worker_succeeds](../tests/test_smt.py); [test_unsatisfiable_witness_fails_without_rejecting_valid_proof](../tests/test_smt.py); [test_unknown_is_inconclusive_with_reason_retained](../tests/test_smt.py); [test_model_supports_dataclasses_with_postponed_annotations](../tests/test_smt.py); [test_command_names_do_not_collide_with_evidence_directories](../tests/test_smt.py).

### Validate Spacer certificates and reconstructed traces
`req~ib-chc-certificates~1`

A safe CHC result requires an SMT-validated invariant for initialization, every transition and target exclusion. A reachable result requires a validated concrete trace. Vacuous initial states, unknown outcomes and invalid or incomplete certificates cannot pass. Model-level safety does not establish application equivalence or liveness.

Needs: impl, utest

Original documentation: [docs/model-checking.md](model-checking.md).

Implementation: [intentbond/chc.py](../intentbond/chc.py).

Existing assertions: [test_safety_certificate_trace_and_portable_polarity](../tests/test_chc.py); [test_bad_certificate_and_infeasible_trace_are_rejected](../tests/test_chc.py); [test_no_initial_states_is_not_a_proof](../tests/test_chc.py); [test_incomplete_evidence_cannot_pass](../tests/test_chc.py); [test_unknown_from_unsupported_theory_is_not_a_pass](../tests/test_chc.py); [test_model_supports_dataclasses_with_postponed_annotations](../tests/test_chc.py); [test_command_names_do_not_collide_with_evidence_directories](../tests/test_chc.py).

### Import Python annotations only from actual comments
`req~ib-python-annotations~1`

For selected Python files, import trace tags only from actual comment tokens; strings, docstrings and embedded fixture examples must not contribute tags. Preserve original relative paths and physical line numbers in the import view without changing captured or executed source. Tokenization errors stop import with a file-specific diagnostic.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/python_comments.py](../intentbond/python_comments.py), [intentbond/oft.py](../intentbond/oft.py).

Existing assertions: [test_strings_are_absent_and_comment_locations_are_preserved](../tests/test_python_annotations.py); [test_encodings_and_physical_newlines](../tests/test_python_annotations.py); [test_unterminated_string_cannot_hide_annotations](../tests/test_python_annotations.py); [test_real_oft_ignores_examples_retains_comments_and_source_bytes](../tests/test_python_annotations.py); [test_comment_link_to_missing_requirement_still_fails](../tests/test_python_annotations.py).

Evidence limit: The interpreter running the checker must understand the source lexical syntax. Other languages retain native OFT recognition; no general multi-language parser guarantee is inferred.

### Retain complete subtest cases with the pinned opt-in producer
`req~ib-pytest-subtests~1`

When explicitly enabled with pytest 9.1.1 and JUnit output, the subtest producer adapter emits a distinct complete case for each reported subtest while retaining parent cases, native outcomes, properties and output. Execution and exit status remain pytest results, and the consumer completeness check is unchanged. With JUnit enabled, an unsupported pytest version is rejected.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/pytest_junit.py](../intentbond/pytest_junit.py).

Existing assertions: [test_unittest_subtests_are_separate_cases_with_stable_names](../tests/test_pytest_junit.py); [test_mixed_subtest_outcomes_and_setup_teardown_errors_survive](../tests/test_pytest_junit.py); [test_unsupported_producer_version_stops_before_writing_junit](../tests/test_pytest_junit.py); [test_skips_still_obey_policy_and_deleted_cases_are_rejected](../tests/test_pytest_junit.py); [test_collection_errors_remain_errors](../tests/test_pytest_junit.py); [test_unittest_failures_skips_and_exceptions_are_retained](../tests/test_pytest_junit.py).

Evidence limit: The adapter uses pinned producer internals. The existing tests cover serial pytest/unittest subtests, not every third-party plugin or parallel/retry interaction. Parent cases and subcases are counted separately.

### Select extra review paths independently of tracing
`req~ib-review-selection~1`

Optional review_paths selects additional literal repository-relative paths for semantic review and is bound to the trusted scope and evidence identity. It does not add or subtract OFT inputs, create requirements, or satisfy trace links. Specification and test selections retain their existing containment rules.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/config.py](../intentbond/config.py), [intentbond/review.py](../intentbond/review.py), [intentbond/boundaries.py](../intentbond/boundaries.py).

Existing assertions: [test_review_only_fixtures_trigger_bound_review_without_importing_examples](../tests/test_boundaries.py); [test_review_paths_use_existing_literal_path_validation](../tests/test_boundaries.py).

Evidence limit: The accepted scope selects examples/ for review only. This selection does not adopt the example applications as product requirements. Recovery rewrite restrictions are linked separately.

### Present draft status, coverage and review separately
`req~ib-draft-reporting~1`

Both single-item and compact explanations expose the native OFT item status, shallow/deep coverage and uncovered types separately, alongside trace and recorded review results. Retain a draft UNCOVERED label even when the uncovered-types list is empty and explain that draft status is not approval; do not convert that label into either a missing-link claim or acceptance.

Needs: impl, utest

Original documentation: [docs/contract.md](contract.md).

Implementation: [intentbond/explain.py](../intentbond/explain.py).

Existing assertions: [test_draft_status_and_native_coverage_are_distinct_in_both_views](../tests/test_explain.py); [test_native_oft_uncovered_status_is_preserved](../tests/test_explain.py).

Evidence limit: This presents native/report metadata. Requirement approval records the maintainer's review; the displayed metadata does not establish semantic correctness or independent review.


### Stdlib unittest execution evidence
`req~ib-unittest-evidence~1`

The optional unittest producer emits one JUnit result per collected test method
with explicitly configured named OFT identities, including skipped and unexecuted
methods. Subtest failures/errors/skips affect their parent result. Fixture errors,
expected failures, unexpected successes and interrupted executions cannot become
passing suite evidence. Zero discovery and invalid mappings fail. Existing
reports are never overwritten.

Needs: impl, utest

### Exclude fixture annotations without losing source or review
`req~ib-trace-exclusions~1`

Trusted scope may select literal paths or directory prefixes in `trace_exclude`
inside its inputs. These paths are excluded only from OFT import, including import
diagnostics and JSX aliases. Source capture, source identity, test access and
specification/test/review path selection retain them. Candidate policy cannot
suppress baseline obligations by adding an exclusion.

Needs: impl, utest

### Diagnose prose accidentally imported as a declaration
`req~ib-markdown-declarations~1`

When OFT imports a Markdown declaration whose leading backtick-delimited ID is
followed by prose on the same line, checking fails with its path, line and an
explicit authoring remedy. Native OFT parsing is unchanged. Historical recovery
inventory remains readable so accidental original declarations can be mapped or
removed with review.

Needs: impl, utest
