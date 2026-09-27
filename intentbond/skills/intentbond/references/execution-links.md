# Link individual test results to traceability records

A passing test suite does not tell the checker which requirement-linked tests ran.
Enable `tests.execution_links` to associate individual JUnit results with named
OpenFastTrace (OFT) test artifacts. OFT supplies their links to requirements.

This optional configuration uses JUnit testcase properties and needs no additional
ib runtime dependency. The project supplies its test runner and emits the IDs.
The fields and evidence format below are provisional.

## Enable for a scope

Add this object inside the existing `tests` configuration:

```json
"execution_links": {
  "format": "junit-properties-v1",
  "artifact_types": ["utest"]
}
```

This requires `tests.format: junit` (the default). Select the project's actual
verification types; `utest` is an example, not a universal requirement. Each
referenced artifact must be imported by OFT, have the exact ID and revision, and
originate within `test_paths`. Review this configuration as part of the trusted scope.

Omitting `execution_links` preserves the existing suite/command behavior,
including for old evidence bundles. Enabling the profile requires a fresh check.

## Require selected artifacts to pass

Optionally add named OFT keys to the same configuration:

```json
"execution_links": {
  "format": "junit-properties-v1",
  "artifact_types": ["utest"],
  "required_artifacts": ["utest~expiration-boundary"]
}
```

Keys use `type~name` without a revision; the report still supplies the exact
`type~name~revision`. Each required key must resolve to exactly one imported
candidate artifact within the selected types and `test_paths`, and every
reported case associated with it must pass. Missing declarations or observations,
skips, failures, ambiguity, mixed outcomes and multiple imported revisions reject
the overall check, even when its suite passes. An empty or duplicate required
list, a revision-qualified key, or a type absent from `artifact_types` is invalid
configuration. Omit the field to retain diagnostic-only behavior.

Use explicit, stable named artifacts. A legitimate revision update keeps the
required identity and uses the normal review process; the policy does not pin
the old revision or approve new meaning. Deleting or renaming that identity
requires updating the trusted policy. Candidate scope edits cannot disable a
rule loaded from the baseline. Unlisted artifacts need not pass this additional
gate, but ordinary suite, skip and metadata validation still apply.

The evidence retains observations separately from policy diagnostics. `ib verify`
recomputes associations and enforces required execution from the retained
JUnit/OFT data and the supplied trusted scope. No new evidence format, dependency,
or agent is needed. Old configurations and their evidence keep their behavior;
enabling this field requires a fresh check and a checker supporting the field.

## Author and report an explicit link

Give the OFT test marker an explicit name using its existing tag syntax:

```python
# [utest~expiration-boundary~1->req~session-expiration~1]
```

The corresponding JUnit case supplies that test artifact's complete ID:

```xml
<testcase classname="test_session" name="test_expiration_boundary">
  <properties>
    <property name="oft_id" value="utest~expiration-boundary~1"/>
  </properties>
</testcase>
```

The property identifies the test artifact, not the requirement. OFT maintains
the requirement relationships; the report does not duplicate them. Repeat
`oft_id` properties if one case explicitly maps to several test artifacts.
Identical repeated values are deduplicated. Suite-level properties do not map
individual cases. Empty IDs, wrong revisions, unknown or duplicate OFT IDs, IDs
outside the selected types/paths, and linked cases without names are invalid.
Invalid supplied metadata rejects the check even when the suite itself passes.

Prefer named OFT artifacts for continuity across source movement. Do not infer
links from similar names or nearby file/line locations. A report's claim that a
case corresponds to an artifact still needs the normal code/test review.

## Supported producer: pytest

The runnable [pytest session example](https://github.com/kbak/intentbond/tree/main/examples/pytest-session)
uses a project-local collection hook to transfer `@pytest.mark.oft_id(...)`
markers into `item.user_properties`. Collection-time metadata survives skips,
expected failures and setup failures; adding a property inside the test body
would not cover those cases.

The collection hook is small and lives in the project's `conftest.py`:

```python
def pytest_collection_modifyitems(items):
    for item in items:
        for marker in item.iter_markers(name="oft_id"):
            for identifier in marker.args:
                item.user_properties.append(("oft_id", identifier))
```

The example selects `junit_family = xunit1`, registers the marker, and disables
the pytest cache provider. Other runners can emit these fields; validate their handling of passing, failing,
skipped, and missing cases before relying on the association. Pytest notes
that testcase properties can fail strict JUnit schema validation in other
consumers; do not assume the extension works in every CI report viewer.

Sources: [pytest properties](https://docs.pytest.org/en/stable/how-to/output.html#record-property)
and [OFT named tags](https://github.com/itsallcode/openfasttrace/blob/4.9.0/doc/user_guide.md#optional-elements).

## Read the evidence

`evidence.json` retains the provisional schema-1 `tests.execution_links` object:

- `format`, `property`, `status` (`recorded` or `invalid`), and `diagnostics`.
- `artifacts`: selected test-artifact IDs, each with `status` and its `cases`.
- Each case retains its ancestor `suite` names, `classname`, `name`, status,
  ambiguity `diagnostics`, and outcome `details` (kind, type and message).
- `unlinked_cases`: cases without a resolved association, including invalid IDs.

The enclosing evidence binds these observations to the source and scope; its
artifact inventory hashes both the original JUnit report and OFT export.
`ib verify` and candidate `ib explain` recompute associations from those retained
inputs and reject altered or missing summaries. Tests are not rerun.

`ib explain` adds `linked_tests` and `execution_link_diagnostics` in JSON and
lists individual cases in text. It follows OFT's existing `covered_by` edges to
find selected test artifacts, including through design items. Explaining a test
artifact directly shows its own observations. `linked_test_execution` summarizes
only those artifacts:

| Status | Meaning |
| --- | --- |
| `passed` | All reported associated cases for the selected artifacts passed. |
| `failed` | All summarized outcomes are failures/errors. |
| `skipped` | All summarized outcomes are skipped, disabled or not run. |
| `not_observed` | The selected artifacts have no associated case in this report. |
| `ambiguous` | A case identity is repeated, has conflicting outcomes, or uses unsupported outcome/retry extensions. |
| `mixed` | The underlying statuses differ; inspect the per-artifact and per-case entries. |
| `not_established` | No usable association evidence, invalid metadata, unmatched source, command error, or no selected test artifact reachable from this item. |

Case identity includes suite ancestry, classname and name. Distinct parameterized
cases can map to one OFT artifact; duplicate case identities are ambiguous,
including an annotated case duplicated by an unannotated one. Recognized retry
extensions are not collapsed into a pass. A producer that hides retries cannot
be reconstructed from its final report. Only represented parameter cases are
known; this profile cannot discover an omitted parameter or prove that every
required scenario ran.

By default, missing observations, skips and ambiguity are diagnostic. The optional
`required_artifacts` gate rejects them for the named artifacts only. Existing suite
and skip policy still apply. Source changes or an incomplete
test command leave reported observations diagnostic; baseline explanations never
reuse candidate executions. The separate in-toto test statement still summarizes
the suite/command outcome and does not assert per-requirement verification.

A passing suite with the boundary test deselected must show `not_observed` for
that test artifact, and rejects the check when that artifact is required. This requirement
cannot detect an omitted parameter case, an insufficient search budget, a narrowed
generator, or a producer that falsely reports execution. A linked `passed` outcome
still requires review of the assertion and its relation to the requirement.
