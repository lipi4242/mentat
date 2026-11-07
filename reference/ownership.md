# Ownership and the publishing boundary

[Magyarul](ownership.hu.md)

The brain repo holds two kinds of text. Keeping them apart is what lets the
product be upgraded without touching the USER's memory, and what keeps that
memory from leaking.

## Managed vs personal

| | **Managed** (the product's) | **Personal** (the USER's) |
|---|---|---|
| What | the rule blocks of `AGENTS.md` between `mentat:managed` markers; skills copied from `skills/` (e.g. `.claude/skills/<name>/SKILL.md`); `.mentat/bin/` | everything else: `brain/` (or `agy/`) — entities, brain dumps, people, decisions, cases, connectors, procedures, subagents and their histories; `projects/`; the unmarked sections of `AGENTS.md` (identity, operating posture, anything the USER added) |
| Who writes it | an upgrade (`mentat upgrade`), replacing a block **as a whole** | the agent, with the USER |
| Templates | fetched on demand from the tagged manual, never copied — nothing to own | — |

A managed block in `AGENTS.md`:

```markdown
<!-- mentat:managed:start entities -->
5. **Entity processing rule** — …
<!-- mentat:managed:end entities -->
```

Rules:

1. **Do not edit inside a managed block.** If the USER wants a product rule
   changed, write the change in a personal section ("Our rules" or the
   matching personal section) and say that it overrides the block. Personal
   text wins over managed text when they disagree.
2. **An upgrade only writes between markers.** It replaces the content of a
   block with the same id, adds blocks that are new, and leaves text outside
   markers byte-for-byte as it was. A block whose markers are missing or
   unbalanced is not touched; the upgrade reports it instead.
3. **Ids are stable.** `reference-manual`, `layers`, `brain-dumps`,
   `entities`, `files`, `frameworks`, `claims`, `large-work`. A renamed block is a new
   block plus a removed one.
4. **Nothing personal is ever written by the product** — not on install, not
   on upgrade. The only exceptions are the files the USER's agent creates
   with the USER during installation.

## Publishing boundary

The brain repo is **private memory**. It contains the USER's thoughts, other
people's details and how the USER's tools are wired.

- Never add a public remote to it, never make it public, never push it to a
  shared organisation without the USER's explicit decision for that remote.
- `.env*` and `.mentat/` are always git-ignored.
- If something should be published — a project, a procedure, a template the
  USER wrote — **copy that one thing into a separate repo** and publish that.
  Before copying, check it for names, e-mail addresses, IP addresses, internal
  paths and tokens, and show the USER the file list.
- A project that has its own public repo lives in `projects/<name>/` as its
  own git repo (or submodule); it never contains `brain/`.

This is the whole policy. There is no allowlist file to keep in sync: the
default for everything in the brain repo is *private*, and publishing is a
deliberate copy.
