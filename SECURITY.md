# Security policy

[Magyarul](SECURITY.hu.md)

## Supported versions

| Version | Supported |
|---|---|
| 0.5.x | yes |
| older | no |

## Reporting a vulnerability

Please report it privately, not in a public issue or pull request.

Use [**Report a vulnerability**](https://github.com/lipi4242/mentat/security/advisories/new)
(the **Security** tab of this repository; GitHub private vulnerability reporting). Only the
maintainers see it. Describe what you found, how to reproduce it, and which version or commit you
ran.

A Mentat agent's `bug-report` skill never files a security problem in public: when the error
looks like a leak or a way around a guard, it stops and points you here.

You get an acknowledgement within a few days. A fix ships as a patch release in the supported
line, and the advisory is published once the fix is available. We credit you in the advisory
unless you prefer not to be named.

## Verifying a release

Each release tag `vX.Y.Z` is created once and never moved or deleted (a repository ruleset
enforces it), and the GitHub Release is immutable once published. Its source archive comes with
`SHA256SUMS` and a signed build-provenance attestation:

```
sha256sum -c SHA256SUMS
gh attestation verify mentat-vX.Y.Z.tar.gz -R lipi4242/mentat
```

## Scope

This repository is the product only. Values that belong to one installation (Telegram bot
tokens, Cloudflare secrets, agent tokens, the admin instance file) live outside it and must
never be committed. If you find such a value here, report it the same private way.

What matters most, by part:

- **Brain** (the root): the install downloads tools into `.mentat/bin/` and checks each against
  the sha256 list in `release.json` before anything runs. A way to make a changed file pass
  that check is in scope.
- **Engine** (`engine/`): code copied into your agent repo by `engine/sync-to.sh`. Writing
  outside the target repo, or running a pack whose version range the engine should refuse.
- **Fleet** (`fleet/`): runs on your own server and talks to the Telegram Bot API with a token
  you provide. Leaking that token, running commands for someone who is not on the bridge's
  allowlist, or writing outside an agent's own files.
- **Admin** (`admin/`): runs on your own Cloudflare account. Reading or changing data without
  the admin key, or an agent token reaching more than its own plugin.

## Known limits

The role guard (`MENTAT_ROLE`, `reference/bekotes/szerep_guard.py`) protects against
accidental access; it is not a security boundary. A role that sets out to get around it can
delete the agent's `.mentat/` folder (or run `git clean -fdx`), after which the guard no longer
runs, or start a nested session under another role (`MENTAT_ROLE=<other> claude -p`). Physically
separating the data (a role sees only what is mounted for it) is planned for a later release.
