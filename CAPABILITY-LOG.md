# Capability log

Generated from `capability-log.json` - do not edit by hand.

## 0.5.1 (not released yet)

### Proactivity and scheduling

- mentat-todo: the backlog command for every agent on a server. Every agent on a server gets the backlog command without a copy of the engine; the agent's name comes from its unit. (Extended: `engine.todo`)

### Operation and flexibility

- One command to upgrade a server. fleet box-upgrade --to vX.Y.Z plans, snapshots, upgrades a canary agent first, skips busy agents, checks the result and rolls back on its own. (Extended: `fleet`)
- Fewer false alarms on a server. Install no longer fails falsely on restart, a bridge that is behind is a to-do instead of an error, and the out-of-memory helper ships in the repository. (Improved: `fleet`)

## 0.5.0 (not released yet)

### Proactivity and scheduling

- Todo + backlog: agents hand work to each other. Todos, cases and backlog items live in one store in the Admin. A PM agent issues an item with measurable acceptance criteria, the developer takes it and reports with evidence for every criterion, and the PM accepts or rejects per criterion. Every agent sees whose ball each item is. (Extended: `engine.todo`)

### Work and projects

- Todo + backlog: agents hand work to each other. Todos, cases and backlog items live in one store in the Admin. A PM agent issues an item with measurable acceptance criteria, the developer takes it and reports with evidence for every criterion, and the PM accepts or rejects per criterion. Every agent sees whose ball each item is. (New: `backlog`)

### Operation and flexibility

- One repository, one install. The brain, the engine, the fleet and the admin now live in one repository. One clone at the release tag gives the engine and the fleet, and the fleet plugin installs from the same place. (Improved: `mentat.init`, `fleet`)

## 0.4.0 (not released yet)

### Proactivity and scheduling

- Recurring duties are repeating todos. The agent's due todos from the Mentat Admin todo list arrive on every tick, and a todo is closed only after the work is done. Requires the Mentat Admin todo plugin, which is not public yet. (New: `engine.todo`)
- Outward hold. While a hold is set, every tick is a dry run and nothing is sent, for at most 24 hours. (Improved: `engine.core`)
- Packs move to the 0.4 engine. Bundled packs declare >=0.4,<0.5; a pack of your own that stops at 0.4 must widen its range. (Extended: `engine.core`)

### Safety and control

- The identity gate asks only when your address could really leak. Only the part of a command that goes out on the network counts; your own GitHub account counts as yours once GitHub confirms the sign-in. (Improved: `guard`)
- Only you decide what counts as yours. A file the agent can edit, an ssh target or a private-network address no longer makes a place yours; only the list you approved and localhost do. (Improved: `guard`)

## 0.3.1 (not released yet)

### Memory and knowledge

- Taking over a business reads less. The inventory no longer downloads excluded files, whole folders can be excluded, and the takeover is offered from the first session. (Improved: `takeover`)
- "What is due" says when and who. The due list shows the time and the people a note refers to. (Improved: `brain.due`)
- Fewer silent assumptions. A changed field list is read back again, and a case's notes and conditions are read before its date or state is changed. (Improved: `brain.new`)
- An existing AGENTS.md is kept. Installed into a folder that already has an AGENTS.md, Mentat keeps your text as it is and adds its own sections at the end. (Improved: `takeover`)

### Proactivity and scheduling

- The status and the engine line tell the truth. status no longer points to the unreleased admin, and the intake installs the engine with its cases pack. (Improved: `engine.cases`)
- Deadlines straight from a table. A CSV list of deadlines feeds the morning summary and reminders without any code of your own. (New: `engine.csv_deadlines`; Extended: `engine.cases`)
- setup --doctor. Compares the installed timers with what setup would write and shows a hand edit line by line. (Extended: `engine.schedule`)
- Faster engine install. setup can record the settings without a timer, a handwritten due: date is understood, and the install clones the release tag. (Improved: `engine.schedule`, `engine.cases`)
- The schedule remembers what each output must contain. setup --expect stores what every scheduled message must hold, such as the people to call, and asks for it when it is missing; the brain's checks read it from there. (Extended: `engine.schedule`)

### Work and projects

- "Next week" is asked, not guessed. A time phrase becomes dates in your time zone; when it can mean two things, the agent asks. (New: `dates`)

### Connection to the outside world

- Google through one tool. Invitations, mail, sharing and sheets go through one tool with safe defaults, checked against your agreement first. (New: `google.auth`, `google.calendar`, `google.gmail`, `google.drive`, `google.sheets`)
- Tools for publishing a page. Check the page the way you see it, go live only on your yes, put Cloudflare Access in front and create the token one step at a time. (New: `web.check`, `web.deploy`, `cf.token`; Improved: `web.publish`)
- Local pages that never stall the conversation. A page, preview or dev server on your computer starts in the background; the agent checks it opens, gives you the address, and it stops by itself after an hour. (New: `web.local`)
- Keys go into a hidden form, not the chat. When a service needs a key, you paste it into a small local form and it is saved in a private project file. A key already pasted into the chat is stored at once, with a suggestion to make a new one. (Extended: `web.local`)
- Going live checks the Cloudflare token first. Before a deploy the agent checks that the token has every permission this project needs and names what is missing and where to fix it; afterwards it checks that the page asks for sign-in. A Cloudflare API gateway set in the environment works too. (Improved: `web.publish`)

### Safety and control

- The guard works from the first session. Reading outside the working folder and dangerous steps are asked from you, and denied when nobody is there to ask; if the guard itself cannot run, the call is blocked. (New: `guard`)
- Direct database writes need you. Writing to a database directly waits for your yes, and is denied when nobody is there to ask. (Extended: `guard`)
- Your address does not go to third parties. A network call that carries your e-mail to a place that is not yours is asked from you, or denied headless. (Extended: `guard`)
- The guard holds the capability tree. New code, services, schedules or packages need a fresh look at what already exists first. (Extended: `guard`)
- What you agreed is kept in a file and checked before it goes out. Lists, exports and group messages are checked against the agreement you approved; red means it does not go out. (New: `contract`, `accept`)
- Tools for publishing a page. Check the page the way you see it, go live only on your yes, put Cloudflare Access in front and create the token one step at a time. (New: `cf.access`)
- Fewer silent assumptions. A changed field list is read back again, and a case's notes and conditions are read before its date or state is changed. (Improved: `contract`)
- Nothing final goes out unseen. Before something is sent, recorded or created elsewhere, the agent reads it back in full with every required field filled. It goes out after you reply with the short code it shows, and the agent then checks what arrived. (New: `final`)
- The agent does the technical steps itself. It does not ask you to run commands or edit files it can handle; you only get what needs a person, such as signing in, paying or typing a key into the form. Telegram agents work the same way. (Improved: `guard`)
- Scheduled messages are checked before they are sent. A message tied to an agreement is held back when it does not match it. (Extended: `accept`)
- The identity gate as a fleet plugin hook. Every agent on a box gets the same check before your e-mail leaves for a third party. (Extended: `guard`)

### Operation and flexibility

- Install in one call. The brain, the guard, mentat.json, the git setup and the engine are installed by one command, which ends with a self-test. (New: `mentat.init`)
- Install with three lines. A three-line prompt in Claude Desktop or Claude Code points the agent at INSTALL.md, which says each step before it is done; a missing git or Python is installed after your yes. (Extended: `mentat.init`)
- The install checks what it downloaded before it runs it. release.json lists a hash for every downloaded file, and the install stops on a partial, mixed or changed download. (Improved: `mentat.init`)
- Windows-aware preflight. On Windows the install stops early, with the one-line fix, when Git Bash or a working python3 is missing. (Improved: `mentat.init`)
- The install says what it found. It lists what was already in the folder and what went into the first commit, and leaves your own uncommitted changes alone. (Extended: `mentat.init`)
- The guard holds the capability tree. New code, services, schedules or packages need a fresh look at what already exists first. (Extended: `brain.where`)
- What already exists, before you build. where --find searches what the suite and your own setup can already do; --decide records the choice; --map draws the tree. (Extended: `brain.where`)
- The capability tree as a reference, and for the fleet. where --map --html shows what you get and what the agent can do on one friendly page; where --export shares a filtered view with the other agents of a fleet. (Extended: `brain.where`)
- The capability tree keeps itself current. Real checks with an expiry show a broken capability as degraded, and the day's first look says what changed. (Improved: `brain.where`)
- The model switch says what leaves. Before moving to another model it tells you that everything it reads goes to that provider, and asks for the privacy setting. (Improved: `mentat.model`)
- The status and the engine line tell the truth. status no longer points to the unreleased admin, and the intake installs the engine with its cases pack. (Improved: `mentat.status`)
- A download that does not match the release is not installed. The install tries once more, then stops and says so in plain words; nothing is left half installed. A network error is reported as one, with a retry. (Improved: `mentat.init`)
- Missing parts are named, not replaced. After an install that stopped, the agent lists which parts of Mentat are there and which are missing, and offers to install the missing one instead of building a substitute. (Improved: `mentat.init`)
- "Done" means checked where you use it. Before calling work done, the agent checks the address you got and that a private page asks for sign-in, the file, or the last scheduled run and its promised content. When it could check only on its own machine, it says so. (New: `brain.done`)
- Unsaved work and stray keys are mentioned. The same check names unsaved changes, pages still running, and keys found in files that git keeps, so you hear about them. (Extended: `brain.done`)
- A new session starts with your schedule's state. When the last scheduled run did not happen, failed, or left out what it promised, the agent tells you first. (Extended: `brain.done`)
- The identity gate as a fleet plugin hook. Every agent on a box gets the same check before your e-mail leaves for a third party. (Extended: `fleet`)
- doctor checks every agent's guard. It shows red when an agent's guard or Claude Code is not up to date. (Improved: `fleet`)
- New agents come up cleanly. Runbooks next to the registry are found, and the session id is recorded for new and older agents alike. (Improved: `fleet`)
- Safer defaults on the server. Fewer elevated rights, and no menu questions for an unattended agent. (Improved: `fleet`)
- The capability tree across the fleet. fleet capabilities collects what each agent on a box can do, so an agent can find what a neighbour already has. (Extended: `brain.where`, `fleet`)

