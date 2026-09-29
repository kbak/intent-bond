# Add traceability to an existing project

Use this workflow when a project already has code and tests but lacks usable
requirements and links between them. Read the existing sources, document the
promised behavior in OpenFastTrace (OFT) Markdown, and link it to the code and
assertions that support it. Flag inferred intent, contradictions, and missing tests
for review. Start with one feature or subsystem.

The commands call this *baseline recovery*: reconstructing requirements from
existing sources. A human or coding agent writes the proposed documentation.
The tool preserves the original source, checks citations and allowed edits, and
runs OFT and the existing tests. Once reviewed and committed, the documentation
becomes a baseline for checking future changes.

The [concepts and result meanings](../intentbond/skills/intentbond/references/semantics.md)
explain how source citations, approval, and test results differ.

## Start with your coding agent

Give the agent the [existing-project skill](../intentbond/skills/recover-baseline/SKILL.md)
and ask: **"Document the requirements for this feature and link them to the
existing code and tests. Flag inferred behavior and missing checks."**

The agent inspects the repository, recommends an initial scope and asks about
unresolved choices, such as which subsystem to start with or whether to include
local changes. It handles prerequisites, bundle preparation, drafting and checks.
You do not need to supply commands, output paths, or a scope.json yourself.
Existing caller decisions are reused. The commands below also support manual use.

For a large repository, start with the feature you will change next, its
dependencies, and boundary cases. For example: "Document session expiration and
logout; leave billing and notifications for later." Review that starting point
before changing behavior. Later work can extend the scope through normal review;
it need not repeat this process for requirements already reviewed.

The default is one focused session: document the main requirements, then check
relevant regression tests and entry points for omissions.
A small Markdown table lists the features documented, open questions, and work
left for later. Give the agent a time budget if useful; it should stop with a partial proposal when decisions,
new tests or lengthy setup prevent further progress.

The agent needs shell access to the project and network access for missing tools.
It reuses the supplied tool version or installs the version matching the skill
link in a separate environment. Setup instructions are included in the skill.

## What you receive

Preparation starts from a clean Git checkout. Proposed edits then appear as
uncommitted changes for review in your editor or normal PR workflow. The agent
summarizes the changes and unresolved questions. An immutable original snapshot is retained separately in
both in-place and isolated modes; temporary drafting and validation directories
remain available to the agent.

| Artifact | Proposed result |
| --- | --- |
| Requirements/design Markdown | Selected documents can gain IDs, be rewritten, reorganized, consolidated, moved or removed. Useful existing structure and surviving IDs are preserved by default. |
| Implementation files | Coverage comments are added or retargeted to requirements the existing code supports. Runtime logic is preserved. |
| Test files | Coverage comments identify which requirements existing assertions check. Assertions are preserved; missing tests are recorded as gaps. |
| Scope configuration | Paths, coverage expectations and the existing test command for normal validation. |
| Evidence and review materials | Original citations, documented/inferred classifications, explanations of document changes and original ID mappings, unresolved questions, OFT/test results, a patch, and generated recovery-review.md. |

The edits remain uncommitted and pending review. After acceptance, commit the
reviewed proposal as described below. Bug fixes and new tests are
separate development work; recovery may reveal that they are needed. Incomplete
recovery still reports its findings and gaps, but cannot establish a validated
baseline.

## Identify properties and missing tests

While documenting the project, identify existing properties: rules intended to
hold across a defined set of inputs or states. Record their requirement IDs,
assumptions, existing tests, and missing checks in the same feature table or
claim notes. Distinguish documented promises from inferred behavior and suggest
which missing tests would be most valuable.

Preserve existing tests during this step so they remain evidence of the original
behavior. After the requirements are reviewed, use the
[property-testing workflow](property-testing.md) to add selected checks through
the project's runner and normal `ib check`. Continue when that test work is
already authorized; a request limited to documenting the project ends with the
proposal and recommendations. Proposed tests are not evidence of past execution.

Subsequent development maintains affected properties with their requirements,
implementation and generators. Reuse surviving identities, record legitimate
changes of meaning, and retain useful counterexamples as regressions.

## Workflow and responsibilities

1. `ib recover` captures the original source snapshot, inventories selected files
   and creates reviewable provenance records. By default the current checkout is
   the workspace; `--isolated` prepares a separate draft and leaves the original
   checkout unchanged. No model or test command runs during preparation.
2. The author annotates or restructures selected specification documents, adds
   or retargets coverage comments, supplies an ordinary scope.json, and records
   original citations, changes and unresolved questions in claims.json. Original
   snapshots, implementation behavior and test assertions are preserved.
3. `ib recover-check` validates citations against the captured original, checks
   the editing boundary, and uses the existing OFT/test checker on the assembled
   baseline. It also imports original specification IDs through OFT and requires
   explicit mappings for changed or removed requirements. It retains a proposed
   patch, source identities, documentation review, claims, and evidence.
4. A maintainer reviews the proposed promises, links, scope, and open questions.
   Passing automated checks still leave the proposal awaiting review. The caller
   establishes a checked repository baseline with
   `ib check --base HEAD --candidate HEAD` after committing it.

Use the project's normal review process to choose the scope, resolve contradictions,
and accept requirements. The tool supplies the source records and automated checks;
a factory or separate approval service is not required.

Recovery follows the evidence order and contradiction handling in OFT's
[reverse-specification skill at 4.9.0](https://github.com/itsallcode/openfasttrace/blob/4.9.0/.agents/skills/openfasttrace-reverse-specs/SKILL.md):
user-facing documentation, existing specifications/design, tests, public code,
then internals/configuration. The bundled guidance adapts that procedure to a
bounded scope without imposing arc42 or generating redundant design layers.

## Prepare and check the documentation manually

Follow the [installation instructions](../README.md#install) for the package and
OFT. From a clean local clone:

```sh
ib recover
```

This records HEAD and the current branch and checks that the index and worktree
are clean, including untracked files. Existing files must match the captured
HEAD bytes; use isolated mode for worktrees with checkout filters that change
those bytes. The tool leaves the branch, index and HEAD unchanged.

The CLI prints the retained snapshot/instructions location and creates
`.intentbond/recovery/<id>/source.json` and `claims.json` in the checkout.
source.json identifies the captured original; preserve it during recovery. The author adds
source citations and unresolved questions to claims.json, adds requirements and
coverage annotations to project files, and proposes root scope.json. These are
ordinary working-tree changes. Newly created files appear in Git status/editor
source control and are not included in unstaged `git diff` until staged.

Always cite the original snapshot, even after the corresponding working file
changes. Temporary drafts are fine; put the proposed edits into the recorded
workspace before checking. Then run:

```sh
ib recover-check --preflight
ib recover-check
```

Preflight checks the proposal and trace graph without executing tests. Use it to
catch citation, annotation/import and editing mistakes before costly setup or
suites. Exit 5 means tests remain unrun, not passing evidence. The full check runs
the configured tests; rerun it only when relevant edits or resolved blockers
justify the cost.

Start with the generated `recovery-review.md`. It separates proposal checks
(source preservation, citations and original-ID accounting) from graph/test
results, and links the detailed artifacts. A structurally incomplete proposal can
still have valid citations and be useful for review. Accepting documentation does
not bypass the configured checks for later development. Record missing evidence
and resolve any changes to that policy through the project's review process.

The active recovery is discovered from Git metadata, including in linked Git
worktrees. Snapshots and raw logs are kept under the worktree's Git directory in
`intentbond/recovery/`; each check creates a fresh result. They do not
appear in Git status. Use --repo to select another checkout, or --recovery to
select a retained bundle explicitly. --input on preparation selects literal
repository-relative paths; omit it to inventory the whole snapshot.

The proposed scope selects the trace graph and test command. Inspect that command
before executing a draft from an untrusted source. --scope can supply an external
proposal when existing scope.json must remain unchanged. --out can select new
storage outside the checkout, or within its tool-managed Git recovery storage.
Check output must also remain outside the source bundle itself.
Both modes default to Git storage; isolated check output is retained beside its
bundle. Explicit paths under system temporary storage produce a retention warning.
Git metadata is local: preserve the full bundle and results in the caller's
artifact storage for another machine or a PR review.

Changes to the starting commit/branch, original snapshot, or durable source
record prevent a successful check. Concurrent candidate changes invalidate the
result. The tool preserves the files for inspection and never resets, stashes,
switches branches, commits, or automatically rolls back a rejected proposal.

| Exit | Meaning |
| --- | --- |
| 0 from recover | Preparation completed; no extraction or verification is claimed. |
| 4 from recover-check | OFT, tests, editing boundaries and source citations passed; baseline review remains required. |
| 5 from recover-check --preflight | Proposal/trace checks passed; tests were not run. This is incomplete validation. |
| 1, 2, 3 from recover-check | Rejected, errored or empty proposal. Read recovery-result.json and retained diagnostics. |

Review project changes together with the durable source/claims records. The
result directory also retains proposal.patch, claims.json, normalized
provenance.json, documentation-review.json, scope.json and check/evidence.json. Full original snapshots and
raw logs should be retained as needed for the project's evidence policy.
`.intentbond/recovery/` is reserved for evidence and excluded from OFT import,
including when inputs contains `.`. Quoted historical links cannot satisfy live
coverage. Those files remain included in source identities and test snapshots.
Open issues remain in provenance and their count is shown in the result. A green
trace does not resolve an open question. Invalid proposals can retain partial
artifacts; the current recovery-result.json status governs the whole invocation.

## Keep source citations when reorganizing documentation

Selected, inventoried Markdown specification documents may change in the proposal;
their originals stay in source/. Include both old and new locations in
specification_paths when moving a document. When a file is deleted, use a containing
input directory so normal OFT import does not require the deleted path to exist.
Documents outside those boundaries remain protected. Keep executable documentation
and test fixtures outside the editable specification scope.

For each substantive edit or deletion, claims.json's document_changes records the
original path, a summary, original source citations, and an author assessment of
meaning: preserved, changed or uncertain. Adding IDs/Needs/Status: draft metadata or editing
coverage comments alone does not require a document-change entry. New requirements
still need their ordinary claim citations. The
[record format reference](../intentbond/skills/recover-baseline/references/recovery.md)
contains the exact schema and examples; the recovery skill guides the agent through it.

OFT imports the original inventoried specification documents independently of
the proposed coverage types. Unchanged requirement identity/content is matched
automatically, including moves. Changed content or revisions, splits, merges and
removals require requirement_mappings with original ID, proposed target IDs, and a
reason. A removed obligation has an empty target list. The review report retains
the original/proposed OFT content and locations for every authored original ID in scope.
Unnamed coverage-comment IDs generated by OFT are excluded from requirement mappings;
their links still participate in graph validation. Moving those comments does not
require a requirement-migration explanation. Explicitly named coverage IDs remain
accounted for, including revision zero.
Malformed originals that OFT cannot import produce diagnostics, not a false claim
that no original requirements existed. Duplicate authored IDs in the original
specification also block recovery, even if the proposal resolves them: the current
mapping format identifies each original by ID and cannot distinguish duplicate occurrences.

Review mappings and explanations together with the diff. Neither a citation nor
a "preserved" assessment proves semantic fidelity. Preserve exceptions, thresholds,
negative requirements and must/should distinctions; flag contradictions and possible
meaning changes. Do not remove obligations or weaken tests just to make tracing
pass. Existing requirement IDs can be accounted for mechanically; completeness of
unstructured prose and non-OFT identifiers still needs an explicit human/agent
assessment. Scope exclusions must be reviewed too.

All changes remain proposals, including deliberate changes of meaning or removal.
New or substantively rewritten recovered items explicitly use `Status: draft`
after their OFT ID; omitted status imports as approved. Unchanged existing items
retain their status. Promote accepted items to `Status: approved` only through
the caller's review and adoption process, preserving their historical origin.
The checker never interprets OFT item status or author notes as baseline acceptance.

## Work in a separate draft

Use an isolated draft when the current checkout has unfinished work or a separate
workspace is preferred:

```sh
ib recover --isolated --repo /path/to/project --out /path/to/recovery
ib recover-check --recovery /path/to/recovery --out /path/to/recovery-result
```

The author works in recovery/draft/ and writes recovery/claims.json. HEAD is the
default source version; --candidate worktree includes existing local changes,
and a commit/ref can select another source version. Explicit storage must be
outside the original checkout. The result includes proposed/, a full copy of the
checked candidate, as well as proposal.patch. Original schema 1 bundles remain
checkable as isolated drafts.

When transferring an isolated proposal for review, check that the original
checkout still matches the recorded source, then apply only the intended patch:

```sh
git -C /path/to/project apply --check /path/to/recovery-result/proposal.patch
git -C /path/to/project apply /path/to/recovery-result/proposal.patch
```

Applying or copying draft changes into a working tree does not accept the
requirements. Patch applicability alone does not prove matching source; compare
the recorded commit and any captured local changes with the target. Preserve the
original snapshot and provenance when moving an isolated proposal.

## Review, commit, and continue development

In-place changes are already in the checkout; do not reapply proposal.patch.
Review and resolve relevant scope/intent questions using the project's usual
process. Commit the accepted requirements, coverage links, and scope. Recovery
records do not need to be committed or kept in the current tree for ordinary
`ib check` / `ib verify` use. Retain provenance and the review decision in one
of these ways:

- Commit the source/claims records with adoption, then remove them in a later
  cleanup change. Keep a commit-pinned reference to them in maintained documentation
  and retain that Git history.
- Archive the complete recovery bundle and result directory in the project's
  durable artifact storage, record their location with the adoption decision,
  and omit the checkout's source/claims files from the adoption commit.

Git can recover committed source bytes and records. It cannot recover uncommitted
claims, local-only snapshots, or test logs that were never stored there. Git
metadata is local and is not included in a clone or push. Keep unresolved questions
and actionable limitations in maintained documentation or the project's issue tracker.

Keep the active source/claims files available through recovery checks and review.
After acceptance and archival, they may be removed from the checkout. Do not
blanket-ignore `.intentbond/`: in-place preparation requires its review records
to appear in Git status. Cleanup changes source identity, so prior recovery
evidence does not verify the cleaned source. Validate the actual adopted commit:

```sh
ib check --repo /path/to/project --base HEAD --candidate HEAD
```

If the reviewed scope is stored separately, pass it with --scope. Recovery checks
use disposable validation commits; they cannot replace this check of the adopted
commit. Subsequent feature work uses the existing ib check / ib verify workflow.
Point the agent to the
[development skill](../intentbond/skills/intentbond/SKILL.md)
for those tasks. It handles standalone setup and the project's committed checking
policy; retain its reference in the project's agent instructions for later sessions.

## Limits

The workflow reads a local Git checkout, including a clone from GitHub.
GitHub PRs/issues, external documents, historical intent reconstruction, and
runtime production discovery are outside extraction scope. Git commit and file
digests identify the evidence; source identity has the same exclusions as the
[normal checker](contract.md#source-identity).

Tests execute with the caller's permissions in a captured source directory;
prepare dependencies and use an isolated workspace as appropriate. Recovery
does not repair bugs or generate new tests to
make an inferred requirement pass. Such work follows baseline review.

Outside editable `.md`/`.markdown` specification documents, existing inventoried
files permit only standalone OFT coverage-comment additions, removals and replacements,
including `//` comments in `.mjs` and `.cjs` modules. All non-annotation lines and
existing file modes must remain unchanged. New files are limited to Markdown within
specification_paths, root scope.json, and the recorded source/claims files created
by in-place preparation. Existing recovery records remain unchanged during recovery;
post-adoption cleanup uses ordinary development checks.

This is a textual editing check, not proof that comments are semantically inert
inside every language construct, that Markdown is never executable, or that metadata
attaches to the intended prose.
OFT validates the resulting graph. Review annotation placement, including code
fences and multiline strings. Unsupported annotation forms require a deliberate
extension. Semantic fidelity and assertion adequacy remain review responsibilities.

A citation proves that the quoted source exists at the recorded location. It
does not prove that the source supports the proposed statement. OFT links and
suite-level test results likewise do not prove individual requirement adequacy.
Reports are unsigned and depend on the caller's custody of the recovery bundle.

Repeated recovery starts a fresh bundle; in-place preparation again requires a
clean checkout. Prior recovery records still in that checkout are preserved during
recovery. Rechecking writes a fresh result
directory, leaving earlier proposals and outcomes intact. A source change after
capture does not update the proposal automatically; recover again or reconcile
the changes before adoption. Incomplete/failed recovery is still a useful report,
but is not an accepted baseline.
