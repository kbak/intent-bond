# Running the tests

These instructions are for contributors testing IntentBond itself.
To check your own project, follow [check a change](../README.md#check-a-change).

From the project checkout, in a Python virtual environment with Git and Java
available:

```sh
python3 -m pip install --require-hashes --only-binary=:all: -r requirements/ci.txt
python3 -m pip install --no-index --no-deps --no-build-isolation -e .
ib install-oft
ib install-alloy
python3 -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

Tests run OFT, Alloy, Z3, and example test commands in temporary directories. Missing
pinned JARs fail the suite. To use existing JARs, set `INTENTBOND_OFT_JAR` and `INTENTBOND_ALLOY_JAR`
instead of running the respective installers. Alloy remains optional for application
projects that do not use model checking. Runner tests execute the real analyzer,
including counterexamples, impossible witnesses, missing commands and bad models.
Z3 tests additionally check native SMT-LIB replay, vacuous assumptions, `unknown`
results, bounded model construction, missing evidence and exact observations. Spacer tests validate induction queries,
portable Horn result polarity, reconstructed traces, vacuity, unknown outcomes,
malformed evidence and mutation counterexamples.

The [CI workflow](../.github/workflows/ci.yml) builds the source distribution and
then its wheel without build isolation, installs the wheel without dependency
resolution, and runs packaged tests/fixtures from a
separate working directory. It checks Python 3.11 and 3.12, packaged skill
references, lint, and the three language examples. Example smoke checks require
passing behavior, rejection of boundary and equality-only defects, and passing
restoration. The equality-only defect satisfies the boundary and translation
properties but violates the full expiration postcondition. Native logs and
evidence are retained as artifacts.
JavaScript dependencies and OFT downloads require network access. QuickCheck is
provisioned only in its dedicated disposable runner.

The [property mutation checks](../.github/workflows/property-evaluation.yml) run
on manual dispatch, separately from the normal pull-request checks.

## Dependency updates

CI installs exact Python versions and artifact hashes from
[`requirements/ci.txt`](../requirements/ci.txt), including build tools and
transitive dependencies. Published package metadata retains compatible ranges.
GitHub Actions use full commit SHAs; Python, Java, and Node tool versions are
also explicit. OS packages and the hosted runner image follow their upstream
distribution updates.

Regenerate locks with uv, then review the diff and run the checks above:

```sh
uv pip compile pyproject.toml requirements/ci.in --extra test --extra smt --python-version 3.11 --universal --generate-hashes --output-file requirements/ci.txt
uv pip compile pyproject.toml --python-version 3.11 --universal --generate-hashes --constraint requirements/ci.txt --output-file requirements/runtime.txt
uv pip compile examples/property-testing/python/requirements.in --python-version 3.11 --universal --generate-hashes --output-file examples/property-testing/python/requirements.txt
```

Existing locks retain selected versions. Use `--upgrade-package NAME` for an
intentional update, changing exact inputs in `requirements/ci.in` where needed.
Keep action version comments with their verified upstream SHAs. Changes to a
runtime lock consumed by IntentMade also need its dependency lock refreshed.

## Coverage

Execution-link tests exercise the existing session fixture and a real pytest
producer. They cover parameterized cases, deselection, skips, expected failures,
setup errors, invalid IDs/revisions, duplicate identities, unsupported retry
extensions, source mutation, and altered retained summaries. A passing suite
with an omitted linked test must report `not_observed`. Opt-in required-execution
tests cover rejection, deletion, skip policy, revision continuity, candidate
policy edits, and independent enforcement when verifying retained evidence.
The `test` extra installs
pytest and Hypothesis for development; neither is a ib runtime dependency.

Hypothesis properties cover JUnit completion, source identity, requirement
revisions and evidence freshness. They run under both unittest and pytest.
See [property test maintenance](property-evaluation.md) for commands, search
limits and mutation checks.

Recovery tests start with an unannotated project, exercise citation and editing
checks, run real OFT/test validation, apply the proposed patch in the fixture,
establish the adopted baseline, and check a subsequent change. They also cover
invented/missing citations, unresolved intent, behavior/document changes, missing
links/tools, failing existing tests and concurrent edits. Compatibility tests
cover JavaScript module annotations and adding OFT IDs/Needs to existing specification
prose while retaining original citations. Documentation tests cover cited rewrites,
moves/deletions and adoption, original ID accounting, revisions, splits, merges and
removals in both recovery modes. They reject undocumented changes, fabricated citations,
test assertion edits and weakened coverage floors. Actual semantic extraction quality
is not established by these deterministic fixtures.
Coverage-comment movement tests verify that generated IDs do not require mappings,
while explicitly named IDs remain accounted for. Duplicate original authored IDs
are exercised as a currently unsupported recovery case.
In-place tests cover reviewable checkout edits, retained originals/provenance,
dirty/staged/untracked work, branch and commit changes, concurrent edits, linked
Git worktrees, automatic storage discovery, schema 1 compatibility, and exclusion
of quoted historical annotations from live coverage. Both modes exercise adoption
and subsequent development. They do not measure how accurately an agent reconstructs requirements. Assess
that separately by reviewing the agent's proposed documentation against its sources.
