# Bootstrap Contract — Reference Manual

You are an AI colleague bootstrapped from `lipi4242/mentat`. This file says what is fetchable, what it costs to read, and when you need it.

Base URL (every path below is relative to it): `https://raw.githubusercontent.com/lipi4242/mentat/v0.5.0/`

## Do not fetch what a command already does

| Need | Run (from the brain repo root), instead of reading templates or `ls`/`grep`ing |
|---|---|
| Skeleton, verification | `python3 .mentat/bin/mentat_scaffold.py --lang <hu\|en> [--check]` |
| New case / person / todo / decision / brain-dump / connector | `python3 .mentat/bin/mentat_brain.py new <type> "Title" [--due YYYY-MM-DD]` — prints the file path |
| What is due (≤8 lines) | `python3 .mentat/bin/mentat_brain.py due [--days 7] [--all] [--full]` |
| Look something up | `python3 .mentat/bin/mentat_brain.py find <word>...` |
| Rename a note (links + index) | `python3 .mentat/bin/mentat_brain.py mv <old> --title "New title"` |
| Commit the brain | `python3 .mentat/bin/mentat_brain.py commit "message"` |
| What runs, where is what | `python3 .mentat/bin/mentat_brain.py where` |
| What already exists, before new code, a service or a timer | `python3 .mentat/bin/mentat_brain.py where --find "<the USER's words>"` (then `--decide`; `--map` = table) |
| A relative date ("next week") to dates, or the readings to ask about | `python3 .mentat/bin/mentat_dates.py "<phrase>" --tz <tz>` (exit 0 exact, 3 ask, 1 unknown) |
| Which building blocks are installed | `python3 .mentat/bin/mentat_cli.py status` |

## Fetch only when (size in KB; `<l>` = `en` or `hu`)

| Path | KB | When |
|---|---|---|
| `reference/initialization.md` (EN) / `initialization.hu.md` | 4 | first run, once |
| `reference/intro-chat/intro-questions.<l>.md` | 4 | the intro chat, once |
| `reference/templates/<type>.<l>.md` | 1-2 | creating a note the tool does not cover: exploration, specification, procedure, project |
| `reference/templates/case.<l>.md` | 5.5 | tailoring the case definition at the first case, or closing a recurring occurrence |
| `reference/templates/decision.<l>.md` | 3 | only the drift rule: acting against a `decided` decision |
| `reference/templates/subagent*.<l>.md`, `acceptance-form.<l>.md` | 1-5 | persona or acceptance work, with `reference/subagents.<l>.md` (8) |
| `skills/develop/SKILL.<l>.md` | 5 | large AND under-specified work; the reasoning is `reference/development-process.<l>.md` (11) |
| `skills/subagent/SKILL.<l>.md`, `skills/status/SKILL.<l>.md` | 4 / 3 | running those skills; index `skills/_index.md` |
| `reference/mentat-json.<l>.md` | 5 | editing `mentat.json` by hand or reasoning about synergies |
| `reference/ownership.<l>.md` | 3 | managed vs personal text, publishing boundary |
| `reference/publish-web.md` (EN) / `publish-web.hu.md` | 3 | the USER wants the work on the web or on their phone: Cloudflare account, token screen by screen, Worker + D1 on workers.dev, Access |
| `reference/capabilities.md` (EN) / `capabilities.hu.md` | 4 | reading a `where --find` answer or deciding on its receipt (use / enable / new) |
| `reference/contract.md` (EN) / `contract.hu.md` | 4 | before a list, export, report or a message to several people is built or sent: the agreed task in a file (`mentat_contract.py`), checked before it goes out (`mentat_accept.py`) |
| `reference/google.md` (EN) / `google.hu.md` | 5 | anything in the USER's Google account (invitation, mail, sharing, a sheet): the tools, the console steps, the sign-in (also from a server), the calls |
| `reference/bekotes/BEKOTES.<l>.md` | 6 | taking over an existing business (its repos, an old agent's memories, Linear): run it in order; its step 0 downloads the tools |
| `reference/frameworks/<name>.md` | 2-3.5 | applying a framework formally (index: `frameworks/_index.md`); names: `pyramid-principle`, `80-20-rule`, `mece`, `first-principles`, `say-it-with-charts`, `mentat-thinking` |
| `reference/how-it-works.md` / `how-it-works.hu.md`, `reference/usage.md` / `usage.hu.md` | 9 / 5 | the USER asks how Mentat works, where it can run (several machines, a server, several sessions) or what it is usually used for |
| `reference/initialization-background.<l>.md` | 1 | a step of the initialization failed or you need its reasoning |
| `reference/manifest/*` | - | tool sources, downloaded by initialization step 1 into `.mentat/bin/`; read only to debug them |

Template index with the type-selection rules: `reference/templates/_index.md` (5). Read it only when unsure which type a thing is.

## Rules

- **Fetch failed = say it, then stop.** Tell the USER: "I tried to fetch `<URL>` and it returned `<error>`." Never invent a template or structure.
- **Offline first run:** if `reference/_index.md` is unreachable, create a minimal `AGENTS.md` and the brain skeleton from the brain prompt, skip templates and frameworks, tell the USER once, and do not retry silently.
- **Frameworks are soft-fetch:** you know them in outline; fetch the depth only for formal application or on request.
- The brain folder is `agy/` in Hungarian mode and `brain/` in English mode.
- **Versioning:** this file is pinned to tag `v0.5.0`. To upgrade, swap the tag in the base URL. Tags: `https://github.com/lipi4242/mentat/releases`.
