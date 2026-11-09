# Skills

Runnable procedures your colleague can invoke by name. Unlike reference
documents (which it *reads*), a skill is something it **runs**, start to finish,
in a defined order.

| Skill | Invoke when | Composed of |
|---|---|---|
| [`develop`](develop/SKILL.en.md) · [HU](develop/SKILL.hu.md) | The USER asks for something **large in scope and not fully specified** | calls `subagent` as a subskill |
| [`subagent`](subagent/SKILL.en.md) · [HU](subagent/SKILL.hu.md) | You need a persona — to create one, call one, or log a session with one | standalone |
| [`status`](status/SKILL.en.md) · [HU](status/SKILL.hu.md) | Someone asks what is installed, or building blocks that should work together do not | `reference/mentat-json.md` |
| [`bekotes`](../reference/bekotes/BEKOTES.en.md) · [HU](../reference/bekotes/BEKOTES.hu.md) | The USER asks this agent to take over a business (repos, old agent memories, Linear) | `status`, the role guard, `reference/mentat-json.md` |
| [`backlog`](backlog/SKILL.en.md) · [HU](backlog/SKILL.hu.md) | You hand work to someone or take it, decide whether finished work is accepted, track a long process as a case, or the plan has `todo_labda` | the Admin's todo + backlog, `backlog/ac-form.en.md` |
| [`model`](model/SKILL.en.md) · [HU](model/SKILL.hu.md) | The USER wants this agent on another model (a measured open model via OpenRouter) or back on Claude | `reference/manifest/mentat_model.py` |
| [`bug-report`](bug-report/SKILL.en.md) · [HU](bug-report/SKILL.hu.md) | Mentat itself fails in a way the docs do not explain, or the USER says "report this bug" | `.mentat/bin/mentat_bugreport.py` (redaction, duplicate search, the USER's yes before posting) |

## Installing

If your environment supports skill files (e.g. `.claude/skills/<name>/SKILL.md`),
copy the matching file there. If it does not, that is fine: **fetch and follow
the skill document directly** — it is written to be executable by reading.

## Why these are skills and not just documents

A reference document tells you how something works. A skill tells you **what to
do next, in order, and what not to skip**. The development process has steps
that are easy to skip under time pressure — asking before starting, filling the
evidence form, proving a test can fail. Writing them as a skill makes the order
part of the instruction rather than a matter of memory.
