# How Mentat works

The background behind the [README](../README.md): how the memory is organised, the personality, the helpers it can call, and the optional parts around it. You do not need any of this to start.

## How the memory works

This is the part worth understanding before you install anything, because everything else follows
from it.

### Context is short-term memory

The context window is your assistant's **working memory**. It is small, it is temporary, and it is
the single thing most worth optimising: you want exactly what you're working on in there, and
nothing else.

That's why you don't want one giant assistant that knows everything at once. You want the right
things loaded at the right moment.

### The repo is the DNA

Everything in the repo at file level — `AGENTS.md`, the conventions, the frameworks — is the
assistant's **DNA**. It's the base personality, and it's identical no matter how many sessions you
open.

Start three agents in the same repo and all three boot with the same personality. But their
working memory fills with different things, so they become good at different things: one is deep
in your finances, one is drafting a proposal, one is fixing a bug. Same DNA, different short-term
memory.

### Long-term memory is shared

Here's the important bit: those three agents **share one long-term memory**. When one of them
learns something, all of them have it. What one figures out about a client on Tuesday, another can
use on Friday without being told.

So the brain compounds. It doesn't fragment across sessions.

### The brain stores chunks

Human memory doesn't hold everything at once either. Things sit dormant in **chunks** until
something makes them relevant, and then the whole chunk comes back — a name, a smell, a film you
haven't thought about in twenty years.

The brain here is organised the same way. It's a folder, and each **entity type** gets a folder
inside it. Individual **entities** are the files:

| Entity type | What lives in it |
|---|---|
| `brain-dump` | Your raw thought-streams — saved verbatim, before any processing |
| `exploration` | A topic you keep circling back to, not yet a decision |
| `person` | Someone whose details keep mattering |
| `todo` | One concrete, finishable thing |
| `decision` | Something you settled — kept on its own shelf, so drifting from it gets caught |
| `case` | Something to get done and keep track of — once, or every month (a bill due on the 10th) |
| `specification` | A change with several moving parts |
| `connector` | How to reach Gmail, your calendar, your todo app |
| `procedure` | A recurring job, written down once |
| `subagent` | **A persona you can call again** — see below |

**Entity types are the shelves; entities are what sits on them.** And new types appear when reality
demands them: if you keep talking about something the brain has no shelf for, the assistant
proposes a new one. It won't invent shelves you never needed.

### It can hire specialists

Some work is better done by someone who is not you. A **subagent** is a
reusable persona: an expert, someone who knows the business, an accountable
owner, or a customer looking at your work from outside.

They are not prompts. Each one keeps its own brain:

| File | What it holds |
|---|---|
| `persona.md` | who they are, what they must know, **what they decide** |
| `history.md` | your joint work: what they helped with, what came of it |
| `personal-history.md` | their own past — professional grounding, or a customer journey |
| `decisions/` | decision records that shaped who they are |

Two things follow. **They persist** — a persona you built once is an asset, not
a throwaway, and it gets better each time you use it. And **they can be given
authority**: a domain where they decide, rather than merely advise. That is what
makes calling one worth more than asking you.

A customer persona with a journey — *this is the email they got, this is how
they replied* — reviews your next draft as **the next thing that person
receives**, not as an isolated artifact. That is a different review than a
generic one.

### It knows how to run a big piece of work

When a request is **large in scope and not fully specified**, your colleague
does not start guessing. It runs a procedure: it asks which development mode you
want, how much you want to shape the specification, and who should answer the
design questions — you, itself, or an outside expert model.

From there the work is delegated with **full acceptance criteria**, an
**evidence form** (every criterion needs a test, and the test must be shown able
to fail), and an **isolated worktree** so a green measurement describes the
repo, not one machine. Reviewer personas check the result over several rounds,
and their feedback is recorded so the whole path stays auditable.

**Expert personas also act as a question filter**: a developer thinks like a
developer and will ask about things a designer knows better. Those get decided
by the expert, not forwarded to you — so you get the few questions only you can
answer.

### It updates itself

You don't file things by hand. When you talk to your assistant, it scans what you said for
entities — a person, a task, a decision, an open question — and creates or updates the files in the
same breath. If you send it a long, messy thought-stream, it saves the raw text *first*, verbatim,
and only then pulls the structure out of it.

One entity type behaves differently: a **decision**. Once you've made one, drifting away from it
later doesn't pass in silence. The assistant stops you — *"you decided this on the 6th, and you
said it mattered. Overwrite it?"* You can always override. You just can't drift without noticing.

### How to talk to it

**Reactive mode** is the normal one: you open a session and work together. Talk to it the way
you'd brief a sharp new colleague — context first, then what you want. Don't compress. Long,
rambling messages are *better* than tidy ones, because the brain saves them whole and mines them
afterwards.

**Proactive mode** is when it acts without you, on a schedule. That needs
[the engine](https://github.com/lipi4242/mentat/tree/v0.6.1/engine) (see below). Even then you're not
locked out: you can open a session alongside and get things done together while it keeps ticking
in the background.

## The personality

Your assistant behaves like an MBB consultant (McKinsey / BCG / Bain) crossed with a Mentat from
Dune: disciplined, top-down, pattern-driven, allergic to ceremony.

It ships with the frameworks that implies — Pyramid Principle, 80/20, MECE, First Principles, Say
It With Charts — and it uses them. Ask a vague question and you get one clarifying question back,
not five paragraphs of hedging.

## Remote control

Run `/rc` in the Claude Code session. It reports back as remote-controlled, and from then on you
can reach that same session from the Claude desktop app, from the web, and from your phone.

It's worth doing early. An assistant you can only talk to from one terminal window is an assistant
you'll forget to use.

## Running on another model

By default your colleague runs on Claude. It can move itself to a measured open
model via OpenRouter — and back — when you ask ("switch to DeepSeek", "back to
Claude"). It uses `skills/model`: one command, a live probe that proves the answer
comes from the new model, rollback if it does not. Only this agent changes; the
shared Claude login and every other agent on the machine stay as they are.

Measured today (acceptance suite, 3 = as expected): **DeepSeek V4.1 Flash 3.62**
against Claude Opus 5.5 3.69, at about a fifteenth of the cost or less. You need an
OpenRouter key with a credit limit; the colleague tells you how to hand it over
without pasting it into the chat.

## Adding a pulse: the engine

Everything above gives your assistant a mind. It doesn't give it a pulse.

Out of the box it's **reactive**: sharp when you talk to it, inert when you don't. It won't notice
the invoice that arrived this morning, because nothing woke it up to look.

[**The engine**](https://github.com/lipi4242/mentat/tree/v0.6.1/engine) is the other half — a
deterministic tick that fires on a schedule and asks *"is anything worth doing right now?"*, then
consults the brain you built here to answer.

| | What it gives your assistant | Without it |
|---|---|---|
| **the brain** | memory, structure, personality | an assistant that forgets you every session |
| **the engine** | a heartbeat — proactive mode | an assistant that only exists while you're typing |

Start here. Add the engine when you're tired of being the one who starts every conversation — the
same way you'd hand a new colleague their own diary once they'd learned the job.

## A back office: the admin

The admin is Mentat's todo + backlog: an optional screen and database next to the brain, on your
computer or your own Cloudflare account ([admin/README.md](../admin/README.md)). Todos, cases and
backlog items live there, and you see whose ball each one is. One agent can hand a backlog item to
another as its PM, the other takes it as the developer, and the report comes back with evidence for
every acceptance criterion (the `backlog` skill). Without the admin the brain keeps cases as
Markdown notes.

## Roles

Several agents can share one brain and divide the work: an assistant, a PM, a developer, a release agent and others, each with its own responsibility, all knowing about each other. The [role map](roles.md) describes each role, how to judge it, and how it works on your own machine and on a server.
