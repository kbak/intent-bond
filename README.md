# IntentBond

IntentBond connects intent, requirements, specifications, code, and tests with
explicit links. Follow them to find what a change affects and update the related
artifacts together.

It checks links across Git versions, runs your tests, and saves results tied to
the source checked. Optional Alloy and Z3 checks add formal verification for
selected properties.

## How it works

Keep requirements in Markdown and reference them from code and tests using
[OpenFastTrace (OFT)](https://github.com/itsallcode/openfasttrace) IDs:

```markdown
### Session expiration
`req~session-expiration~1`

Sessions expire after 30 minutes of inactivity.

Needs: impl, utest
```

```python
# [impl->req~session-expiration~1]  # Beside the implementation
# [utest->req~session-expiration~1] # Beside the test assertion
```

`1` is the requirement revision. OFT checks that the required links exist and
reference that revision. IntentBond runs the tests and reports changes against
a Git baseline. Review determines whether the linked code and checks satisfy
the requirement.

Include rationale and intermediate design or specification items where useful;
a separate document for each is optional. See the [session example](examples/session)
and [artifact meanings](intentbond/skills/intentbond/references/semantics.md).

## Install

Requires Python 3.11+, Git, and Java 17+ on Linux or macOS. Install `intentbond`
from this checkout in a Python virtual environment:

```sh
python3 -m pip install .
ib install-oft
```

The OFT installer downloads and checksum-verifies the pinned release. For an
existing JAR, set `INTENTBOND_OFT_JAR` or pass `--oft-jar` to `ib check`.

## Add traceability to an existing project

Start with one feature. Use its documentation, code, and tests to propose
requirements and links. Flag inferred intent and missing tests for review.

Give a coding agent the [existing-project skill](intentbond/skills/recover-baseline/SKILL.md),
or start manually from a clean project checkout:

```sh
ib recover
```

This saves the original source and prepares citation records. Add requirements,
code/test references, and a `scope.json` following the [recovery guide](docs/recovery.md),
then run:

```sh
ib recover-check
```

Exit 4 means checks passed and review is pending. Read `recovery-review.md`,
resolve open questions, and commit the accepted changes. Recovery records remain
local under Git metadata; the guide explains how to retain and share them.

## Check a change

### 1. Configure the project

Copy [scope.json](examples/session/scope.json) and adapt its paths, coverage rules,
and test command. Commit it at the project root with the starting requirements
and references.

Checks use the baseline's scope, so candidate edits cannot change their own
checking rules. A caller can instead supply a trusted external scope with
`--scope`. Tests run on captured source; their dependencies must be available
in the checking environment.

### 2. Validate the starting commit

From the project's checkout:

```sh
ib check --base HEAD --candidate HEAD
```

### 3. Make changes and check them

```sh
ib check
```

By default, this compares your working tree with the branch's merge base against
the default branch, or `HEAD` on the default branch. Use `--base COMMIT` to choose
another baseline. Each run saves results in a fresh temporary directory; use
`--out /path/to/check-1` to choose a new directory outside the project.

See the [command reference](docs/contract.md#check-and-verify-inputs) for defaults
and source-capture details.

## Understand and review the result

Open `summary.md` in the reported evidence directory for changed requirements,
test results, and pending review.

| Exit from `ib check` | Meaning |
| --- | --- |
| 0 | Automated checks passed; no specification or test files changed. |
| 4 | Automated checks passed; specification or test changes need review. |
| 1, 2, 3 | Validation failed, could not run, or had an empty scope. |

Review the full diff. `review.patch` contains only specification/test changes;
passing checks do not approve them.

Inspect a requirement and its links in saved evidence:

```sh
ib explain 'req~session-expiration~1' --evidence /path/to/check/evidence.json
```

Match a later commit to the source already checked:

```sh
ib verify --candidate HEAD --evidence /path/to/check/evidence.json
```

Use the original baseline and scope. For exit-4 evidence, `--allow-pending-review`
allows matching while review remains pending. `verify` does not rerun tests.
See [evidence semantics](intentbond/skills/intentbond/references/semantics.md)
for what each result establishes.

## Work with an agent

Give your agent the [development skill](intentbond/skills/intentbond/SKILL.md)
to maintain requirements, code, tests, and links during changes. Configure CI
separately to enforce checks on pull requests.

IntentBond also works manually and in CI. The
[OpenHands factory integration](https://github.com/kbak/openhands-factory/blob/main/docs/traceability.md)
is optional.

## Add property tests

Use the [property-testing guide](docs/property-testing.md) to express selected
requirements as assertions over generated inputs. Tests use your existing runner;
examples cover Hypothesis, fast-check, and QuickCheck.

Optional [execution links](intentbond/skills/intentbond/references/execution-links.md)
associate individual test results with requirement coverage and can require
selected tests to run and pass.

## Check selected properties with Alloy or Z3

Formal checks are optional. The [model-checking guide](docs/model-checking.md)
covers authoring models, reviewing assumptions, replaying traces against code,
and retaining results. Committed checks run without an LLM.

Run the Alloy example:

```sh
ib install-alloy
ib alloy-check --root examples/model-checking --manifest checks.json --out /tmp/alloy-check-1
```

Or install Z3 and run the SMT example:

```sh
pip install 'intentbond[smt]'
ib smt-check --root examples/smt-checking --manifest checks.json --out /tmp/smt-check-1
```

`ib chc-check` uses Z3 Spacer to check safety over arbitrary numbers of modeled
transitions. See the [CHC example](examples/chc-checking).

These runners work standalone or alongside tests in `ib check`. Results concern
the model under recorded assumptions and bounds; review and implementation
replay assess its correspondence to real code.

## Inspect requirement evolution

```sh
ib impact --evidence /path/to/check/evidence.json
```

Compare requirement declarations, links, and source changes. The
[granularity guide](docs/requirement-granularity.md) explains how to give
independently changing promises their own IDs.

For configuration and evidence formats, see the [reference](docs/contract.md).
For contributing, see [running the tests](docs/validation.md).
