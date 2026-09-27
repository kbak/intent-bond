"""Native Z3Py obligations over exact integer amounts."""

from z3 import And, If, Implies, Ints

from intentbond.smt import Obligation


def obligations():
    amount, requested = Ints("amount requested")
    domain = And(amount >= 0, requested >= 0)
    accepted = requested <= amount
    remainder = If(accepted, amount - requested, amount)
    observations = {
        "amount": amount,
        "requested": requested,
        "accepted": accepted,
        "remainder": remainder,
    }
    return {
        "Conservation": Obligation(
            domain, Implies(accepted, requested + remainder == amount), observations
        ),
        "CanSplit": Obligation(
            domain, And(accepted, requested > 0, remainder > 0), observations, kind="run"
        ),
    }
