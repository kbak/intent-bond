# Command and evidence reference

IntentBond uses the `ib` command from the `intentbond` package.

Scope schema 1 and evidence schema 2 are provisional and may change.

See [result meanings](../intentbond/skills/intentbond/references/semantics.md)
for how to interpret evidence.

## Commands

| Command | Required arguments | Result |
| --- | --- | --- |
| `ib install-oft` | None; optional `--destination DIRECTORY` | Downloads and checksum-verifies the configured OFT release. |
| `ib check` | None | Traces both versions, runs candidate tests, and writes evidence. |
| `ib verify` | `--evidence` | Matches saved evidence to the selected scope, base, and candidate. |
| `ib explain` | Complete OFT item IDs and `--evidence` | Explains selected items from the retained OFT graph and check evidence. |
| `ib impact` | `--evidence` | Compares retained declarations, links, and source-change categories; see [requirement evolution](requirement-granularity.md). |
| `ib recover` | None; defaults to current clean repository at HEAD | Saves original source and prepares records for documenting existing requirements. `--isolated` creates a separate draft. No agent or tests run. |
| `ib recover-check` | None for an active in-place recovery; `--recovery` for an isolated bundle | Checks proposed documentation, citations, links, and existing tests; review is still required. |

`recover-check --preflight` validates edits, provenance and the OFT graph without
running tests. An otherwise clean result is `incomplete` (exit 5), and `verify`
rejects it even with `--allow-pending-review`.

The command name `recover` refers to reconstructing requirements from existing
sources. See [add traceability to an existing project](recovery.md) for that
workflow and its record format.

### Optional formal commands

| Command | Required arguments | Result |
| --- | --- | --- |
| `ib install-alloy` | None; optional `--destination DIRECTORY` | Downloads and checksum-verifies the configured Alloy release. |
| `ib alloy-check` | `--manifest`, `--out` | Checks Alloy assertions and witnesses; retains native results, bounds, and JUnit. |
| `ib smt-check` | `--manifest`, `--out` | Checks Z3 obligations under explicit assumptions; retains native queries, results, and JUnit. |
| `ib chc-check` | `--manifest`, `--out` | Checks modeled reachability with Z3 Spacer; validates invariants or concrete traces and retains results. |

See [model checking and formal verification](model-checking.md) for authoring,
backend contracts, result meanings, and integration with the core. `ib verify`
matches retained evidence to source; it does not invoke a formal verifier.

### Explain saved evidence

```sh
ib explain 'req~session-expiration~1' --evidence /path/to/check/evidence.json
ib explain 'req~session-expiration~1' --evidence /path/to/check/evidence.json \
  --snapshot base --format json
```

`--snapshot` selects `candidate` (default) or `base`; `--format` selects `text`
(default) or `json`. `--oft-jar` and `--java` work as for `check`. No Git checkout
is required. The command verifies retained artifact hashes and source/scope
bindings, then runs the pinned OFT `trace -o aspec` reporter on the saved item
export. OFT computes coverage and links; ib adds the recorded execution and
review context. It does not run the project's test command or write to the bundle.

The provisional JSON schema 1 exposes `artifact` (description, location, Needs,
OFT shallow/deep coverage, `covers`, `covered_by`), immediate `related` locations,
`source`, `scope`, `recorded_check_status`, `tests`, `review`, and `limitations`.
Follow a related ID with another invocation to traverse a design chain. Coverage
refers to the native OFT graph; the recorded diagnostics also show policy failures.

Both text views show the OFT item status, native shallow/deep coverage and
uncovered types separately. OFT 4.9.0 can label a draft `UNCOVERED` even when
its uncovered-types list is empty. That label is retained as reported; inspect
the trace result and diagnostics for structural defects. Draft status, link
coverage, test outcomes and the external review gate do not imply one another.

Several positional IDs select compact output automatically; `--compact` selects
it for one ID. The command validates the retained bundle and loads OFT's graph
once, then returns each distinct requested ID in first-occurrence order. Any
unknown ID or revision fails the whole request without partial output.

Compact text retains full descriptions, per-item coverage and execution outcomes,
with immediate edges referring to a shared table of distinct path/line locations.
Table labels such as `L1` are local display references, not persistent artifact
IDs. Evidence status, diagnostics and limitations appear once. The compact JSON
shape retains schema version 1 and uses `artifacts`, a list of objects containing
`artifact`, `linked_test_execution`, `linked_tests` and
`execution_link_diagnostics`. Other metadata is shared at the top level;
`related` deduplicates by artifact ID and preserves complete IDs and locations.
Without `--compact`, a single ID retains its existing JSON shape.

Context assembly requires no AI inference, relevance ranking or source checkout.
It describes exactly the selected artifacts and their immediate links; it does
not establish that the selection is complete, traverse all indirect dependencies,
or determine whether a requested behavior change is authorized.

`linked_test_execution` remains `not_established` without the optional
[execution-link profile](../intentbond/skills/intentbond/references/execution-links.md).
With that profile, `linked_tests` retains per-artifact and per-case observations,
and `execution_link_diagnostics` explains invalid or unavailable evidence.
Baseline explanations report
`not_recorded_for_baseline` for tests, because this bundle's test run targets the
candidate. `review` is the check's recorded gate, not a later approval. Recovery
origin and caller approval decisions are outside ordinary check bundles.

Exit 0 means successful inspection, including inspection of rejected checks.
Missing IDs/revisions, incomplete exports, changed artifacts, or tool errors
return exit 2. An explanation describes saved evidence; it does not match the
current working tree, authenticate the unsigned producer, or establish program
correctness. Use `ib verify` to match current source.

### Check and verify inputs

For both `check` and `verify`:

- `--repo` defaults to the repository containing the current directory, including
  when invoked from a subdirectory. An explicit path must name the repository
  root. The repository must have a HEAD commit.
- `--base` defaults to the merge base of HEAD and the default branch. The CLI
  identifies that branch through `origin/HEAD`, preferring its local branch when
  present. Without `origin/HEAD`, it looks for local `main`, then `master`.
  It uses existing refs without fetching. On the default branch itself, or with
  detached HEAD, the baseline is HEAD. If no default branch or unique merge base
  can be found, supply `--base COMMIT` explicitly. For changes based on another
  feature or release branch, also supply the intended starting commit.
- `--candidate` defaults to `worktree`; it also accepts a commit or ref.
- `--scope` defaults to the root `scope.json` read from the resolved baseline
  commit. An explicit path is read as-is, relative to the current directory.

`check` creates a fresh `ib-evidence-*/check` directory in system temporary
storage and prints the evidence path. To retain evidence elsewhere, supply
`--out`: it must be a new directory outside the repository. Keep the full output
bundle when moving or retaining evidence. If the system temporary directory is
inside the repository, an explicit output path is required.

The check's text summary retains the `STATUS: /path/to/evidence.json` first line
and prints baseline/source identity, test counts and source stability, review
status, and available review/trace/test artifact paths. It shows up to five
diagnostics (600 characters each) and three reported failing cases (650 detail
characters each). When no failing case is available, it shows a bounded test-log
tail. Excerpts and omitted diagnostics/cases are labeled. Full evidence, reports,
exit codes and validation policy are unchanged; consumers needing structured
results should read evidence.json. `review.patch` covers changes selected for semantic review,
so the caller still reviews the full candidate Git diff, including new files.

For `verify`, use the same baseline and scope as the original check. If the
default baseline has moved, pass its original commit with `--base`.

Checks use the JAR selected by `--oft-jar` or `INTENTBOND_OFT_JAR`, falling back to the
user cache. `--java` selects the Java executable. Provision these tools before
running a check.

## Scope

```json
{
  "schema_version": 1,
  "name": "session",
  "inputs": ["requirements.md", "session.py", "tests", "run_tests.py"],
  "specification_paths": ["requirements.md"],
  "test_paths": ["tests", "run_tests.py"],
  "required_coverage": {"req": ["impl", "utest"]},
  "policy": {
    "require_revision_increase": false,
    "allow_skipped_tests": true
  },
  "tests": {
    "format": "junit",
    "command": ["python3", "run_tests.py"],
    "report": "test-results.xml",
    "timeout_seconds": 30
  }
}
```

`inputs` selects files for OFT. Each root must contain files at both versions.
Paths are literal, repository-relative POSIX paths; `.` selects the whole
snapshot. Path escapes and `.git` paths are rejected. Overlapping input roots
are imported once.

JSX/TSX files use OFT 4.9.0's existing JS/TS tag importer through temporary,
byte-identical aliases; retained exports restore original paths and line numbers.
Python files use Python's tokenizer to select actual comment tokens before OFT
import. Strings, docstrings and embedded fixture examples contribute no tags.
The temporary import view preserves original relative paths and physical line
numbers; snapshots and executed source remain unchanged. Tokenization errors
stop the import with a file-specific diagnostic. The interpreter running ib
must understand the selected Python source's lexical syntax.
Graph validation consumes the exported OFT graph. Standalone short coverage
comments that were not imported produce a location-specific error before tests,
including on unsupported file extensions. This is an import diagnostic, not a
check of executable behavior or assertion adequacy. Other languages retain
OFT's native annotation recognition.

The `.intentbond/recovery/` namespace is reserved for recovery records and
excluded from OFT import, even under `inputs: ["."]`. Source citations can
quote historical annotations; these must not count as current trace links.
Records present in the checkout still participate in source identities and test
snapshots. Ordinary checks do not require them after adoption; see
[retaining recovery provenance](recovery.md#review-commit-and-continue-development).

`specification_paths` and `test_paths` must lie within inputs and must not
overlap each other. Include test helpers, fixtures, and runner configuration in
test paths to expose their changes for review.

Optional `review_paths` is a nonempty, unique list of literal relative paths
using the same path rules. It selects additional files for semantic review
without adding OFT inputs. For example, `"review_paths": ["examples", "fixtures"]`
can expose edits to illustrative requirements without importing them into the
project's graph. Select narrower `inputs` to exclude those examples: review
selection never subtracts a file already included in `inputs`. This field is
bound to the trusted scope and evidence digest. It does not grant specification
rewrite permission during recovery, create requirements, or satisfy test links.

`required_coverage` selects artifact types and their minimum `Needs`. Selected
artifacts must originate within specification paths. An empty needs list is
valid. To use a design chain, for example, select `{"req": ["dsn"], "dsn":
["impl", "utest"]}`. OFT validates the relationships and revisions throughout
the chain.

The scope can be maintained in the project repository or in separate
configuration. The same approved scope applies to base and candidate.

By default, it comes from the baseline commit; changes to the candidate's copy
do not change the checking rules. A missing or invalid baseline scope fails
without falling back to the working copy. An explicit `--scope` reads the file
as-is, even when it is inside the repository: `--scope scope.json` does not read
the baseline version. Keep that approved copy outside candidate control for
checking and verification. Trust depends on the selected version and who can
change it, not its directory. Changes to the approved scope require authorization
and a fresh check. OFT's `Status: approved` and files written by the candidate
do not grant that authorization.

Unknown fields, duplicate JSON keys, invalid types, and unsupported schema
versions are errors. Both versions must pass tracing and configured coverage
checks. Validate a baseline's tests with base equal to candidate; subsequent
change checks trace the base and run only the candidate's tests.

An empty candidate normally fails. `allow_empty: true` permits status `empty`
(exit 3) when no other check fails. Removed artifacts remain in the review
record; empty scope does not count as successful coverage or test execution.

## Review and revision policy

Specification and test changes are compared against the baseline. The comparison
includes OFT artifact content, revisions, relationships, obligations, and file
content/modes. It covers intermediate design artifacts and prose outside
artifact blocks. `review.json` records the changes and their source/scope
digests; `review.patch` displays the text diff.

`summary.md` labels added, removed and modified items and shows before/after
description excerpts for up to 20 items. Each side includes up to 240 description
characters, with ellipses for omitted text. Excerpts normalize whitespace and
start near the first description difference when possible; they can omit later
differences and metadata changes. Full records remain in review.json/review.patch.
Rendering uses already-collected evidence and does not infer rationale or approval.

When automated checks pass, any specification or test change produces
`review_required`. The caller's review process decides whether the change is
adequate and authorized. Ordinary edits covered by the task proceed to that
review. Conflicts with approved requirements need a decision through the
caller's existing question or review process.

`policy.require_revision_increase` defaults to false. When true, imported
content changes require a higher revision, and revisions may not decrease. When
false, revision changes are left to review. OFT always checks reference
revisions.

Review must assess the meaning of changed requirements and the adequacy of
assertions. Structural references alone cannot establish that a requirement is
satisfied or that its particular test ran.

## Test execution

`tests.command` is an argument array. Shell syntax requires explicitly selecting
a shell, for example `["bash", "-c", "make test"]`. Commands run in the captured
candidate with the invoking account's permissions and inherited environment.
`PROJECT_DIR` points to that snapshot, and Python bytecode writes are disabled.
Set `TMPDIR` to place snapshots on a volume accessible to containerized tests.

`tests.timeout_seconds` must be an integer from 1 to 86400. The runner stops
remaining processes in the command's process group after completion or timeout.
It retains command arguments and output; it does not record environment values.
Use an isolated worker when commands need restricted access to the host.

| Format | Configuration | Passing result |
| --- | --- | --- |
| `junit` (default) | Set `tests.report`, or `tests.reports` for multiple relative file paths. | Exit 0, fresh complete reports, at least one passing case, and no failures or errors. |
| `command` | Omit `tests.report` and `tests.reports`. | Exit 0 from the configured command. No case counts or skip results are recorded. |

For a project with several runners, use one existing aggregate command or an
explicit shell command that invokes them and propagates failures. For example:

```json
{
  "format": "junit",
  "command": ["bash", "-c", "python -m pytest --junitxml=backend-results.xml && npm --prefix frontend test -- --run --reporter=junit --outputFile=results.xml"],
  "reports": ["backend-results.xml", "frontend/results.xml"],
  "timeout_seconds": 900
}
```

Adapt runner flags to the project. All listed reports must be fresh, regular files
in the captured candidate; duplicates, missing reports and stale reports fail.
Originals are retained as `tests-1.xml`, `tests-2.xml`, etc., and merged into
`tests.xml`. Report paths provide enclosing suite names to distinguish identical
case names across runners. Existing testcase properties, including optional OFT
execution links, are retained. This adds no task runner dependency. A suite run
separately outside this command is not included in the check evidence.

The JUnit adapter accepts unnamespaced XML and rejects DTDs and entity declarations
regardless of encoding, malformed or inconsistent reports, and reports already
present in the candidate. Entirely skipped or empty suites fail.
`policy.allow_skipped_tests` defaults to true; false also rejects mixed
passing/skipped suites. Suite-level errors fail.

For pytest **9.1.1**, `-p intentbond.pytest_junit --junitxml=results.xml` enables
the packaged subtest producer adapter. Native pytest counts subtests without
emitting a separate testcase for each; the strict completeness check rejects
that report. The adapter feeds each subtest to pytest's JUnit writer with a
distinct ID and closes it as a complete case, preserving outcomes, properties
and output. Parent cases remain present, and pytest's execution and exit status
are unchanged. Runtime exceptions during a subtest remain pytest call failures;
setup/teardown errors remain errors. Counts therefore include parent cases and
reported subtests, not just collected test functions. No report counts are
rewritten and the consumer's completeness checks remain unchanged. Loading the
adapter with a different pytest version and JUnit enabled is an error; revalidate
it when upgrading the pinned producer. It is opt-in and requires pytest in the
test environment; pytest is not an ib runtime dependency.

With the optional [execution-link profile](../intentbond/skills/intentbond/references/execution-links.md),
`tests.execution_links.required_artifacts` can require passing observations for
selected named OFT keys (`type~name`, without revisions). Each key must resolve
to exactly one candidate revision inside the configured types and test paths.
Missing declarations, unobserved/skipped checks, ambiguous or nonpassing outcomes
reject the overall check. `verify` enforces the same rule against retained data.
Omitting this field preserves diagnostic-only execution links. The gate cannot
establish generator adequacy, parameter completeness or requirement satisfaction.
The separate test-result attestation remains a suite result; a passing suite can
coexist with a rejected check when a required artifact was not observed.

## Source identity

The source digest is SHA-256 of canonical JSON containing sorted `{path, mode,
sha256}` entries. JSON uses sorted keys, ASCII escaping, compact separators, and
no trailing newline. Modes are `100644` (regular file), `100755` (executable file), or `120000`
(symlink). The retained manifest
contains those exact bytes.

Commit snapshots read Git blobs, unaffected by archive export attributes.
Worktree snapshots include tracked files as present on disk and untracked
nonignored files, including files outside trace inputs. Deleted tracked files
are absent. Tracing and tests consume the same captured candidate.

Before/after checks detect modifications to captured source and concurrent
changes to the original candidate. They cannot detect a command that changes and
restores source while running. Ignored untracked files, Git metadata, installed
dependencies, environment, and network state are outside source identity.
Snapshots omit `.git` and ignored local environments, reject submodules, and
leave Git LFS pointers unexpanded.

Relative symlinks within captured source retain their Git mode (`120000`) and
target bytes; their digest hashes the target string, not the referent. File and
directory links, link chains and dangling internal links are preserved for tests.
Absolute links, escaping targets, cyclic link chains and links into Git metadata
are rejected. A checkout filesystem must support native symlinks. Ignored targets
are not copied just because a link points to them.

OFT imports actual files once, without following aliases. Select the actual paths
in trace inputs and specification/test review paths, including when selecting a
subtree through a directory alias. Explicit alias inputs report this requirement.
Source identity and before/after checks include link targets and modes even when
they are outside the trace inputs. Review diffs show changed link targets rather
than dereferenced contents.

## Evidence files

### Optional execution links

For a JUnit scope, `tests.execution_links` can select format
`junit-properties-v1` and a nonempty `artifact_types` list. JUnit testcase
properties named `oft_id` then identify the exact OFT test artifacts executed.
See the [profile and producer example](../intentbond/skills/intentbond/references/execution-links.md)
for configuration, evidence fields, supported outcomes and limitations.

This adds no runtime dependency or default execution-completeness gate. Unknown
IDs or invalid supplied metadata reject the check; missing observations remain
visible and reject the check when named in `required_artifacts`. With the profile
disabled, existing behavior and bundles remain valid.

### Bundle contents

| Files | Contents |
| --- | --- |
| `scope.json`, `base-manifest.json`, `candidate-manifest.json` | Checked scope and source identities. |
| `base-items.xml`, `candidate-items.xml`, `*-import.log`, `*-trace.log` | OFT exports and execution logs. |
| `review.json`, `review.patch` | Specification and test changes. |
| `summary.md` | Human-readable results, changed items, and links to detailed records. |
| `tests.log`, optional `tests.xml` | Command output and retained JUnit report. |
| `evidence.json` | Check outcome, identities, tool versions, review state, diagnostics, and artifact hashes. |
| `test-result.json` | Test attestation, emitted only when execution has a confirmed stable source. |

`evidence.json` uses an unsigned [in-toto Statement
v1](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md). Its
subject is `candidate-manifest.json` and the source digest. The predicate type
is `https://github.com/kbak/intentbond/check/v0.2`. Error statements
may have no subject if source capture failed.

`test-result.json` uses the [in-toto Test Result
predicate](https://github.com/in-toto/attestation/blob/main/spec/predicates/test-result.md),
with the same subject and a digest of the scope file. It omits per-test names.
`tests.source_status` is `matched`, `changed`, or `unchecked`. Changed or
unchecked source suppresses this attestation, even if the subprocess passed; its
outcome remains in the check record for diagnosis. Verification requires
`matched`. Evidence without that field needs a fresh check.

Artifact hashes detect changes relative to the record. Statements are unsigned;
the caller's storage and access controls must establish who produced them.

## Exit codes and verification

| Check exit | Status | Meaning |
| --- | --- | --- |
| 0 | `passed` | Automated checks passed; no specification or test changes need this review gate. |
| 1 | `rejected` | Trace, policy, test, or source-stability checks failed. |
| 2 | `error` | Invalid input, missing tools, or execution/evidence setup failure. |
| 3 | `empty` | Empty selected scope; no successful coverage or executed-test claim. |
| 4 | `review_required` | Automated checks passed; specification or test changes await review. |

Preserve the current invocation's exit code as well as its bundle. A failed
invocation cannot be replaced with an earlier passing bundle.

`verify` checks retained artifacts and outcomes against the trusted scope, base,
and actual candidate contents. It normally accepts only `passed` evidence.
`--allow-pending-review` also accepts `review_required` and returns `review:
required`; the caller must still complete review before accepting the change.
Caller-required code review also applies to exit-0 checks.

Verification matches contents; it does not rerun tests. A worktree can match a
later exported commit with a different commit ID when the full manifest matches.
Rerun checks after repairs or shared-branch updates that change the candidate.

## Source, tracing and review boundaries

New check evidence and `review.json` include `source_boundaries`: a sorted inventory of changed paths from the complete captured base/candidate manifests. Each path records addition/deletion/modification, membership in `inputs`, and selection by `specification_paths`, `test_paths`, or optional `review_paths` (reported as `specification`, `test`, or `review`, in that precedence order). Counts are named for those exact meanings. Requirement-change entries and file-change entries in `review.changes` can describe the same path, so their count is not a distinct changed-file count.

A file outside the selected semantic-review roots is still included in full source identity when it belongs to the captured manifest. Editing it after a check invalidates source verification. This inventory does not expand the frozen scope, infer missing requirements, or certify the meaning of excluded files. The ordinary full candidate diff may still require review by the consuming workflow.

Source identity, OFT structural coverage, executed assertions and semantic approval are separate results. `review_required` means the selected changes need external review; it is neither approval nor rejection. `passed` does not turn out-of-selection documents into semantically approved artifacts.

`ib check`, the human summary and `ib explain` expose these boundaries. Verification recomputes new inventories from retained manifests and the trusted scope. Older schema-2 evidence remains readable: `ib explain` derives the inventory from its retained manifests without rewriting historical records.


### Fixture imports and illustrative IDs

Optional `trace_exclude` is a nonempty, unique list of literal relative paths or
directory prefixes within `inputs`. It affects only OFT import. Files remain in
the captured source, available to tests, and selected for review according to
`specification_paths`, `test_paths` and `review_paths`. For example, import `tests`
and exclude `tests/fixtures` to keep fixture application IDs out of the product
graph while reviewing fixture changes. This is trusted scope policy; editing a
candidate scope does not change the policy used for a check.

Write Markdown declaration IDs on their own lines. For a literal example, prefix
the inline ID with prose such as “Example:”; a line starting with a backtick ID
can be an OFT declaration even when followed by a sentence. IntentBond diagnoses
those imported lines before tests without rewriting OFT's grammar. Historical
recovery inventory still records them for explicit identity reconciliation.
