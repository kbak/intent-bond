# Allocation loop

Install `intentbond[smt]`, then run:

```sh
ib chc-check --root examples/chc-checking --manifest checks.json --out /tmp/allocation-chc
```

The loop transfers any nonnegative amount from remaining to allocated. Spacer
checks conservation over arbitrarily many iterations. The runner validates the
inferred invariant's initial, inductive and safety obligations using ordinary
SMT. `SeveralRows` requires and reconstructs a concrete four-step witness; that
witness length does not limit the conservation check.

Change `na == allocated + row` to `na == allocated + row + 1` to introduce value
creation. Conservation then fails with a concrete native derivation and validated
trace. No application implementation is represented by this example.
