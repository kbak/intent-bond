# Hegel as an optional engine

Hegel shares an in-process engine across language-specific libraries. This can
reduce duplicated generator/shrinker engineering when adding languages. It does
not remove each language's test runner, bindings, build setup, or result mapping.
For Python, use Hypothesis directly. Reuse an existing project library unless a
migration has a concrete benefit.

The upstream compatibility guide currently describes Hegel as beta. Check the
selected binding, platform, native binary availability, API, and version before
adopting it. The old `hegel-core` protocol repository is archived; current
libraries use `libhegel` through FFI. Do not build a new integration on the old
protocol. Haskell also has the separately maintained Zizek binding; it is not the
same package as QuickCheck.

Use Hegel's own agent skill and binding documentation for authoring mechanics,
while preserving this workflow's approved obligations and evidence boundaries.
No Antithesis subscription is necessary for the open libraries. Before claiming
support for a binding, exercise a passing property, a deliberate failure,
shrinking/replay, and propagation of the result to the project's runner. Keep
native results; do not translate a sampled pass into a proof.

This package provides selection guidance, not a bundled Hegel runtime or a
certified Hegel reporter. Adding a new engine should need a project test command
and, only when useful, a small native-result adapter rather than a new property DSL.

Sources: [Hegel](https://hegel.dev/),
[compatibility](https://hegel.dev/compatibility),
[TypeScript binding](https://github.com/hegeldev/hegel-typescript),
[agent skill](https://github.com/hegeldev/hegel-skill),
[Haskell binding](https://github.com/MercuryTechnologies/zizek).
