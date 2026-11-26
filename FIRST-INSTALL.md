# Installing Mentat for the first time

> 🇭🇺 Magyarul: [FIRST-INSTALL.hu.md](FIRST-INSTALL.hu.md)

This page sets up a new assistant in an empty folder. Already have one (a Mentat brain of any age)? Use [UPGRADE.md](UPGRADE.md). A whole fleet of agents: [UPGRADE-ALL.md](UPGRADE-ALL.md).

This page is read by two readers: you, and the Claude that does the installing. The first half is
for you. The second half is the exact list of steps Claude follows, so you can see what it will
do before it does it.

## For you

**What you need:** Claude Desktop (with its Code tab) or Claude Code, on a paid Claude plan.
Nothing else. If your computer is missing git or Python, Claude tells you and installs them
after you say yes.

**Our strong recommendation: make your first assistant your personal assistant & fleet
manager.** That is one agent that, for every new project, idea or exploration, is your developer,
product manager and release manager in one, using its own brain for all of them, and that also
looks after your other agents. Why:

- **one brain for all your projects:** what it learns in one, it knows in the next;
- **fast development:** no hand-over between agents for a new idea; it starts the same day;
- **it keeps the fleet together:** when you add more agents later, one of them knows them all,
  upgrades them ([UPGRADE-ALL.md](UPGRADE-ALL.md)) and notices when one goes quiet.

The role, its duties and its self-image (Szerep önkép) are defined in the role map,
`reference/roles.md`. You can choose another role; Claude will ask.

**What to do:**

1. Open Claude Desktop, go to the **Code** tab, and choose a new, empty folder (for example
   `Assistant`). In Claude Code: make the folder, open a terminal in it, type `claude`.
2. Paste this:

```
Install the Mentat assistant for me in this folder.
The steps are here: https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/FIRST-INSTALL.md
Tell me each step before you do it.
```

Claude then asks a few questions (your name, what to call it), sets up the folder, and has a
short getting-to-know-you chat. At the end a second, brand-new Claude session checks that it
remembers both names. It takes a few minutes.

**What runs on your computer:** Claude downloads Mentat's own tools from this GitHub repository
(this release) into the folder's `.mentat/bin/`, checks each file against the release's list of
fingerprints (sha256), and only then runs them.

**What it touches:** only this folder (if you ask for the engine, this release of Mentat is
cloned once into your home folder, under `src/mentat`, and the engine is copied from there). Two exceptions, each asked first: installing git or
Python with your system's own installer, and on Windows a restart of Claude after that.
It never asks for a password, key or code in the chat.

**Later, if you want it: todos + backlog (Mentat Admin).** An optional web app where you and
your agents keep todos, longer-running cases and a backlog with acceptance criteria, instead of
a paid tracker. It runs on your computer or on your own Cloudflare account. Start with the
[Admin quickstart](admin/README.md#quickstart-look-at-it-on-your-machine-about-a-minute-and-a-half),
then [connect your agent](admin/docs/plugins/todo/INSTALL.md). On your own computer,
`npm run connect -- --local` (in `admin/worker`) keeps it running after the terminal is closed:
a background service on Linux and macOS. Windows has no such service: there the Admin runs only
while its terminal is open. Nothing of it is installed unless you ask.

## For Claude: the steps

### Rules for the whole install

Fetch `https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/entry-rules.md` and follow it for the whole install, before Step 1; where a
step and those rules disagree, the rules win. For this page they name two outside places: the
system installers of Step 1 (winget, `xcode-select`, apt/dnf), and only for git and Python; and,
when the USER wants the engine, the one Mentat clone at this tag.

### Before Step 1 — the first assistant's role

When this is the USER's first Mentat assistant, recommend very clearly that it be the
**personal assistant & fleet manager** (the reasons are in "For you": one brain for all projects,
fast development, it keeps the fleet together); its definition is the role map,
`reference/roles.md` at this tag: read it from there, do not restate it. Ask once, together with the questions of Step 2; the USER may choose
another role. Record the choice in the intro chat (Step 2, 3) as the agent's role.

### Step 1 — Check git and Python

Run `git --version` and `python3 --version`. On Windows, a `python3` that prints "Python was not
found" or opens the Microsoft Store counts as missing. If both answer (Python 3.9 or newer), go to
Step 2.

If something is missing, tell the USER what is missing, the one command, and that the command
accepts the package's license for them; run it after their yes. On Windows, name the Python
package: `9NQ7512CXL7T` is the Python Install Manager from the Microsoft Store.

| System | git | Python |
|---|---|---|
| Windows (PowerShell) | `winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements` | `winget install 9NQ7512CXL7T -e --accept-package-agreements --accept-source-agreements` |
| macOS | `xcode-select --install` (a window opens: Install; it brings python3 too) | same |
| Linux | the USER runs `sudo apt install -y git python3` (Fedora: `dnf`) in a terminal | same |

- **Windows:** Windows may ask "Do you want to allow this app to make changes?". That is the
  installer: the USER clicks Yes. Then Claude has to be restarted to find Git Bash: ask the USER to
  close Claude completely, open it again in the same folder, and paste the same three lines.
  You start over at Step 1, which now passes. The first `python3 --version` after that may take
  a minute: it downloads the Python runtime.
- **Windows without winget:** give the USER the official pages instead,
  `https://git-scm.com/download/win` and `https://www.python.org/downloads/windows/`.
- **macOS:** wait until the window says the install is done, then check again.

### Step 2 — Set up the brain

Fetch `https://raw.githubusercontent.com/lipi4242/mentat/v0.7.0/reference/initialization.md`
(Hungarian USER: `initialization.hu.md`) and follow it to the end. In short, it:

1. asks the few real questions in one message (names, form of address, whether they want
   reminders from the engine);
2. downloads the tools of this release into `.mentat/bin/` and runs `mentat_init.py`. It first
   checks every downloaded file against the sha256 list in `release.json` and stops on a
   mismatch; then the mechanical checks: git, Git Bash on Windows, `python3` where Claude Code's hooks run it, the
   Claude Code version, disk space. When it stops with `MENTAT-INIT HIBA: …`, that one thing is
   the task: tell the USER, fix it (with their yes if it installs something), run it again — except
   when the download does not match the release: then do only what that message says (it is not
   yours or the USER's to fix or waive, and nothing replaces Mentat's parts);
3. has the short intro chat, saves the first commit, and offers remote control (`/rc`).

Nothing is pushed anywhere and no remote is added.

### What not to offer

- **The engine on a desktop computer** installs without a background timer: it works when the
  USER asks ("what is due?"), and each new Claude session catches up once. On macOS and Linux the
  USER can add the schedule later (`python3 -m anytime_engine.setup --tz <tz> --install`); then it
  runs every hour while the computer is awake. Windows has no background schedule. Say so when
  they choose the engine.
- **The Fleet** (always-on, Telegram) is for a Linux server, not for this computer. Do not offer
  it here. If the USER asks: `https://github.com/lipi4242/mentat/tree/v0.7.0/fleet`.

