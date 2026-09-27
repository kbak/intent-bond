---
name: property-testing
description: Identify, add, and maintain property tests for reviewed requirements using the project's existing test library and runner.
---

A property is a rule intended to hold across a defined set of inputs or states.
An executable property test searches for violations using generated inputs.

When documenting an existing project's requirements with `ib recover`, identify
existing tests, proposed properties, input domains, and missing checks in the
feature table or claim notes. Preserve tests, generators, dependencies, and runner
configuration during that documentation step. Add or change tests once the starting
requirements are reviewed and the task authorizes test work. Passing documentation
checks do not approve inferred intent.

Improve the maintained test suite for the selected behavior. Start from approved
requirements and their linked implementation; inferred behavior is a proposed
property until its intended meaning is established. Reuse existing test libraries,
requirements, IDs, and fixtures. Add a separate property item only when it expresses
a useful refinement, not a duplicate requirement. Ordinary example tests remain useful.

To improve the test suite, start with missing checks identified in the requirements
or review. When behavior changes, follow the affected requirements and code to
existing properties. Update assertions, generators, and assumptions, and add
checks for new requirements or uncovered behavior. Preserve identities for surviving promises;
revise changed meaning through the existing requirement/review policy. Record
deferred checks and counterexamples in the same maintained documentation/tests.

For each selected property, explain its scope and assumptions in readable prose
and link an executable assertion to the same obligation. For critical or ambiguous
rules, optionally add **Domain**, **Assumptions**, and **Logical statement** beside
the prose and existing ID. These are Markdown conventions, not machine-checked
fields. Define variables, types, units, and quantifiers. Identify a precondition,
postcondition, state invariant, or temporal property; define old/new state,
observation points, and time or concurrency assumptions when relevant. Reuse clear
existing statements and create a separate linked property only when it needs its
own identity. Preserve the meaning of the requirement; flag conflicts between
prose and logic instead of silently choosing one.

Keep caller/environment assumptions separate from guarantees. Do not assume the
behavior that must be checked, exclude required invalid-input cases, or turn test
generator ranges into domain restrictions. Stronger preconditions, narrower domains,
and weaker guarantees are requirement changes subject to normal revision and review.
Derive checks from the complete statement; boundary or metamorphic checks may cover
only part of it. A formula alone supplies no execution or proof evidence.

Exercise the actual implementation. Specify generators for relevant boundaries,
invalid inputs, and operation sequences; generated valid inputs must not silently exclude promised
behavior. Pair safety constraints with required successful behavior where relevant.

Use the existing runner and one appropriate library. Read only the relevant guide:
[Hypothesis](references/python.md), [fast-check](references/typescript.md),
[QuickCheck](references/haskell.md), or [Hegel](references/hegel.md).
For Daml contracts, read the [Daml guide](references/daml.md); Haskell's
QuickCheck is not a drop-in Daml dependency.
If an adapter supplied this text without the references, read the matching installed
file with `importlib.resources.files("intentbond")` under
`skills/property-testing/references/`. No new agent service is needed.

Distinguish an implementation defect from a wrong assertion, invalid generated
input, or harness failure. Preserve the failing example before repair. Changes to
approved properties, exclusions, generators, budgets, skips, or assumptions belong
in the existing review; do not narrow them merely to obtain a pass. Use a targeted
known defect or deliberate mutation when useful to check assertion sensitivity.

Run committed tests without an LLM. Keep native replay details and turn useful
minimal failures into regression examples. Report the checked revision, method,
scope, result, and limits through the existing test/evidence flow. A property-test
pass describes a search, not a proof. Missing tests, excessive discards, timeouts,
and harness errors must remain visible. One property can exercise many inputs;
do not count those inputs as distinct requirements or proofs.

Humans can follow this same procedure without an agent. With OFT, preserve exact
requirement/test IDs and revisions and the project's existing coverage chain.
Keep property identity independent of the checking method so later runtime,
differential, schema-based, or symbolic checks can target the same obligation.
Use a formal tool's native language when needed, linking its model or predicate
to the property ID and revision and retaining assumptions, bounds, and tool version.
Shared IDs do not establish semantic equivalence. Review the translation and the
model's relationship to the implementation; never assume the guarantee merely to
make a model check pass.

For an authorized Alloy or Z3 modeling task, use the sibling
[model-checking skill](../model-checking/SKILL.md). During recovery, identify useful
model candidates in the existing property notes; its executable authoring and
replay steps apply when the task includes that work.
