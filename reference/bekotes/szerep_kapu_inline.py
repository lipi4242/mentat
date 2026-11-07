"""Two nets for szerep_kapu (wired in _later): code run inline, and mail sent from the shell.

guard_write(tool, inp) -> True: a python/node command whose own code (`-c`, `-e`, a heredoc) names the
guard's or the product's files (.mentat/bin, .claude/settings*.json) and writes (open … 'w'/'a',
write_text, shutil, os.replace/rename/remove, writeFileSync): the same as editing them ("beallitas").
mail(tool, inp) -> True: a mail sender (sendmail, mail, mailx, msmtp, mutt, swaks) or inline code
that sends mail (smtplib): an outbound message ("post"), so it goes through the read-back.
Known limits: text patterns over the command line; a script file run from disk is not read.
"""
import re

from szerep_bash import commands

PROTECTED = re.compile(r"\.mentat/bin|\.claude/settings[\w.]*\.json|\.mentat/model\.env")
WRITES = re.compile(r"open\([^)]*['\"][wax+]+b?['\"]|write_(text|bytes)\(|shutil\.|os\.(replace|rename|remove|unlink)\(|"
                    r"\.unlink\(|writeFileSync|appendFileSync|copyFileSync|fs\.rm")
INTERP = re.compile(r"(^|[\s;&|(])(python[0-9.]*|node|bun|deno|perl|ruby)\b")
MAILERS = {"sendmail", "mail", "mailx", "msmtp", "mutt", "swaks"}


def guard_write(tool, inp):
    cmd = str(inp.get("command", "")) if tool == "Bash" else ""
    return bool(cmd and INTERP.search(cmd) and PROTECTED.search(cmd) and WRITES.search(cmd))


def mail(tool, inp):
    cmd = str(inp.get("command", "")) if tool == "Bash" else ""
    if not cmd:
        return False
    if INTERP.search(cmd) and "smtplib" in cmd:
        return True
    return any(name in MAILERS for name, *_ in commands(cmd, None))
