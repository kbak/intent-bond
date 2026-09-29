# Contributing to IntentBond

Bug reports, documentation improvements, and focused pull requests are welcome.
For larger changes, open an issue describing the problem and proposed behavior.
Report vulnerabilities through
[SECURITY.md](SECURITY.md).

## Development setup

Use Python 3.11+, Git, and Java 17+ on Linux or macOS. In a virtual environment:

```sh
python -m pip install --require-hashes --only-binary=:all: -r requirements/ci.txt
python -m pip install --no-index --no-deps --no-build-isolation -e .
ib install-oft
ib install-alloy
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

See [validation](docs/validation.md) for dependencies, packaged tests, examples,
and optional mutation checks. CI builds a source distribution and wheel, then
tests the installed package outside the source checkout.

The [secret scan](.github/workflows/secrets.yml) runs checksum-pinned Gitleaks over
all fetched history on pushes and pull requests. A synthetic token first checks
that detection works. CI uses upstream rules without candidate config, ignore
files or inline suppressions. To check locally with Gitleaks 8.30.1:

```sh
gitleaks git --redact --ignore-gitleaks-allow --log-opts="--all" .
```

Git mode does not inspect uncommitted files. Also run
`gitleaks dir --redact /path/to/release` on the exact release directory.
Use obvious dummy fixture values instead of realistic tokens; revoke or rotate
any real exposed secret before arranging history cleanup.
Follow [clean packaging](docs/validation.md#build-a-release-from-clean-source)
and [evidence sharing](docs/contract.md#sharing-evidence) before publishing
packages, logs or check bundles.

## Make a change

- Start from the affected requirements in the [specification](docs/spec.md) and
  follow their links to [intent](docs/intent.md), implementation, and tests.
  For each commit, keep the outcomes, promises, reference
  docs, code, and assertions consistent; unchanged behavior can keep unchanged
  requirement wording and IDs.
- Read the [command and evidence contract](docs/contract.md) before changing CLI
  behavior, scope handling, source capture, or evidence formats.
- Keep source identity, structural coverage, test outcomes, and semantic review
  distinct. A passing link check must not imply requirement satisfaction.
- Add focused regressions for changed behavior. Prefer runnable examples over
  assertions about what an agent or formal model should achieve.
- Update guides and packaged skill references when their instructions change.
- Use the upstream tool's supported capabilities before introducing an adapter.

Use the [development skill](intentbond/skills/intentbond/SKILL.md) for the check
and review workflow. Record the starting commit before editing, run `ib check`
against that baseline before committing, and use the same baseline when verifying
the committed result. This preserves the change being reviewed when working on
`main`. Consider requirement splits when promises need to evolve independently;
the [granularity guide](docs/requirement-granularity.md) describes how to migrate
their links without losing obligations.

Keep runtime data, credentials, local evidence bundles, and development diaries
out of the repository. Documentation should describe current behavior and
reproducible checks.

## Submit a pull request

Explain the problem, resulting behavior, and checks performed. Call out any CLI,
schema, compatibility, or packaging changes. Keep unrelated refactors separate.

Contributions are provided under the repository's [MIT license](LICENSE).
Retain third-party notices and avoid copying incompatible material.
