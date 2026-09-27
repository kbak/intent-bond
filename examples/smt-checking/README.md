# Z3 arithmetic checks

Install `intentbond[smt]`, then run from the tool checkout:

```sh
ib smt-check --root examples/smt-checking --manifest checks.json --out /tmp/amount-check-1
```

`Conservation` checks an integer split and `CanSplit` requires a nontrivial witness.
Changing the accepted remainder from `amount - requested` to `amount` produces a
counterexample. Making the input assumptions contradictory rejects the check as
`unsatisfiable_preconditions`. This example describes mathematical integers; an
application model must supply its actual numeric and operational semantics.
