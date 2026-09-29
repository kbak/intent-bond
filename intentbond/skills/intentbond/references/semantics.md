# Traceability concepts and result meanings

Use these definitions when writing requirements, following their links, or
interpreting IntentBond check results. The same meanings apply to human and agent
workflows.

## The checking workflow

| Term | Meaning |
| --- | --- |
| Intent | The desired outcome and rationale behind the work, recorded in existing source documents or decisions. An inferred interpretation remains distinct from an accepted promise. |
| Requirement | A statement of expected behavior or a constraint the software must satisfy. |
| Specification / design | A description of required behavior, interfaces, or structure. It can contain requirements or refine them through linked items; a separate layer is optional. |
| Traceability link | An explicit reference connecting a requirement to related requirements, design, code, or tests. |
| Baseline | The Git commit used as the starting point for comparison. A reviewed baseline contains requirements and checking rules accepted through the project's review process. |
| Candidate | The source version being checked: a commit or the current worktree. |
| Scope | The configuration selecting trace inputs, coverage rules, and the test command. |
| Evidence | Saved check results, logs, and source identities. Interpret them with the recorded scope and method. |
| Baseline recovery | The initial process of documenting requirements and links from an existing project's sources. The commands are `ib recover` and `ib recover-check`. |
| Property | A rule intended to hold across a stated domain of inputs or states. Property tests search for counterexamples using generated inputs. |
| Logical statement | An optional precise expression of a property beside its prose and ID, with a defined domain and assumptions. It becomes machine-checkable only when interpreted by a tool with defined semantics. |

Use the project's existing documents and artifact types. Separate design layers
and formal models are optional; review assesses whether their links are meaningful.

`ib check` validates links in both baseline and candidate and runs the candidate's
tests. It records specification and test changes for review. `ib verify` matches
saved evidence to source contents without rerunning tests. Neither command grants
approval or proves that all intended behavior is correct.

## Artifacts and coverage

OFT supplies the artifact syntax and tracing rules. Its
[concepts and terms](https://github.com/itsallcode/openfasttrace/blob/4.9.0/doc/user_guide.md#concepts-and-terms)
define specification items, IDs, artifact types, revisions, and coverage.
Use the project's existing types and chains; `req`, `dsn`, `impl`, and `utest`
are useful conventions, not a mandatory universal hierarchy.

| Term | Meaning in this workflow |
| --- | --- |
| Artifact / specification item | A named specification item or an OFT coverage marker. Its type identifies its role in the project's trace chain. |
| `Needs: impl, utest` | An obligation to have covering items of each listed type. It names types, not particular implementations or tests. |
| `Covers` / coverage annotation | A declaration that the current item covers the referenced item at its stated revision. For example, `[impl->req~session-expiration~1]` points from an implementation marker to that requirement. |
| Trace coverage | The declared links meet OFT's tracing rules and the trusted scope's minimum coverage obligations. This is a structural result. |
| Requirement satisfaction | The implemented behavior fulfills the promise. Assess this using the requirement's meaning, implementation, assertions, and applicable evidence. A coverage link alone does not establish it. |

Follow links in either direction to find related work. Reverse navigation does
not reverse their meaning: a requirement does not implement its implementation.
A complete requirement/design/code/test chain supports impact analysis; it does
not make behavioral correctness follow transitively from its links.

Coverage is bounded by the selected inputs and policy. An unlinked behavior or
missing requirement may never enter the graph. A passing check therefore does
not establish that all product promises were captured.

## Identity and exact versions

Keep these identities distinct:

| Identity | Example and use |
| --- | --- |
| Continuing named artifact | `req~session-expiration` identifies the promise across revisions within a project. Reuse it when revising that promise. |
| OFT item ID | `req~session-expiration~1` includes the declared revision that coverage links must reference. |
| Checked source | The source manifest digest identifies the captured paths, modes, and file contents. Use it to bind artifacts and results to exact source. |
| Checking policy | The scope digest identifies the rules and test configuration used for the check. Interpret results with that scope. |

Keep repository context with IDs when combining projects; OFT names are not a
global registry. Paths and line numbers locate items in a particular snapshot.
Moving a named requirement does not by itself change its identity. Do not assume
that an automatically generated coverage-marker ID has the same continuity as
an explicitly named specification item.

An OFT revision is author-declared. With `require_revision_increase: false`,
the same item ID can occur with changed content in different snapshots. Even
with revision enforcement, an item revision does not identify the whole program
or checking policy. Retain source and scope identity when comparing evidence.
`ib verify` matches saved evidence to contents; it does not rerun tests.

Recovery's original-to-proposed requirement mappings record lineage and a
reason for revisions, splits, merges, or removals. A mapping does not establish
semantic equivalence or authorize the proposed change.

## Origin, authorization, and verification

These are independent questions, not stages in a single confidence scale:

| Question | Existing records and their limits |
| --- | --- |
| Where did the claim come from? | Recovery records `origin: documented` or `inferred`, with source citations whose roles are `intent`, `implementation`, `test`, or `context`. `documented` requires an intent citation. The checker verifies source membership and exact quotations; the author/reviewer assesses whether those quotations support the claim and role. |
| Who accepted the promise or change? | The caller's task and review process establish authorization. Neither `origin: documented`, OFT's `Status: approved`, nor a passing check grants it. Preserve the applicable decision through that process. |
| What was checked? | Check evidence records trace, policy, test, source-stability, and review results for the selected versions. Report each at its recorded scope. |

An inferred claim may later be accepted without changing its historical origin.
A documented claim may be disputed, unimplemented, or untested. Keep uncertainty
and contradictions visible instead of changing origin labels or weakening a
promise to produce agreement. Recovery provenance describes recovered claims;
it is not a record of every subsequent link author or approval.

## Execution evidence and permissible conclusions

| Observation | Supported conclusion | Still requires separate evidence or judgment |
| --- | --- | --- |
| OFT tracing and coverage policy pass | Declared links and obligations pass for the selected artifacts. | Whether the links are relevant and assertions adequately check the promises. |
| Tests pass at `level: command` | The configured command returned success. | Which tests or assertions ran, unless established from additional execution evidence. |
| Tests pass at `level: suite` | The fresh JUnit report and command satisfy the configured completion policy. | Whether each OFT-linked test ran and which requirement each executed case checks. |
| Optional execution links report a case outcome | A JUnit case explicitly identifies an OFT test artifact in the checked snapshot. | Whether the association and assertions are adequate, every required scenario ran, or the requirement is satisfied. |
| `tests.source_status: matched` | The recorded source-stability checks matched around execution. | Reproduction of external dependencies, environment, or network state; detecting a source change restored before the final check. |
| Check status `passed` / exit 0 | Automated checks passed without changes in specification_paths, test_paths or optional review_paths triggering this review gate. | Caller-required review, approval, and overall requirement satisfaction. |
| Check status `review_required` / exit 4 | Automated checks passed with review pending. In recovery, the entire proposal remains pending. | Acceptance of the changed or recovered promises. |
| Recovery preflight status `incomplete` / exit 5 | Proposal and trace checks completed without running tests. | Passing validation, test execution or baseline acceptance. |

The checker retains JUnit reports. The optional `tests.execution_links` profile
associates reported cases with exact
OFT test-artifact IDs; without it, individual execution remains unestablished.
The default policy also permits skipped tests. Do not turn suite success or a
linked passing case into an individual requirement's "verified" status without
assessing the assertions and required scenarios. Command-only results contain
no report-based test counts.

Evidence statements are unsigned. Digests bind recorded contents but do not
establish producer identity; attribution depends on the caller's trusted
execution and audit records. Results with changed or unchecked source remain
diagnostic and cannot support a test attestation or successful evidence
verification.

## Example: explain a requirement

Suppose `req~session-expiration~1` promises expiration at 30 minutes, has
implementation and unit-test coverage markers, and OFT passes. The suite passes,
but its report marks the boundary test skipped while another test passes. This
can satisfy the default completion policy.

A useful explanation is:

> The requirement has declared implementation and unit-test coverage in the
> checked snapshot. The suite passed under a policy allowing skips, but the
> boundary test was reported skipped. This run does not establish execution of
> the expiration boundary assertions. The requirement's stated promise remains unchanged.

For a real handoff or query, cite the requirement and relevant source locations,
the evidence bundle and checked source/scope, and any applicable review decision.
Explain the supported result and remaining uncertainty in the caller's existing
summary. An absent connection means "not established by this evidence"; it does
not by itself mean that the behavior is incorrect. No separate report format is
required.
