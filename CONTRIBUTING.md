# Contributing to RepoDx

Thanks for helping! RepoDx stays small on purpose: one Python file, no
dependencies, and checks that a beginner can read.

## Your first contribution

1. Pick an issue labeled
   [`good first issue`](https://github.com/omerbek/repodx/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
   and comment that you're taking it, so two people don't do the same work.
2. Fork the repo, make the change on a branch, and run the tests (see below).
3. Open a PR that says `Fixes #<issue number>`. A maintainer reviews it, usually
   within a day.

One issue per PR keeps reviews quick.

## Reporting a false alarm or a missed secret

Open an issue with:

- the RepoDx version (`repodx --version`)
- the finding title and the file type (for example "OpenAI API key in a `.ts` file")
- the line that caused it, **with the secret replaced by fake characters of the same shape**

Never paste a real key into an issue. If you did, rotate the key.

## Adding a check

1. Write a small function in `repodx.py` that returns `make_finding(...)` results.
2. Add a plain-language fix to `FIXES`. Say what to do, not only what is wrong.
3. Call it from `build_report`.
4. Add tests in `tests/test_repodx.py`. Build fake keys at runtime with `fake(...)`
   so no literal secret is committed.
5. Run it on a few real repositories and check that it does not raise false alarms.

Pick severities carefully:

- **critical**: someone can use it against you right now (a live key, a public write rule)
- **warning**: likely a mistake that should be fixed before sharing
- **info**: a suggestion

## Running tests

```bash
python3 -m unittest discover
python3 repodx.py .   # the repo must keep scoring 100
```

## Releasing

1. Update `__version__` in `repodx.py`, `version` in `pyproject.toml`, the pinned
   versions in `README.md` and `docs/README.tr.md`, and add a section to
   `CHANGELOG.md`.
2. Merge to `main`, then either push a tag (`git tag v0.4.0 && git push origin v0.4.0`)
   or run the `release` workflow from the Actions tab, which tags `main` for you.
3. The `release` workflow runs the tests, checks the tag matches the version,
   publishes a GitHub release with `repodx.py` attached, and publishes the same
   version to PyPI using trusted publishing.
