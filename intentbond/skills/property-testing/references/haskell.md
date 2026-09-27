# Haskell: QuickCheck

Use the project's existing Hspec or Tasty integration, or a small executable that
turns `quickCheckResult` outcomes into the process exit code. Calling `quickCheck`
only prints a result; printing a failure is not sufficient to fail CI.

Make tested types explicit. Define appropriate `Arbitrary`/`Gen` instances and
shrinkers; default generation may rarely reach a domain boundary. Use `classify`,
`cover`, and `checkCoverage` where distribution requirements are meaningful.
Treat `GaveUp` and missing expected failures as unsuccessful verification. Avoid
implication-heavy properties that discard most of their inputs.

Preserve the actual failing value, seed, size, and library version. Save important
counterexamples as ordinary tests as well. Reuse state-machine libraries already
adopted by the project instead of introducing a new state model by default.

Tasty has QuickCheck integration and existing XML reporters. Their availability
does not establish support for the per-case OFT metadata extension. Until an
adapter is tested, use ib's command/suite evidence and retain native output.
`examples/property-testing/haskell` demonstrates correct failure exit behavior
without introducing a second test-runner dependency.

Sources: [QuickCheck reference](https://hackage.haskell.org/package/QuickCheck/docs/Test-QuickCheck.html),
[Tasty integration](https://hackage.haskell.org/package/tasty-quickcheck),
[Tasty XML reporter](https://github.com/ocharles/tasty-ant-xml).
