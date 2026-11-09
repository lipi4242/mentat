# Contributing to Mentat

Thank you for helping. Bug reports, ideas and fixes are all welcome.

## How this repository works

This repository is **generated**: at each release the maintainers' development repository
composes the public tree, checks it (no private data, every pinned link resolves, versions agree)
and publishes it here as one commit `Mentat vX.Y.Z` with a tag `vX.Y.Z`. Nothing is merged here
directly, because the next release would replace it.

So:

- **Issues** are the main way in. They are read and answered here.
- **Pull requests** are welcome too. A maintainer ports an accepted change to the development
  repository, keeps you as co-author (`Co-authored-by:`), and the pull request is closed with a
  link to the release that ships it.
- **Security problems** never go in an issue or a pull request: see [SECURITY.md](SECURITY.md).

## Reporting a bug

Use the **Bug report** form. It asks for the version (`version` in `release.json`), the part,
how Mentat runs for you, and the error. Before you post, remove tokens, keys, passwords, e-mail
addresses and paths that contain your user name.

If you run a Mentat agent, ask it to report the bug: its `bug-report` skill collects the
versions and the error, removes secrets and personal data, looks for an existing issue (and offers
to add your details there instead), and shows you the draft. Nothing is posted until you say yes,
and it is posted from your own GitHub account; the issue gets the label `agent-reported`.

## Suggesting a feature

Use the **Feature request** form, and describe the problem before the solution. Questions about
installing or using Mentat go to [Discussions](https://github.com/lipi4242/mentat/discussions).

## Working on the code

Each part has its own tests; CI runs all of them on every pull request
(`.github/workflows/ci.yml`):

| Part | Run |
|---|---|
| Brain (the root) | `python3 -m unittest discover -s reference/manifest` |
| Engine | `cd engine && python3 -m pytest -q` |
| Fleet | `cd fleet && PYTHONPATH=src python3 -m unittest discover -s tests -q` and `node --test "bridge/test/*.test.mjs"` |
| Admin | `cd admin && npm ci --prefix worker && npm --prefix worker run test` |

Keep a change small and focused, add a test that fails without it, and update the docs that
describe the behaviour (English, and Hungarian where the page has a `.hu.md`).

## Conduct

Everyone taking part follows the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contribution is licensed under the
[Apache License 2.0](LICENSE), like the rest of the project.
