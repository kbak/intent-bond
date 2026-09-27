# Executable properties

A property states a rule that should hold across a defined set of inputs or
states. For example, a session must be expired whenever its idle time is at least
30 minutes. A property test generates inputs and searches for cases that violate
the rule.

Use property tests for selected requirements where broader input coverage is
valuable. Keep the assertions and generators in the project's normal test suite.
They run without ib, OFT, an agent, or a factory. Use OFT references to connect
tests to requirements; ib records results tied to the checked source.

Give an agent the packaged [property-testing skill](../intentbond/skills/property-testing/SKILL.md),
or follow it manually. For example: "Add property tests for these scheduling
requirements using the existing test workflow. Preserve their meaning and retain
regression examples for any defects found." The skill reuses existing IDs and
does not require another requirements document or approval stage.

## When to add and update properties

When [documenting an existing project](recovery.md), identify existing properties
and valuable missing checks. Record the source of each proposed rule, its input
domain, assumptions, and existing tests in the requirements or claim notes.
Preserve executable tests and dependencies during that initial documentation step.

After the starting requirements are reviewed, add selected property tests using
the project's runner. Check the changes with `ib check` against that baseline.
This can continue the same task when test work is already authorized; unresolved
intent still needs a decision through the project's normal review process.

When behavior changes, update affected assertions, generators, and assumptions.
Add properties for new requirements or uncovered behavior, and keep useful
counterexamples as regression tests. Changes to a requirement's meaning follow
the existing revision and review policy. A human or agent writes these tests;
the tools supply guidance and record check results.

## Describe the property and link its tests

Keep the promise separate from how it is checked. A precise existing requirement
can be linked directly to a named test. When a derived property adds useful
detail, use the project's OFT artifact conventions (custom types are supported),
link it to the requirement, and link its tests to it. Do not duplicate every
requirement in a mandatory property layer.

The smallest useful property description states its behavior, domain, and
assumptions in Markdown beside its identity. Executable predicates, generators,
and harnesses live in the test suite and participate in the existing review.
Later runtime assertions, differential tests, schema checks, or symbolic analysis
can target the same identity with their own methods and evidence limits.

### Optional logical statements

For selected critical or ambiguous requirements, add a logical statement beside
the existing prose and OFT ID. Use these labels when helpful; they are ordinary
Markdown, not required fields or a new specification language:

- **Domain:** variables, types, units, and the inputs or states covered.
- **Assumptions:** environmental conditions or caller obligations the guarantee
  depends on. State arithmetic, clock, and concurrency assumptions where relevant.
- **Logical statement:** the property, with its quantifiers and observation point.
  Identify it as a precondition, postcondition, state invariant, or temporal property.

For example, the expiration requirement can include:

```text
Domain: last and now are integer timestamps in the same unit; timeout is a
        positive integer. result is the Boolean returned by expired(last, now, timeout).
Assumptions: mathematical integer arithmetic, without overflow.
Logical statement (postcondition):
  For every input in the domain, on return:
    result is true if and only if now >= last + timeout.
```

A precondition is an obligation before a call; a postcondition is a guarantee
on completion under the stated assumptions and preconditions. For a state
invariant, name the state and when it must hold, such as after every completed
operation. For a temporal property, define the relevant events and any ordering,
time, or fairness assumptions. For state changes, distinguish old and new values
and state what must remain unchanged when that matters.

Add only details that clarify behavior or guide a check. Reuse an already precise
statement rather than restating it in several notations. If independently changing
properties need separate identities, use linked OFT items through the project's
existing conventions. A formula that disagrees with the prose is an unresolved
specification conflict; neither representation silently overrides the other.

Keep assumptions separate from obligations being checked. An agent must not turn
"reject unauthorized requests" into a precondition that all requests are authorized.
Specify required invalid-input behavior separately. Strengthening a precondition,
narrowing a domain, or weakening a guarantee changes the promise and follows the
normal revision and review policy.

Readable logic is not automatically machine-checked. OFT imports it as requirement
text and checks links; ib records changes and execution results. Tests and later
formalizations must reference the relevant property ID and revision using the
existing traceability mechanism. Keep generator ranges, sample counts, and solver
bounds in the checking configuration or its documentation; they do not redefine
the requirement's domain.

When a formal tool is introduced, use its native language and identify the model
or predicate that represents the property. Record its assumptions, bounds, and
tool version with the result. Model checking also needs initial states, allowed
transitions, and a justified relationship to the implementation. A shared property
ID does not prove that prose, tests, and models mean the same thing. Reuse predicates
where practical and review translations; do not assume the guarantee in the model
instead of checking it.

For bounded Alloy checks, the [model-checking workflow](model-checking.md) adds
native models, implementation replay and retained solver evidence for selected
properties, reusing these identities and assumptions.

## Record check results

Use native JUnit or command results through the existing scope. Python can also
use the optional [per-test execution links](../intentbond/skills/intentbond/references/execution-links.md).
One reported property case may execute many generated examples; the JUnit case
count is not an input count or a proof count. Preserve native diagnostics, observed
statistics when available, tool versions and replay details.

Scope assumptions, exclusions, generator distributions, and test budgets affect
what was exercised. Review meaningful changes to them. A passing search does not
establish a universal claim; an absent, skipped, invalid, or timed-out check does
not become passing evidence. To require observations for critical checks,
set `tests.execution_links.required_artifacts` to their named OFT keys, such as
`["utest~expiration-boundary"]`. For each required key, the checker requires
exactly one imported revision and reported passing results. Missing declarations
or results, skips, and ambiguous revisions fail the check. Other linked test results
are reported without this additional requirement. This detects absent artifacts;
it cannot detect missing generated inputs or weakened generators.
The [execution-link reference](../intentbond/skills/intentbond/references/execution-links.md#require-selected-artifacts-to-pass)
defines the policy and its limits.

## Choosing a library

Use Hypothesis for Python, fast-check for JS/TS, and QuickCheck for Haskell when
the project has no established choice. Read only the corresponding skill
reference. Hegel is an optional shared engine with language-specific bindings;
its current beta/platform requirements are documented in the Hegel reference.
There is no requirement to install every framework in a project or factory image.

For Daml contracts, the [Daml guide](../intentbond/skills/property-testing/references/daml.md)
describes using generated inputs with Daml Script and recording ledger-test results.

The [runnable examples](../examples/property-testing/README.md) use the same small
expiration obligation in the three language environments. The Python example
demonstrates individual OFT execution links; the other examples intentionally
use command-level evidence until a per-case metadata producer is validated.

## Checking property quality

Check that each property exercises the promised boundaries and detects a known
defect or deliberate mutation. Preserve useful failing inputs as regression
examples. Review generators, assumptions and budgets alongside assertions;
passing execution alone does not establish that a property is adequate.
