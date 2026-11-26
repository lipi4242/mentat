Mentat help · v1 (2026-11-13)

WHAT I CAN DO
[[The main feature list goes here. Until then: https://github.com/lipi4242/mentat/blob/main/reference/usage.md]]
You need no commands: talk to me as you would to a colleague.

START WITH THESE
1. /mentat status
   Expect: my role, the todo, the scheduler and the next step, in four lines.
   If it shows an error: python3 .mentat/bin/mentat_cli.py status (says what is missing or broken).
2. Say: "Note this: tomorrow at 10 I call Anna."
   Expect: I save it and tell you which note it went into.
   If I cannot save it: python3 .mentat/bin/mentat_cli.py status, the brain line should say "present".
3. Say: "Is there something for this already: every morning list what is due."
   Expect: from python3 .mentat/bin/mentat_brain.py where --find I tell you what exists and what to switch on.
   If it finds nothing: there is no such capability yet, and I ask whether we should build it.

COMMANDS
/mentat status   who I am, what is switched on, the next step
/mentat todo     switching on the todo and the backlog, step by step
/whoami          the status line's content (also in the desktop app)
/fleet:roster    my fleet mates, when I run in a fleet
Documentation: https://github.com/lipi4242/mentat/tree/main/reference

== todo
SWITCHING ON THE TODO AND THE BACKLOG (first locally, on your own computer)
You need: git, curl, python3, Node.js 22+ and the Mentat checkout (~/src/mentat, as in the admin README's quickstart).
1. Dependencies: cd ~/src/mentat/admin && npm ci --prefix worker && npm ci --prefix admin
2. Connect in one command: cd worker && npm run connect -- --repo <this agent's folder> --url http://localhost:8787 --local --plugins todo
   Expect: a short block at the end (done / next / sign in). The admin keeps running as a service (macOS: launchd, Linux: systemd), also after you close the terminal.
   If it shows an error: the same with --check only lists what is missing; npm run status shows the service.
3. Check, in the agent's folder: mentat-todo me
   Expect: the agent's own todo handle (@name), with no --as.
4. Sign in once: npm run login-link (in the worker folder), open the link, and create your own handle on the participants page (Résztvevők).
5. /mentat status
   Expect: Todo: on (@name).
Later, to reach it from your phone or several computers: the same command with --remote --url https://<your admin> for a Cloudflare instance.
