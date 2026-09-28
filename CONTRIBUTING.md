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

## Make a change

- Read the [command and evidence contract](docs/contract.md) before changing CLI
  behavior, scope handling, source capture, or evidence formats.
- Keep source identity, structural coverage, test outcomes, and semantic review
  distinct. A passing link check must not imply requirement satisfaction.
- Add focused regressions for changed behavior. Prefer runnable examples over
  assertions about what an agent or formal model should achieve.
- Update guides and packaged skill references when their instructions change.
- Use the upstream tool's supported capabilities before introducing an adapter.

Keep runtime data, credentials, local evidence bundles, and development diaries
out of the repository. Documentation should describe current behavior and
reproducible checks.

## Submit a pull request

Explain the problem, resulting behavior, and checks performed. Call out any CLI,
schema, compatibility, or packaging changes. Keep unrelated refactors separate.

Contributions are provided under the repository's [MIT license](LICENSE).
Retain third-party notices and avoid copying incompatible material.
