# Templates

Hard-fetch — before creating a new artifact in the USER's brain folder (`brain/` in EN, `agy/` in HU) or in `projects/`, you MUST fetch the matching template (`<type>.<lang>.md`).

| Type | When to create | EN | HU |
|---|---|---|---|
| brain-dump | The USER sends a long message (≥ ~200 words) that's a thought stream | [en](brain-dump.en.md) | [hu](brain-dump.hu.md) |
| exploration | A new tematic topic you'll discuss several times before it becomes a project | [en](exploration.en.md) | [hu](exploration.hu.md) |
| person | Someone the USER mentions enough that recurring details matter | [en](person.en.md) | [hu](person.hu.md) |
| todo | A specific task with a doable shape | [en](todo.en.md) | [hu](todo.hu.md) |
| **decision** | The USER settles something later work must follow — recorded the moment it is made, so drift from it can be caught | [en](decision.en.md) | [hu](decision.hu.md) |
| **case** | Something to get done and track over time — once or recurring (a bill due every 10th, a claim waiting on someone) | [en](case.en.md) | [hu](case.hu.md) |
| specification | An upgrade or build with nested todos under it | [en](specification.en.md) | [hu](specification.hu.md) |
| connector | A capability config to talk to an external tool (Gmail, TickTick, etc.) | [en](connector.en.md) | [hu](connector.hu.md) |
| procedure | A playbook for a recurring task | [en](procedure.en.md) | [hu](procedure.hu.md) |
| project | A sustained piece of work with its own folder, optionally its own git repo | [en](project.en.md) | [hu](project.hu.md) |
| **subagent** | A reusable persona you will call again — expert, business-aware, accountable, or customer voice | [en](subagent.en.md) | [hu](subagent.hu.md) |
| **subagent-history** | The log of working with a persona; written after **every** use | [en](subagent-history.en.md) | [hu](subagent-history.hu.md) |
| **subagent-personal-history** | The persona's own past — professional grounding, or a customer journey | [en](subagent-personal-history.en.md) | [hu](subagent-personal-history.hu.md) |
| **subagent-decision** | An ADR kept at the persona, not only in the project | [en](subagent-decision.en.md) | [hu](subagent-decision.hu.md) |
| **acceptance-form** | Evidence that delegated development work is done (step 4 of the development process) | [en](acceptance-form.en.md) | [hu](acceptance-form.hu.md) |

## Decision rules

### When to create which artifact

| If the USER... | Create as... |
|---|---|
| brings up a topic they'll discuss multiple times before deciding | `exploration` |
| commits to building something specific with multiple subtasks | `specification` |
| asks for help with an external tool (Gmail, TickTick, Asana, Strava, etc.) | `connector` (and likely `procedure` later) |
| wants a recurring task done a specific way | `procedure` |
| mentions a sustained piece of work that needs its own folder/repo | `project` |
| sends a long message (~200+ words) that's a thought stream | `brain-dump` (raw, then process) |
| references a specific person twice or more | `person` |
| names a concrete task with a doable shape | `todo` |
| settles something that later work should follow (even mid-todo or in a side remark) | `decision` — and link it from the todo, don't bury it there |
| has something with a done state, a next step and a date — a deadline, a recurring payment, a matter waiting on someone | `case` |

### Transitions between types

- **`exploration` → `specification`**: when the USER says "let's build it", commits a deadline, or stops adding open threads.
- **`specification` → `connector` + `procedure`**: when implementation requires external-tool access. Connector captures the auth/capability; procedure captures the workflow that uses it.
- **`specification` → `project`**: when scope warrants its own folder, possibly its own git repo.
- **`procedure` references `connector`**: every procedure that uses an external tool should link the connector by path. Don't duplicate connector details in the procedure file.

### Boundary clarifications

- **Connector vs procedure**: a connector is a static *capability* description (what API, where auth lives, what actions are possible). A procedure is a *workflow* (when to run, what steps, what output, edge cases). One connector can power many procedures.
- **Decision vs todo**: a todo is something to *do*; a decision is a rule the USER chose that later work must *respect*. When a todo carries out a decision, the decision gets its own file in `decisions/` and the todo links to it.
- **Case vs todo vs decision**: a todo is one step; a case is a matter with a done state (or recurring occurrences), a next step and a date — it can contain todos; a decision is a rule to respect. A todo that has rolled for weeks and depends on someone else becomes a case.
- **Exploration vs specification**: an exploration is for thinking; a specification is for building. The distinguishing test is commitment — has the USER said yes to building this?
