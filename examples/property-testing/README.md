# Property-testing examples

Each directory is a standalone project with the same session expiration rule.
Its requirement includes an optional logical statement defining the domain,
assumptions, and postcondition. The test-search ranges are documented separately.
See the [property convention](../../docs/property-testing.md#optional-logical-statements).

Install only that project's test dependencies and run its normal command. The
examples need no agent. The Python example additionally emits per-case OFT
identities; the JS and Haskell examples record command-level evidence because
their reporters do not emit OFT IDs for individual test cases.

| Project | Setup | Run from that directory |
| --- | --- | --- |
| `python` | Install `requirements.txt` in a virtual environment | `python -m pytest --hypothesis-show-statistics --junitxml=test-results.xml` |
| `typescript` | `npm ci` | `npm test` |
| `haskell` | GHC plus QuickCheck in its package environment | `runghc Main.hs` |

The JS example uses runnable JavaScript to avoid requiring a TypeScript compiler;
fast-check exposes the same APIs to TypeScript. For Haskell, `cabal install --lib
QuickCheck` is one setup option in an isolated development environment; reuse an
existing project package configuration when available.

To exercise ib, copy one directory into a disposable Git repository, commit its
baseline, and run `ib check --base HEAD --candidate HEAD` with ib/OFT and its test
dependencies available. Use the supplied scope unchanged. Dependencies such as
node_modules or virtual environments are deliberately not captured source.
The JS scope uses `sh test.sh`, which installs the locked dependency into a
temporary copy outside captured source; this requires registry access. The
Python and Haskell scopes use the already provisioned language environment.
The Python scope requires passing execution observations for all three named
property artifacts. Selecting only the boundary test can pass pytest but fails
`ib check` because the postcondition and translation properties were not observed.
Required keys omit revisions; the report must still identify the exact imported revision.
OFT 4.9.0 does not import Haskell source tags, so that example uses native OFT
Markdown items in `traceability.md` to name the source symbols explicitly.

The postcondition property compares the expiration result with the complete rule
over generated inputs, including explicit examples at and after expiration.
The boundary property checks one tick before expiration and equality. The
translation property checks that shifting both timestamps preserves the decision.

Two deliberate defects demonstrate the difference: replacing `>=` with `>`
violates equality, while replacing it with `==` violates expiration after the
boundary. The second defect passes the boundary and translation properties;
the postcondition property rejects it. Each failing run must return nonzero,
and the Python report retains the corresponding `oft_id` results. These bounded
searches check the implementations; they do not prove the logical statement.

To check an example and its failure handling, provision the dependencies above and
ib/OFT, then run from the repository (or extracted source distribution):

```sh
python scripts/check_property_examples.py python --out /tmp/ib-python-example
python scripts/check_property_examples.py typescript --out /tmp/ib-js-example
python scripts/check_property_examples.py haskell --out /tmp/ib-haskell-example
```

Each output directory must be new. The script copies the example into a
disposable Git repository, checks correct behavior, applies each defect separately,
requires a native property failure, restores the source, and checks again.
It verifies the saved passing evidence and retains all logs. Use `INTENTBOND_OFT_JAR`
or `--oft-jar` for an existing JAR. JS runs require npm registry access.
