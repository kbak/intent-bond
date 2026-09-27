# Independently evolving retry promises

This small CLI-tested example separates exponential growth from the maximum delay policy. Run `python3 -m unittest discover -s tests -v` from this directory.

To inspect the bounded evolution in a disposable Git copy:

1. Commit the baseline and remember its commit. Keep `scope.json` frozen.
2. Change `req~retry-cap~1` to revision 2 and its promised cap from 8 to 16 seconds. Keep `req~retry-growth~1` unchanged.
3. In `retry.py`, update only the cap declaration/reference and `min(delay, 8)` to `min(delay, 16)`.
4. In the cap test, advance its declaration/reference, assert the new exact boundary and update the over-cap expectation to 16. Preserve the growth test's identity and assertions.
5. Run `ib check --base BASE --out /tmp/retry-impact`, then `ib impact --evidence /tmp/retry-impact/evidence.json`. The check returns 4: current tests/links passed, selected review is pending.
6. In a separate candidate, leave the cap test's requirement reference at revision 1 while keeping its updated assertions. Tests pass, but checking rejects the stale reference.

`tests/test_impact.py` executes both cases and an annotation/revision-only control. See [requirement granularity](../../docs/requirement-granularity.md) for exact structural counts, stable-ID/split guidance and measurement limits. No measured reduction in review effort is claimed.
