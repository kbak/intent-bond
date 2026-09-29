---
name: intentbond
description: Draft requirements or implement and review a task with OpenFastTrace, using the supplied scope and baseline to follow linked documentation, code, tests, and evidence.
---

Maintain requirements, supporting documentation, code, tests, and their links
in each commit prepared for the task.
Compare changes with the agreed starting commit and retain check results for review.

Use the [concepts and result meanings](references/semantics.md) from the matching tool
package or the copy included in context. Apply its distinctions in the existing
task summary; no separate report is required. For design discussions or changes
to requirements, use [requirements guidance](references/requirements.md).
Discussion does not authorize implementation.

## Task context

Reuse supplied instructions, requirement context, and matching local/package/factory
tooling. Read missing context as needed; do not reread supplied text merely to
follow this workflow. Honor pinned revisions and preserve local changes.
If tooling is missing, follow the [standalone setup](references/setup.md).

Retain the target repository's absolute path. Use the supplied scope and baseline;
in standalone use, the CLI defaults to the repository's adopted scope.json and
merge base with the locally known default branch (HEAD on that branch or detached
HEAD). Use an explicit baseline for work based on another feature/release branch.
Resolve and retain the starting baseline before editing or committing. Reuse it
for checking the intended change and verifying its committed result; resolving
the default again after a commit on the default branch would select the new HEAD
and omit the change from the comparison.
Ask only about unresolved task or scope decisions. If the project lacks starting
requirements and links, use [the existing-project skill](../recover-baseline/SKILL.md)
to document them. Continue implementation when already authorized, retaining the
recovery evidence and reviewing the combined change through the existing workflow.
Ordinary development does not repeat that initial work. Candidate scope edits
cannot authorize their own policy.

Locate affected promises through existing headings, capability tables or targeted
searches; read their full text and follow links through design, code and assertions.
When saved evidence is available, assemble missing context for known IDs together:

```sh
ib explain 'req~first~1' 'req~second~1' --compact --evidence /path/to/check/evidence.json
```

This shares metadata and linked locations without rerunning tests. Use
`--format json` for structured IDs or `--snapshot base` for historical items. Saved evidence
does not establish current-source agreement or complete impact coverage. Follow
indirect links as needed; query only to resolve gaps, not as a required final step.
For a nondefault OFT installation, keep `INTENTBOND_OFT_JAR` set or pass `--oft-jar`
to `explain` as well as `check`; saved evidence does not configure the local JAR path.

## Implementation and review

Keep IDs beside the relevant behavior and assertions; follow the scope's coverage
and revision policy. Do not weaken promises or remove obligations to hide failures.
Keep prose and test edits visible. Authorized edits can proceed without another
confirmation; conflicts with approved requirements need a decision through the
caller's question or review process. Candidate approval files grant no authority.

Follow affected obligations to existing properties and maintain their assertions,
generators and assumptions with the change. For selected new checks or properties
identified while documenting the project, use the matching packaged
[property-testing skill](../property-testing/SKILL.md), or its supplied inline
copy. It strengthens selected obligations with ordinary executable tests and
uses the existing review/evidence flow; it does not require property tests for
every change. Load only the applicable framework guide.

Before each commit or final handoff, review the full intended Git diff, including
new files, and related unchanged promises, code and assertions. Keep the active
requirements and supporting reference documentation consistent with the change.
Unchanged promises do not need wording or ID edits just to accompany a code change.
Compare their meaning: does the implementation
satisfy the promise, and do tests check the affected behavior and boundary cases?
Code-only changes need this assessment too. Use focused source reads around the
links; avoid overlapping rereads or fixed small pages that fragment the review.
After a repair, inspect its delta and affected relationships; repeat a full
review if the repair changes the scope or invalidates earlier conclusions.

In the existing task summary, state what you checked, reuse or update the handoff's
requirement-change summary, and flag contradictions, gaps and uncertainty with
IDs and file references. This is best-effort review; structural checks do not
establish semantic agreement or assertion adequacy.

## Run checks and report the result

When the task asks to connect requirements, code, tests and their execution,
inspect the supplied scope's `tests.format` and `tests.execution_links` before
choosing a runner or reporting a tool gap. IntentBond already supports explicit
JUnit `oft_id` associations and required passing artifacts; see
[execution links](references/execution-links.md) for pytest and unittest producers.
Command success, suite accounting and individual execution associations establish
different evidence. Propose missing configuration/producer work separately from
unsupported capability; changing trusted policy still follows the caller's authority.

Run the configured check on the completed candidate and again after repairs:

```sh
ib check --repo /path/to/repo
```

Use explicit task inputs when supplied:

```sh
ib check --repo /path/to/repo --scope /path/to/trusted-scope.json \
  --base BASE_COMMIT --candidate worktree --out /path/to/new-evidence
```

`python -m intentbond` is equivalent. The runtime requires Git,
Java, OFT and the project's test dependencies. Each output directory must be new
and outside the repository. Retain the actual baseline commit, exit code and
complete bundle. Start with the printed status, counts, diagnostics and artifact
paths. Open detailed logs/reports for failures or unresolved questions; success
does not require dumping every retained artifact into context. The check already
runs the configured tests; repeat them separately only for a concrete need.

Inspect required changes in review.json. review.patch contains specification/test
changes, not the full candidate diff; it need not duplicate a review already
covering those edits. Exit 0 passes automation; exit 4 leaves specification/test
review pending. Other exits cannot establish completion. Repair in-scope failures;
report prerequisite or baseline defects without bypassing policy. Changed source
requires a fresh check; an earlier passing bundle cannot replace a failed run.

Suite success does not establish execution of each linked test. With the optional
[execution-link profile](references/execution-links.md), preserve missing, skipped
and ambiguous observations. A reported passing execution is not proof of requirement
satisfaction. An explain exit 0 means inspection succeeded, not validation passed.

Once the change is committed or exported to another checkout, verify that commit
with the original baseline:

```sh
ib verify --repo /path/to/repo --base BASE_COMMIT --candidate EXPORTED_COMMIT \
  --evidence /path/to/new-evidence/evidence.json
```

Add the same --scope if one was supplied. For exit-4 evidence, use
--allow-pending-review only when the caller enforces review before acceptance;
verification leaves it pending. Recheck changed contents. Follow the existing
Git/review process; this skill does not itself authorize publishing or acceptance.
Report the exact evidence path and a concise assessment. Completion requires
matching current source, successful checks and the caller's review gates.
