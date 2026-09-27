# Property test maintenance

The Hypothesis tests exercise the [source, review and evidence contract](contract.md)
through the normal unittest or pytest runner:

- [JUnit properties](../tests/test_report_properties.py) check outcome preservation,
  completion policy, suite-level failures and missing cases.
- [Snapshot properties](../tests/test_snapshot_properties.py) check source identity
  across worktree, staged, committed and archive captures, including paths, bytes
  and executable modes.
- [Revision properties](../tests/test_revision_properties.py) check revision rules,
  requirement removal and movement using OFT-shaped records. OFT checks graph validity.
- [Lifecycle properties](../tests/test_lifecycle_properties.py) check evidence
  freshness across sequential source edits, Git operations and restoration, using
  real Git/OFT and an independent reference map of file contents and modes.

## Run the properties

Install the test dependencies and OFT as described in [validation](validation.md),
then run with native search statistics:

```sh
python -m pytest tests/test_report_properties.py tests/test_snapshot_properties.py tests/test_revision_properties.py tests/test_lifecycle_properties.py --hypothesis-show-statistics
```

The generators and budgets are defined in the test files. Searches are bounded
and deterministic, with health checks enabled. Repeating them reproduces the same
search; vary inputs or budgets deliberately when exploring further. Concurrent
writers, external environment changes and malicious reporters are outside the
lifecycle model. Existing example tests cover additional cases.

## Check sensitivity to mutations

```sh
python scripts/evaluate_properties.py --out /tmp/ib-property-mutations
```

Use a new output directory. The script checks the unmodified tests in a disposable
source copy, applies each fixed mutation separately, and runs its targeted test.
The source repository is unchanged. Output includes source hashes, dependency
versions, patches, native diagnostics, JUnit and a JSON summary.

| Mutation | Expected detection |
| --- | --- |
| Omit untracked source files | Captured paths differ from the created files. |
| Discard executable mode | Changing the mode incorrectly preserves source identity. |
| Hash only file data | Renaming a file incorrectly preserves source identity. |
| Permit changed meaning at the same revision | Revision policy fails to reject the change. |
| Hide removed requirements | A removed promise disappears from review. |
| Accept stale evidence | Verification accepts changed source contents. |

The command returns nonzero if a mutation survives or a check fails to run.
Timeouts, collection errors and unrelated exceptions do not count as detections.
When the targeted source changes, update the fixed mutation and its expected
assertion. These checks measure sensitivity to the listed faults; they are not
an estimate of general bug detection or a proof of correctness.
