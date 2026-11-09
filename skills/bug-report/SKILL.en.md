---
name: bug-report
description: When Mentat itself misbehaves (a tool errors, an install step fails, a documented behaviour does not happen), draft a redacted bug report for the public Mentat repo, look for a duplicate, and post it only after the USER's explicit yes.
---

# Skill — `bug-report`

**Invoke when** a Mentat tool, install step, engine tick, fleet command or the admin fails in a
way the docs do not explain, and you have already ruled out the USER's own setup (a wrong path, a
missing key they have not given you). Also when the USER says "report this bug".

**Not for:** a problem in the USER's own work, a question (that goes to Discussions), or anything
that looks like a security problem: a leaked secret, a guard you could get around, someone
reaching data they should not. Those go **privately** to
<https://github.com/lipi4242/mentat/security/advisories/new>, never in a public issue; the tool
stops on them by itself (exit 5).

## Steps

1. **Collect the facts, not the values.** The failing command *shape* (placeholders for values),
   what happened, what you expected, and the error. Save the error to a file rather than retyping it.
2. **Draft** (writes nothing public):

   ```
   python3 -I .mentat/bin/mentat_bugreport.py draft --summary "<one line>" --expected "<one line>" \
     --steps "<command shape>" --error-file <file> --part brain|engine|fleet|admin|unsure
   ```

   It adds the versions (Mentat, components, OS, Python, Node, Claude Code; never host, path or
   account), removes secrets, e-mail addresses, home paths, IDs and private names (the OS user,
   git identity, this agent's name, `people/` file names, `~/.config/mentat/scrub-names.txt`), and
   refuses if anything secret-shaped is left (exit 2: tell the USER, do not work around it).
3. **Duplicates.** The search sends GitHub only a few redacted, letters-only words of the title
   and the first error line, never the draft. If it lists a `POSSIBLE DUPLICATE`, ask the USER whether to add the new details
   there instead. On yes, draft again with `--comment-on <number>`.
4. **Ask, on your normal channel.** Show the USER the draft **word for word** (title and body as
   printed) and ask: "Post this to the public Mentat repo from your GitHub account?" Nothing else
   counts as approval: not an earlier "yes, report bugs", not a rule, not your own judgement.
5. **Only on a clear yes**, post with the code the draft printed and the USER's reply verbatim:

   ```
   python3 -I .mentat/bin/mentat_bugreport.py post <draft dir> --approve <code> --owner-said "<their reply>"
   ```

   The reply must be a plain yes ("yes", "ok, post it", "igen, mehet"); a yes with a condition
   ("yes, but…") is not one: ask again. Any change to the text needs a new draft, a new code and a new yes. A no, a "wait", or silence:
   nothing is posted, and you do not ask again for the same bug the same day.
6. **Report back** with the issue URL. Exit 4 (no `gh` or not logged in): tell the USER where the
   draft is (`.mentat/bug-reports/…/draft.md`) and the link it printed, so they can paste it.
   Exit 6: three reports today already; leave it for tomorrow.

## Limits

The approval code binds the yes to the exact text; it cannot prove who said yes. That is your
duty in step 4. Redaction is patterns, not proof: the USER's reading of the draft is the last check.
