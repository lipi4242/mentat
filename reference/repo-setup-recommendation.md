# Repository setup: the recommendation step

A section to include in an install guide. Background and diagram: `reference/repo-setup.md`.

If the owner has or will have a codebase, or plans more than one agent, ask these two questions at
the end of the install and wait for the answers:

1. "Do others clone or install your end product from GitHub?"
   - No: recommend **pattern A**. The codebase repository gets the Mentat brain, and the
     assistants and other Mentats go into a shared `agents` repository, each in its own folder.
     Say that this is the recommended path.
   - Yes: offer **pattern B**. The codebase splits into a release-only repository and a dev
     repository, the brain lives in the dev repository, and the shared `agents` repository sits
     next to them.
2. "Will any agent be handed over to someone one day, or hold data that belongs to someone else?"
   If yes, that agent gets its own repository; the rest go into the shared `agents` repository.

When installing into an empty folder and the owner plans several agents, offer to make this
folder the first agent folder of an `agents` repository (`agents/<name>/`). No `CLAUDE.md` with a
persona goes at the root.

When installing into an existing repository, look at which pattern it is closest to and say only
what would differ. Do not move, rename or create a repository without the owner's yes.

Record the choice as a decision: `python3 .mentat/bin/mentat_brain.py new decision "Repository
setup"`. Put in it: which pattern, which agent got its own repository and why, and which machine
the fleet runs on. Then tell the owner in two or three sentences what they chose, and that it can
be changed later.
