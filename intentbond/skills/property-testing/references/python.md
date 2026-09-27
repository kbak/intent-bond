# Python: Hypothesis

Use the project's existing pytest or unittest runner. Hypothesis is a test
dependency, not a dependency of ib or the application runtime. For a new project,
add it through the project's dependency/lock process. Preserve an existing
approved library choice.

- Use `@given` and strategies for function properties. Prefer constructive
  strategies to rejecting most generated values with `assume` or `filter`.
- Use `RuleBasedStateMachine` for interacting operation sequences when simpler
  generated lists are insufficient. Sequential stateful tests do not explore
  concurrent interleavings automatically.
- Isolate state per generated example. A function-scoped pytest fixture is shared
  across a property's examples; use a context manager or explicit reset inside
  the property instead of suppressing the fixture health check.
- Pin the library/environment for replay. Preserve useful counterexamples as
  `@example` or ordinary tests; the example database and reproduction blobs are
  useful caches/replay mechanisms, not a permanent portable format.
- Keep short CI budgets separate from longer exploration. A fixed seed or
  `derandomize=True` helps reproduce an environment, but repeatedly using only
  one search does not broaden exploration.
- Use `--hypothesis-show-statistics` for executed/invalid examples and stopping
  reasons. Do not invent counts from `max_examples`; it is a limit, not an
  observed count. Hypothesis's experimental observability format is optional,
  not a required portable evidence schema.

With plugin autoload disabled, explicitly enable `-p hypothesispytest`. Keep
health checks active and investigate excessive filtering or flaky failures.

OFT execution links reuse the existing collection-time `oft_id` marker hook and
pytest's xunit1 JUnit output. Put the marker on the property test itself, not on
each generated example. The JUnit case identifies the test artifact; OFT supplies
its relationship to the property or requirement. When adding cases to an existing
named artifact, reuse its marker but keep one canonical OFT declaration. Repeating
the full named source tag elsewhere creates duplicate artifacts, not a reference.
Native failure output preserves
the shrunk example. Include generator/configuration files in review-sensitive
test paths. The runnable Python example is under `examples/property-testing/python`.

Before writing scaffolding manually, consider Hypothesis Ghostwriter for
round trips, idempotence, or equivalent implementations. Review its assumptions;
it cannot determine business intent. For an existing OpenAPI/GraphQL schema,
consider Schemathesis instead of writing schema generation machinery.

Sources: [Hypothesis](https://hypothesis.readthedocs.io/en/latest/),
[stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html),
[replay](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html),
[Ghostwriter and statistics](https://hypothesis.readthedocs.io/en/latest/reference/integrations.html),
[Schemathesis](https://schemathesis.readthedocs.io/en/stable/quick-start/).
