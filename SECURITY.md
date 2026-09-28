# Security

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/kbak/intentbond/security/advisories/new).
Include the affected revision, a minimal reproducer, expected and observed
behavior, and practical impact. Remove credentials and private project data.
Do not disclose an unpatched vulnerability in a public issue.

## Execution and trust

IntentBond is a local CLI. It invokes Git, OFT, optional formal analyzers, and the
test command selected by the trusted scope. Test commands run with the invoking
account's permissions and inherited environment. Source snapshots are not a
process sandbox. Run untrusted projects in an isolated worker without sensitive
credentials or host access.

The baseline scope, or an explicitly supplied external scope, selects the checking
policy. Candidate edits must not silently replace that policy. The caller is
responsible for choosing and protecting the baseline and external configuration.

Evidence records source and policy identities, test results, and artifact hashes.
Verification must reject mismatched or altered inputs. Bundles are unsigned:
matching hashes do not authenticate their producer. Consumers must establish
producer trust separately.

Structural links, passing tests, and formal results support different conclusions.
Specification review and approval remain external decisions. Formal checks concern
the supplied model under its recorded assumptions and bounds.

## Relevant reports

Examples include paths escaping intended file boundaries, candidate-controlled
policy substitution, stale or mismatched evidence being accepted, and results
incorrectly represented as passed. Explain how the behavior is reached and what
trust boundary it crosses. See the [contract](docs/contract.md) for the detailed
execution and evidence semantics.
