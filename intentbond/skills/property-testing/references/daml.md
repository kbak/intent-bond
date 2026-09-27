# Daml: generated contract tests

Inspect `daml.yaml`, the SDK/LF versions, and the existing test boundary. Reuse
Daml Script fixtures or an established ledger API client. Daml's resemblance to
Haskell does not make ordinary Haskell QuickCheck packages directly usable.

For a project with Daml Script tests, a small Hypothesis driver can generate JSON
arguments for a parameterized `Script ()`. Keep contract creation, choice execution,
queries, and behavioral assertions in Daml. See the [Python guide](python.md) for
Hypothesis configuration, replay, and pytest execution links.

## Run the implementation

Build the project's test DAR using its pinned SDK before the property run. Fail
on build errors; do not fall back to an unchecked existing DAR. A representative
invocation for SDKs supporting these flags is:

```sh
dpm script --dar path/to/tests.dar --script-name Properties:checkCase --ide-ledger --static-time --input-file case.json
```

Check `dpm script --help` for the project's SDK. Run from the appropriate Daml
package directory so SDK selection is explicit. Use the project's normal build
and test commands as well; `dpm test` may require a local socket for its test service.

- Start a fresh IDE ledger for every generated example and shrinking attempt.
  A session fixture may build the DAR once, but must not share mutable ledger state.
- Match the JSON representation to the Daml input type. Generate exact fixed-point
  amounts using integer quanta and decimal strings; avoid binary floats and implicit
  decimal rounding. Derive precision and bounds from the actual `Numeric` type.
- Query actual output contracts and consumed inputs. A Python calculation or a
  pure state model alone does not check contract authorization, choice execution,
  or ledger state transitions.
- Pair valid operations with separate required rejection properties. Do not filter
  invalid inputs out of a property whose promise is to reject them. Use distinct
  input contracts and the appropriate parties when those are genuine preconditions.
- Preserve exit failures, timeouts, JSON inputs, and native Daml diagnostics.
  Distinguish assertion counterexamples from compilation, decoding, or harness errors.

Starting a JVM per example trades throughput for simple isolation. Measure it
before choosing the sampling budget. Reuse an existing ledger client when it offers
better throughput and reliable per-example isolation. The IDE ledger checks local
contract semantics; it does not establish distributed Canton behavior.

## Link the result

Use existing requirement IDs and OFT conventions. If OFT does not import the
project's `.daml` annotations, declare implementation/test mappings in Markdown
with paths and symbol names. Such mappings need maintenance; structural link
validation does not resolve Daml symbols.

A pytest property can report its OFT test-artifact ID through the existing JUnit
metadata hook. Declare that artifact once, within the scope's `test_paths`; a
Markdown mapping beside the tests works when Daml annotations are not imported.
Link to the declaration from other docs rather than repeating a standalone OFT ID.
Keep the Daml script, generator, fixture, dependencies, and runner
configuration in the reviewed test scope. Retain the test DAR digest and SDK
version with the run. Existing Daml tests run by a setup command have command-level
evidence unless their individual results also have a validated report mapping.

## Other reusable tools

[daml-props](https://github.com/OpenZeppelin/daml-props) supplies native generators
and a pure state-machine runner. Its current runner is not an effectful Daml
Script runner; check SDK compatibility and its experimental status before adoption.
[Hypothesis2Daml](https://drops.dagstuhl.de/entities/document/10.4230/OASIcs.FMBC.2026.5)
provides a ledger JSON API approach. Check API/authentication compatibility and
isolation against the target environment before reusing that integration.

Sources: [Daml Script invocation and JSON input](https://docs.digitalasset.com/build/3.4/reference/cheat-sheet.html),
[IDE ledger script invocation](https://docs.digitalasset.com/build/3.4/sdlc-howtos/smart-contracts/upgrade/smart-contract-upgrades.html).
