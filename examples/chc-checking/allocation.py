"""An allocation loop with an unrestricted number of iterations."""

from z3 import And, Ints

from intentbond.chc import Reachability, System


def obligations():
    initial, allocated, remaining, count, ni, na, nr, nc, row = Ints(
        "initial allocated remaining count next_initial next_allocated next_remaining next_count row"
    )
    system = System(
        state=dict(initial=initial, allocated=allocated, remaining=remaining, count=count),
        next_state=dict(initial=ni, allocated=na, remaining=nr, count=nc),
        initial=And(initial >= 0, allocated == 0, remaining == initial, count == 0),
        inputs=dict(row=row),
        steps={
            "allocate": And(
                row >= 0,
                row <= remaining,
                ni == initial,
                na == allocated + row,
                nr == remaining - row,
                nc == count + 1,
            )
        },
    )
    return {
        "Conservation": Reachability(system, allocated + remaining != initial),
        "SeveralRows": Reachability(system, And(count == 4, allocated > 0, remaining > 0), "run"),
    }
