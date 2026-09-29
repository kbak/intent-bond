# CHC reachability with Spacer

Use this mode for safety properties across arbitrary numbers of modeled steps,
or recursive loops over arbitrary finite lists. Z3's existing `[smt]` extra
includes Spacer; no additional solver dependency is needed. The shared runner
constructs linear Horn clauses from native Z3 transition formulas, validates
inferred invariants, and reconstructs finite traces. It supports one recursive
reachability relation with named transitions and any number of state fields or
control phases. It is not a frontend for arbitrary nonlinear Horn-clause systems.

## Author a native system

A model exports `obligations()` returning named
`intentbond.chc.Reachability` objects. Each contains a `System`, a
native Boolean `target`, and `kind="check"` or `"run"`.

**For a check, the target is the violation to exclude.** This differs from
`Obligation.goal` in the SMT API, which states the desired guarantee. For a run,
the target is a reachable state required as a witness.

```python
from z3 import And, Int
from intentbond.chc import Reachability, System, assign


def obligations():
    state = {"balance": Int("balance")}
    following = {"balance": Int("next_balance")}
    amount = Int("amount")
    system = System(
        state=state,
        next_state=following,
        initial=state["balance"] == 0,
        inputs={"amount": amount},
        steps={
            "deposit": And(
                amount >= 0,
                assign(state, following, balance=state["balance"] + amount),
            )
        },
    )
    return {
        "Nonnegative": Reachability(system, state["balance"] < 0),
        "Positive": Reachability(system, state["balance"] > 0, "run"),
    }
```

Current/next fields must have identical keys and matching sorts, and all state,
next-state and input constants must be distinct. Initial states and targets may
reference only current state; steps may also reference next state and inputs.
Use `assign` to constrain every next field, retaining the current value for
fields omitted from updates. Native formulas may be written directly, but a
missing frame equality permits arbitrary changes; it does not mean unchanged.

Choose state sufficient to express the property and its interactions. Derive
transitions from code and targets from requirements. Do not assume the invariant
being checked or remove allowed transitions to obtain a proof. Ghost accounting
variables must follow events independently of the target equation. Keep source
numeric ranges, overflow, rounding and failure semantics explicit.

If a model deliberately selects successful paths, state that restriction and
avoid claims about rejection, authorization or rollback. For a loop inside one
atomic transaction, replay the complete transaction; internal iterations are not
separately committed ledger states. Arbitrary steps do not imply arbitrary
contracts/parties unless their representation also supports them. Safety alone
does not establish termination, fairness or eventual progress.

## Run and retain

Use the same captured-input manifest structure as SMT checking:

```json
{
  "schema_version": 1,
  "model": "balance.py",
  "inputs": ["balance.py", "README.md"],
  "assumptions": "Exact integer deposits, initially zero, arbitrary finite histories.",
  "timeout_seconds": 30,
  "solver_timeout_ms": 10000,
  "commands": [
    {"name": "Nonnegative", "kind": "check"},
    {"name": "Positive", "kind": "run"}
  ]
}
```

Include source mappings, requirements, model helpers, implementation and replay
inputs. An optional `artifact_id` on each command supplies its declared OFT
identity in JUnit. Models are trusted Python, executed with the caller's
privileges from captured inputs. Process isolation is not a security sandbox.

```sh
ib chc-check --root examples/chc-checking --manifest checks.json --out /tmp/chc-check
```

Outputs must be new or empty. The process timeout covers model construction,
Spacer, certificate checking and trace reconstruction. Each native query also
has a solver timeout. Exit 0 means all selected checks/witnesses passed; 1 means
an obligation failed; 2 means execution/evidence was erroneous or inconclusive.

The runner first requires satisfiable initial states. A check passes only if its
target is unreachable and the inferred invariant passes ordinary SMT checks:
initial states imply the invariant; every transition preserves it; and it excludes
the target. The per-transition checks use unconstrained current/next/input values
and the original transition formula. They do not rely on bounded exploration.
An invalid or unavailable invariant cannot become passing proof evidence.

For reachable targets, the runner extracts the named rule sequence from Spacer's
native derivation and solves that exact sequence with ordinary SMT to obtain
concrete states and inputs. It does not search only up to a chosen depth and call
that a safety proof. Unsupported/infeasible derivations fail validation. Required
runs exercise meaningful branches, including nontrivial loop counts; satisfiable
initial states alone cannot expose every overconstrained transition relation.

## Results and replay

The native fixedpoint query convention is **SAT means reachable**. A check fails
on reachable; a run requires reachable. UNSAT means unreachable. `unknown`,
timeout, missing results and failed validation are never a pass.

The portable `horn.smt2` instead asserts that the target is impossible and uses
standard Horn satisfiability: **SAT means safe; UNSAT means unsafe**. Keep this
polarity separate when adding another solver. The file enables comparison with
other solvers; exporting it does not claim it has been cross-checked externally.

Captured source files are retained under `inputs/`, and each command's native
queries, receipts and process log are retained under `native/<name>/`.
Evidence includes:

- Captured inputs/hashes, tool version, scope and JUnit in the existing format.
- `query.smt2`: native fixedpoint clauses and target query.
- `horn.smt2`: standard Horn clauses with an assertion excluding the target.
- `receipt.json`: native answer and either validated invariant checks or a trace.
- `certificate-*.smt2`: initialization, transition and target-exclusion queries.
- `trace.smt2`: a reachable derivation reconstructed with concrete states/inputs.

Trace fields use the SMT runner's exact observations: `sort`, native `smt2`, and
`value` for integers/bit-vectors (decimal strings) or Booleans. The trace contains
`initial` and ordered `steps`, each with `name`, `before`, `inputs` and `after`.
A zero-step trace is valid when the target holds initially. Application decoders
must map all relevant inputs and compare implementation outcomes/state.

Use `intentbond.model_evidence.ReplayEvidence` for implementation
replay pipelines. Within its context, `record(name, action, artifact_id=...)`
retains the action's result or exception, execution time and a copy of current
`metadata`. It writes incremental JSON/JUnit and records pipeline failures on
exit. Keep domain-specific decoding, operation execution and expected state
comparisons in the application repository. Include actual implementation mutation
checks when feasible; a compilation error is not evidence of defect detection.

A validated invariant establishes the modeled safety claim. Source-derived or
LF-derived correspondence requires separate justification; sampled replay and
cross-solver agreement do not establish a sound translation.
