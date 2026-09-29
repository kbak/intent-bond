---
name: recover-baseline
description: Document an existing project's requirements, link them to code and tests with OpenFastTrace, and identify missing checks for review.
---

Document the promised behavior of an existing project using its documentation,
code, and tests. Propose requirements and links, preserve the original behavior,
and flag inferred intent and missing checks. The command and skill names call
this *baseline recovery*: reconstructing requirements from existing sources.

Use the shared [concepts and result meanings](../intentbond/references/semantics.md)
when interpreting recovered claims, identity mappings, and check results. Read
it from the matching tool checkout or package; recovery bundles and injected
agent contexts include the reference so no separate lookup is needed there.

Use this for an existing project, including one whose structured requirements
need reconciliation. A request such as "Document this feature's requirements and
link them to the existing code and tests" is enough to start, including when the
caller supplies only this skill's GitHub link.
Guide the caller through the process; do not require a prepared bundle, installed
tooling, CLI arguments, or knowledge of the artifact schema.

## Set up the tools

Identify and retain the target project's absolute path before acquiring tooling.
If starting from a GitHub skill URL and a matching tool checkout is unavailable,
clone that repository into a new agent-managed directory outside the target project.
Honor the branch, tag or commit in the supplied URL; resolve it to a commit and
read both this skill and references/recovery.md from that same checkout. For an
unqualified copy of this skill, the upstream is
`https://github.com/kbak/intentbond.git`, branch `main`. Keep the
resolved tooling commit for the handoff. Use HTTPS for a public checkout; do not
require the caller to clone the tool or configure GitHub SSH access.

For a supplied local checkout, packaged skill or preconfigured factory runtime,
reuse its matching code and included reference. Preserve the caller's chosen
version and local changes; do not replace them with upstream main. If code is
missing, fetch the supplied repository/ref into a separate checkout. When only
an unversioned skill copy is available, use upstream main and reread its complete
guidance. Resolve relative references against the tool checkout, not the target
project; an inline reference supplied by the adapter needs no separate download.

Read the [setup and record format](references/recovery.md), then install any
missing tooling in an isolated Python environment outside the target project.
Follow that contract for prerequisites, revision matching and commands. Keep
the target path explicit when running recovery after setup. This skill needs an
agent with repository, shell and (when downloading) network access; if a capability
is unavailable, explain the specific blocker and request only the missing access.

## Choose the scope and preserve the original

If no bundle was supplied, identify the repository from the workspace and inspect
its documentation, source layout, test setup, and Git status. Ask for the repository
only if it cannot be identified. Honor any scope already requested. Otherwise,
recommend a scope around the next intended change, including dependencies and
boundary cases; ask only about unresolved choices. A small project may fit one
pass; defer unrelated areas. A clean
checkout uses in-place recovery by default. If local work exists, offer isolated
recovery and ask whether that work should be included when the intent is unclear.
Combine unresolved choices into a short exchange and continue independent
inspection while waiting. Do not ask callers to choose flags or output paths.

Check prerequisites and run `ib recover`; it preserves the original snapshot
and chooses tool-managed storage. Use `--isolated` when a separate draft was
requested or existing work must be preserved. Do not stash or discard user work.
Resolve routine setup within the task's permissions. Read the returned
recovery.json for the mode, workspace and claims locations, then read its
inventory and original source. Reuse supplied scope/source decisions;
an automated caller that already provided them needs no intake conversation.
The caller decides which recovered promises to adopt. Recovery does not grant
approval or replace an established baseline.

Aim for a useful first review in one focused session, roughly 30–60 minutes when
setup and tests permit, unless the caller requests more depth. Recover the main
promises, then make one short omissions pass through relevant regression tests
and public entry points. Honor a supplied time limit. Stop with a cited partial
proposal when further progress needs product decisions, new tests, lengthy setup
or broader investigation. Do not expand scope or keep iterating toward perfect
coverage. Rerun costly checks only after a relevant change or resolved blocker.
If setup or tests would overrun the session, retain the draft and mark those
checks unrun with a concrete resumption step instead of repeatedly repairing the
environment. The caller can request a deeper pass later.

The original snapshot is required in both modes. Preserve it throughout recovery,
including when using temporary files for drafting. In-place mode writes proposed
changes to the recorded checkout for normal Git review; isolated mode writes to
the bundle's draft repository. Leave the current branch and HEAD unchanged and
leave edits uncommitted. A working-tree diff is still a proposal, not acceptance.

## Write requirements and identify missing checks

Follow OFT's reverse-specification evidence order: user-facing documentation,
existing specifications/design, tests, public entry points, then internal code
and configuration. Extract meaningful observable behavior and constraints.
Add design items when they explain decisions; use existing OFT conventions and
avoid redundant layers. Reuse existing IDs for surviving obligations; start new
ones at revision 1. Preserve useful existing structure. Restructure where it
clarifies scattered evidence, not merely to shorten already clear requirements.

Give newly recovered or substantively rewritten specification items explicit
`Status: draft` immediately after the OFT ID, before the description. OFT otherwise
imports omitted status as approved. This applies to documented and inferred claims;
keep origin and disputes in their existing provenance records. Preserve the status
of unchanged existing items. Passing checks never promote draft items, and status
must not be changed just to remove trace defects.

Keep a small feature table in the proposed Markdown: documented (IDs), deferred
(reason/next step), or outside scope. Group by meaningful behavior, not every file
or function; no new schema or exhaustive catalog is needed. In the omissions pass,
look especially for boundary/negative cases, retry and lifecycle behavior, and
contradictions with the first pass. Relevant regression assertions can reveal
promises missing from the docs. Record remaining uncertainty instead of estimating
a percentage recovered.

In that same pass, inspect existing invariants and executable properties for the
selected capabilities. Reuse their identities, assertions and generators; record
what they actually check and their domain/assumptions. Identify a few useful
missing properties from the requirements, prioritizing critical logic and known
gaps. Keep these in the existing feature table or claim notes, with linked
requirement IDs, documented/inferred origin, available checks, and the next action.
Uncertain intent belongs in open_issues. A candidate property is a proposal;
current code or a passing test cannot establish that it is an accepted promise.

Use the [property-testing workflow](../property-testing/SKILL.md), or its inline
copy, for this discovery and handoff. During recovery, preserve executable tests,
generators, dependencies and runner configuration. Do not install a new testing
library or generate tests as part of the recovery proposal. The shared workflow's
authoring steps apply after adoption, when adding tests as described below.

Within that same short pass, try to disprove a few broad or uncertain requirements:
what option, input, platform or interaction could make the sentence false? Use
existing evidence first; a small temporary probe may resolve uncertainty without
adding project tests or extending the session. For example, "dotenv values round-trip
unchanged" may overstate evidence that escaping preserves text: subsequent
interpolation can change the loaded value. If the original docs promise the broader
behavior, cite the contradiction in open_issues rather than silently narrowing it.
For an inferred claim, state only the supported conditions and retain uncertainty.

Split clauses when their origin, implementation or verification differs materially.
A linked happy-path test must not hide an untested limit or another channel's
behavior. Keep partial evidence in claim notes and unresolved obligations in
open_issues. Choose verification types appropriate to the promise: provider
operations and device setup may need manual evidence rather than unit tests.
Never invent a manual-verification marker without the corresponding artifact.

## Record citations and requirement changes

Read the bundle's original `source/` files for citations. Within selected Markdown
specification paths, add native OFT IDs and `Needs:` metadata, reorganize or rewrite
documents, and move or consolidate content when useful. Keep original paths in
specification_paths when moving/deleting documents so their IDs remain accounted
for; select a containing input directory if an old file disappears.
Record substantive edits in claims.json's document_changes with original citations,
a summary, and whether meaning is preserved, changed or uncertain. Preserve
exceptions, thresholds, negative requirements and must/should distinctions.
Do not resolve ambiguity by inventing intent or silently dropping an obligation.

Account for each original OFT ID. The checker matches unchanged identity/content
automatically, including moves. For rewrites, revisions, splits, merges or removals,
provide requirement_mappings with target IDs and reasons. A proposed removal uses
an empty target list. These explanations are pending review, not authorization to
weaken a promise. Record contradictions and possible meaning changes visibly;
never label a recovered or inferred requirement as newly approved.

Add or retarget standalone coverage comments beside the code and test assertions
that support them. Preserve all non-annotation source/test lines and existing file
modes. Capture unimplemented promises, undocumented behavior and disagreements in
claims.json. Documentation that is itself executable or used as a test fixture
must retain that behavior; keep it outside the editable specification scope.
Test names and copied documentation alone do not establish behavioral coverage.

For each selected OFT requirement/design item, record whether intent was
documented or inferred, exact original source citations, and relevant uncertainty.
Never label inferred current behavior as historically approved intent. Agreement
between generated docs, code and tests may reflect one shared mistaken assumption.
Avoid numerical confidence claims without a calibrated basis.

Prepare the proposed scope.json using the existing IntentBond
scope format, including the project's real test command. The evidence inventory
is broader context; the scope selects the actual bounded trace and test policy.
Before finalizing it, identify which source documents remain maintained descriptions
of recovered behavior. Include those living documents (for example, the README)
in specification_paths and inputs even without OFT IDs, so later edits receive
specification review. Historical evidence such as old changelog entries can remain
citations without becoming maintained specifications. Keep executable docs under
the behavioral protections above.
Follow relevant implementation dependencies far enough to include the mechanisms
behind recovered promises, or record the boundary; avoid selecting only files
already annotated. Include the runners needed for linked tests across stacks.
Use existing aggregate commands or tests.reports for multiple JUnit outputs;
record suites left unexecuted. Recovery does not add new test runners or tests.
When execution traceability is requested, read the matching package's
[execution-link reference](../intentbond/references/execution-links.md) before
reporting a gap. `tests.execution_links` already joins explicit JUnit `oft_id`
metadata and can require named artifacts to pass. Inspect existing producers and
configuration; distinguish an unconfigured integration from an absent tool feature.
If a producer or test edit is needed, record it as follow-up development rather
than altering historical test evidence during recovery.
For missing behavior/tests, preserve the gap and report it. Bug repairs and new
characterization tests are separate tasks, not recovery shortcuts.

## Check and review the proposal

Use `ib recover-check --preflight` after drafting to check edits, citations and
OFT import/links before expensive tests. Exit 5 means preflight was otherwise clean
but tests were not run; it is not passing validation. Fix inexpensive authoring
mistakes; retain genuine evidence gaps. Prefer the default durable storage; use
temporary locations for tooling/drafting, not the sole retained snapshot/results.

Run `ib recover-check` in an active in-place workspace, or supply `--recovery`
with the bundle path. The tool chooses a fresh result directory each time.
Inspect the current invocation's result, OFT/test logs and proposal.patch. Exit 4
means automation passed but the entire proposal still needs review, including
open issues and citation meaning. Other nonzero exits cannot establish a valid
baseline. Repair draft mistakes within scope; report missing prerequisites and
unresolved contradictions without removing obligations just to obtain a pass.

In the final diff review, check each added or retargeted marker against its nearby
function, branch or assertion. For example, a link for "empty values are accepted"
beside the double-quoted-value branch does not establish empty-value handling;
place it beside the actual empty-value path or assertion, or record missing support.
Review the inserted comments, not the whole repository again; keep this within the
same omissions/review pass and session budget.

Present the result in plain language: the features documented and the scope,
documents added, rewritten, moved or removed, implementation/test files receiving coverage
comments, and checks that passed or failed. Explain that behavior and test
assertions are preserved; missing tests and bug fixes are follow-up work.
Highlight inferred or disputed intent, changes in meaning, removed/split/merged
obligations and unresolved gaps that need decisions. Walk through
documentation-review.json alongside the diff. Accounting for existing IDs does
not prove that every obligation in unstructured prose was recovered; state the
remaining completeness uncertainty instead of claiming exhaustive extraction.
Point to working-tree changes in in-place mode and the proposed patch in isolated
mode. Start with the generated recovery-review.md, then link the feature table,
requirements, provenance and validation results so the
caller can inspect them without navigating JSON unaided. A partial recovery
should still explain what was found and what prevents a validated baseline.
The report distinguishes proposal checks from tracing/tests. A useful partial
proposal can finish this recovery task while still failing the development gate;
review acceptance does not waive missing evidence. Retain the complete bundle
and result directories with the review handoff; Git metadata is local, not pushed.

## Commit reviewed requirements and add tests

Leave adoption to the caller's existing review workflow. In-place edits already
exist in the checkout; do not apply proposal.patch over them. For an isolated
draft, transfer only the reviewed changes to the matching original source.
Retain provenance and the review decision in Git history or durable artifact
storage, and record where they can be retrieved. The checkout's source/claims
files are needed through recovery checks and review, but need not be committed
or remain in the current tree after acceptance and archival. Follow the
[retention procedure](references/recovery.md#bundle-and-proposed-edits); keep
unresolved questions in maintained documentation or the issue tracker. Validate
the actual committed baseline after any cleanup before normal development begins.
Committing a draft alone does not
establish acceptance or activate a development policy.
As part of authorized adoption, explicitly set `Status: approved` only for the
items accepted through that review. Preserve their documented/inferred origin.

Hand off the prioritized properties, linked IDs and revisions, domains and
assumptions, existing test locations, missing checks, and unresolved intent in the
same maintained Markdown. After the caller adopts the baseline, use the
property-testing workflow to add the authorized tests: reuse the project's
library, add the selected checks, retain counterexamples, and run ordinary
`ib check` against that adopted baseline. Honor an existing authorization to
continue; ask only about unresolved intent or scope. A task limited to documenting the project ends
with these findings and recommendations. Do not mix new test evidence into the historical
recovery evidence or treat exit 4 as adoption.

This workflow is informed by OpenFastTrace's reverse-specification procedure at
4.9.0; the source and intentional differences are documented in the reference.
