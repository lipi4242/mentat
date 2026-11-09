# Using your Mentat

What a normal week with it looks like, where it can run, and the situations it is usually set up for. For the background (how the memory is organised), see [how-it-works.md](how-it-works.md).

## A normal day

Open Claude Code in the agent's folder and talk to it like a colleague who has been around for a while. You do not need commands. What people say most, by area:

- Memory and knowledge. "Note this: ...", or a long, messy message about what is on your mind. It saves the text word for word first, then files the people, todos, decisions and cases it finds. "We decided to ..." goes on its own shelf: if you later ask for something that contradicts it, it reminds you of the date and the reason, and lets you overrule it.
- Proactivity and scheduling. "What's due this week?" It answers from its notes, with the time and the people involved, and says which note each line comes from. "Remind me every month on the 10th to pay X" becomes a case; with the engine installed, the reminder arrives in the morning summary without you asking.
- Work and projects. "Let's build a small tool for ..." gets a place under `projects/`. A large request that is not fully specified goes through a set procedure: questions first, acceptance criteria, then the work.
- Connection to the outside world. "Invite the three of them to Thursday's meeting", "share the sheet with ...": through Google's own library, with a hidden guest list, checked against the agreed recipients.
- Safety and control. "Send the list of open items to the three of them." For a list, an export or a message to several people, it first writes down what you agreed (which rows, what stays out, who receives it, for which dates) and asks for your yes. Before sending, it checks the output against that agreement; if something does not match, it does not go out. It also asks before steps that are hard to undo: reading outside its folder, deleting outside it, force-pushing, writing straight into a database, sending your e-mail address to a service that is not yours. When nobody is there to ask (a scheduled run on a server), it does not do them.
- Operation and flexibility. "Is there already something for this?" Before building anything new, it looks at what the suite and your own projects can already do (`where --find`). "What is installed here?" `status` answers from `mentat.json`.

## Where it can run

The brain is a private git repository, so the same agent can live in more than one place. The setups we use and support:

| Setup | What you need | Good for |
|---|---|---|
| Your own computer | Claude Code (desktop app or terminal); on Windows also Git for Windows | Getting started. Works for non-technical users; the install takes a few minutes. |
| Several computers | The same private repo (for example on GitHub) cloned on each; the agent saves with git, and you pull before you start on the other machine | One person with a laptop and a desktop, or one agent helping on several family computers. |
| A server, always on | A Linux server with the [fleet](https://github.com/lipi4242/mentat/tree/v0.6.1/fleet) runner; Telegram for talking to it | An agent that works on a schedule and answers you on your phone, also when your computer is off. |
| Several sessions on one computer | Open more than one Claude Code session in the same folder; optionally a role per session (`MENTAT_ROLE=<role> claude`) | Working on two things at once. The sessions share one long-term memory. |
| From your phone or the web | Run `/rc` (remote control) in a session | Continuing a session started on your computer from elsewhere. |

One rule across setups: the engine's schedule runs in one place only. If two machines tick for the same agent, reminders go out twice. The fleet runner keeps it on the server; on a personal computer, `setup --doctor` shows what is installed.

## Typical situations

- Helping an older parent with their computer. The agent is set up on their machine, in their language, knows the people and accounts that matter to them, and asks before anything risky. Someone else in the family can reach the same agent from another machine.
- An old computer turned into a small server. With the fleet runner it keeps the agent running day and night, and you talk to it over Telegram.
- A one-person business. Cases for recurring obligations (invoices, renewals, deadlines in a spreadsheet), a morning summary, and an agent that can take over the business's existing repos and notes through the [onboarding guide](bekotes/BEKOTES.en.md).
- A small web page or tool for a club, a family or a team. The agent builds it, puts it online on Cloudflare behind a sign-in only the people you name can pass, and checks it the way those people will see it. It goes live only when you say yes ([publish-web.md](publish-web.md)).
- A shared calendar or mailing that must not leak addresses. Invitations and group mails go out with a hidden guest list, through Google's own library, checked against the agreed recipient list ([google.md](google.md)).

## Moving to a new version

Each release has a [CHANGELOG](../CHANGELOG.md) entry with a "You need to" part when anything is required from you, and a [capability log](../CAPABILITY-LOG.md) that says which capability changed and how. Give your agent the link to the new release's CHANGELOG and ask it to do the "You need to" steps. Nothing changes for an installed agent until you do this: installs are pinned to a release tag.
