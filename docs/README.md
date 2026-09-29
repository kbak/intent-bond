# Documentation

Start with the [README](../README.md) for installation and a first check.

## Guides

- [Recover a baseline](recovery.md) — document an existing project and review the proposal.
- [Property testing](property-testing.md) — connect requirements to generated test cases.
- [Model checking](model-checking.md) — use Alloy and Z3 for selected properties.
- [Requirement granularity](requirement-granularity.md) — choose IDs and inspect change impact.

## Reference

- [IntentBond intent](intent.md) — user outcomes, rationale, and design direction.
- [IntentBond specification](spec.md) — technical promises linked to intent, code, and tests.
- [Command and evidence contract](contract.md) — CLI, scope, snapshots, results, and verification.
- [Artifact meanings](../intentbond/skills/intentbond/references/semantics.md) — what the evidence establishes.
- [Execution links](../intentbond/skills/intentbond/references/execution-links.md) — associate observed tests with coverage.
- [Security](../SECURITY.md) — execution assumptions, producer trust, and reporting.

## Examples and agent guidance

- [Session expiration](../examples/session) and [pytest session](../examples/pytest-session).
- [Property tests](../examples/property-testing) in Python, TypeScript, and Haskell.
- [Alloy](../examples/model-checking), [SMT](../examples/smt-checking), and [CHC](../examples/chc-checking) checks.
- [Development skill](../intentbond/skills/intentbond/SKILL.md) and
  [existing-project skill](../intentbond/skills/recover-baseline/SKILL.md).

## Contribute

- [Contributing](../CONTRIBUTING.md) — setup and change guidelines.
- [Validation](validation.md) — tests, packaging checks, and language examples.
- [Property test maintenance](property-evaluation.md) — generators and mutation checks.
