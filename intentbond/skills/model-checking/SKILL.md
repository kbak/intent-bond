---
name: model-checking
description: Author and maintain Alloy, Z3 SMT and CHC/Spacer models for selected requirements, validate their implementation mapping, and replay useful traces against real code.
---

Use the project's recovered requirements and linked implementation to select a
small behavioral slice. During onboarding, record candidates and uncertain intent
with the existing property notes. Author executable checks when the task authorizes
them and their intended meaning is established. Reuse requirement IDs and revisions.

Codex authors native Alloy `.als` or Z3Py models and an implementation-specific
replay harness. Use Alloy for relational structure and bounded state transitions;
use Z3 for arithmetic or other SMT theories with explicit source semantics, and
CHC/Spacer for safety invariants over arbitrary modeled step counts.
Committed checks run through the existing analyzer or solver without an LLM. Do not
introduce an intermediate specification language or a general source translator
for a slice that a small explicit model can describe.

Derive the assertions from the requirements and the transition relation from the
implementation. Read callers and relevant storage/authorization boundaries as
well as the selected functions. Map each modeled state field, transition, and
observation point to source symbols. Explain what is omitted and whether the
abstraction restricts behavior or conservatively admits extra behavior. A shared
property ID or passing model check does not prove that the translation is sound.

Record initial states, transition guards, frame conditions, environment behavior,
atomic operations, and arithmetic/clock assumptions. Never encode the guarantee
being checked as a fact, strengthen its preconditions, or remove failure paths to
make it pass. Keep model bounds separate from the requirement's domain. For
temporal models, include stuttering and justify fairness; finite traces alone do
not establish eventual progress. For explicit `State` orderings, document their
exact cardinality and number of transitions.

Add named assertion `check` commands and satisfiable `run` witnesses exercising
successful behavior and relevant transitions. Check a deliberate guard or frame
mutation where useful; preserve its counterexample before changing anything.
Distinguish a bad abstraction, a disputed requirement, and an implementation bug.
Review substantive changes to assumptions, predicates, and bounds with the model.

Replay generated instances through actual implementation operations, comparing
observable state after each step. Use the existing property test framework to
exercise additional implementation traces where practical. Preserve useful
counterexamples as ordinary regression fixtures. Label replay as sampled
correspondence evidence, not a proof that all implementation behavior is covered.

Read [execution.md](references/execution.md) for Alloy,
[smt.md](references/smt.md) for Z3 SMT, or [chc.md](references/chc.md) for
CHC/Spacer reachability, induction certificates and concrete traces. Read only
the relevant implementation guide: [Python](references/python.md) or
[Daml](references/daml.md).

Report the model/source identity, native command bounds, tool version, assumptions,
and separate check/replay outcomes. A completed Alloy UNSAT assertion search means no
counterexample in the modeled bounds. A Z3 UNSAT violation query establishes the
encoded goal under its assumptions; validate those assumptions are satisfiable
and distinguish unrestricted numeric domains from bounded transition depth. An unsatisfiable witness, missing command,
parse error, timeout, or unknown result must not become passing evidence.
