# Alloy execution and evidence

Reuse the upstream Alloy 6.2.0 distribution and its bundled SAT4J solver. Java 17+
is sufficient for the pinned JAR. Provision it separately from application runtime
dependencies:

```sh
ib install-alloy --destination /path/to/tools
export INTENTBOND_ALLOY_JAR=/path/to/tools/alloy-6.2.0.jar
ib alloy-check --root /path/to/project --manifest tests/models/checks.json --out /tmp/alloy-result-1
```

The output directory must be new or empty (ib precreates JUnit report parents).
Existing files are never replaced. A manifest
uses schema version 1, a native model path, explicit relative input files, readable
assumptions, a per-command timeout, and exact command names:

```json
{
  "schema_version": 1,
  "model": "tests/models/ownership.als",
  "inputs": ["requirements.md", "src/store.py", "tests/models/ownership.als", "tests/models/mapping.md"],
  "assumptions": "Serialized storage transitions; see tests/models/mapping.md for omitted behavior and source mapping.",
  "timeout_seconds": 60,
  "commands": [
    {"name": "Ownership", "kind": "check", "artifact_id": "utest~ownership-model~1"},
    {"name": "CanComplete", "kind": "run", "artifact_id": "utest~ownership-model~1"}
  ]
}
```

Include imported local Alloy modules and the implementation/dependency files used
by the abstraction. The runner copies only declared files plus the manifest into
an isolated input directory. Bundled Alloy library imports remain available.
This input list is an explicit coverage boundary, not automatic dependency discovery.
Bounds live in native Alloy commands; their original text and parsed scope fields
are retained from Alloy's receipt. The runner does not set `--nooverflow`, because
it excludes overflowing instances. Choose adequate integer width and document the
relationship to source arithmetic; do not use exclusion to conceal source overflow.

Each `check` expects UNSAT; each `run` expects SAT. The runner requires at least one
of each and validates the exact command identity and kind. Exit 0 means all those
expectations held, 1 means a counterexample or unsatisfiable witness, and 2 means
execution/input failure. Multiple commands may target one requirement. An OFT
artifact ID is optional; when used, declare it once in a
supported OFT file within the test scope and link it to the required revisions.
Alloy `.als` annotations are not assumed to have an OFT importer.

`result.json`, `junit.xml`, input copies, process logs, native receipts and XML
instances are retained. JUnit embeds the input hashes, assumptions, native receipts
and XML instances, so existing ib report retention preserves counterexamples.
The standalone report binds explicitly listed inputs. Run through `ib check` to
add the existing whole-candidate snapshot, trusted scope, and review policy.
Do not claim a standalone check is a whole-repository source attestation.

For CI, invoke this command from the project's aggregate test command and add its
fresh `junit.xml` to `tests.reports`. Put the model, mappings, manifest, and replay
harness in reviewed test paths. Keep the JAR outside captured source. The old
baseline scope cannot enforce a newly added model command: adopt the updated
scope through normal review before claiming it is required.

Native references: [Alloy release](https://github.com/AlloyTools/org.alloytools.alloy/releases/tag/v6.2.0),
[Alloy 6 temporal scopes](https://alloytools.org/alloy6.html).
