# JavaScript and TypeScript: fast-check

Use fast-check as a development dependency with the existing Node, Vitest, Jest,
or other compatible test runner. Keep properties as normal source tests.

Use `fc.property` for synchronous checks and `fc.asyncProperty` for asynchronous
checks; await asynchronous assertions. Construct domain-specific arbitraries,
including boundary and invalid cases whose behavior is specified. Use native
command/model testing for stateful sequences when warranted. The scheduler can
explore controlled asynchronous orderings; it does not control arbitrary external
I/O or OS threads.

Retain failure seed, path, library version, and concrete counterexample. Model
command replay can also require a command replay path. Keep a regression example
even when native replay works; replay tokens depend on the generator and version.
Do not use `fc.sample` output as if a property had been checked. Ensure a failed
`fc.assert` reaches the runner as a failure, including when writing a custom harness.

Use the runner's native JUnit reporter if available. A native report without
per-case `oft_id` properties supports suite evidence, not the optional OFT
execution-link profile. Do not infer IDs from test names or claim an association
that the report did not supply. Validate any metadata adapter against passing,
failing, skipped, and absent cases before enabling that profile.

`examples/property-testing/typescript` is an executable JavaScript example using
Node's test runner and fast-check; the same APIs work in TypeScript. Its portable
scope intentionally records command-level evidence. It requires no custom reporter.

Sources: [properties](https://fast-check.dev/docs/core-blocks/properties/),
[advanced testing](https://fast-check.dev/docs/advanced/),
[replay configuration](https://fast-check.dev/docs/api/interfaces/Parameters/).
