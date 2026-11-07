"""Mit mutat az ágens tmux-pane-je: áll-e a claude egy indítási ablaknál.

A unit `active`, a processz fut — közben a claude egy dialógusnál vár, és
senki nem látja (elfogadási mérés, 2026-10-15: a Bypass Permissions ablakot a
felhasználónak tmux-ban, nyilakkal kellett elfogadnia). Ezért a telepítés és
a doctor a pane SZÖVEGÉT is nézi, nem csak a processzt.

A minták a Claude Code 2.1.x bináris szövegeiből (2026-10-16). Az elsőbbség
sorrendben: egy pane-en egyszerre egy ablak látszik.
"""
from __future__ import annotations

from fleet.txn import run_cmd

#: (minta a pane-ben, ablak neve, mi előzi meg)
DIALOGS = (
    ("Quick safety check", "workspace trust",
     "a workdir nincs megbízhatónak jelölve (projects[<workdir>].hasTrustDialogAccepted)"),
    ("Yes, I trust this folder", "workspace trust",
     "a workdir nincs megbízhatónak jelölve (projects[<workdir>].hasTrustDialogAccepted)"),
    ("Bypass Permissions mode", "Bypass Permissions elfogadás",
     "skipDangerousModePermissionPrompt: true a fiók settings.json-jában"),
    ("Yes, I accept", "Bypass Permissions elfogadás",
     "skipDangerousModePermissionPrompt: true a fiók settings.json-jában"),
    ("Choose the text style", "téma (első indítás)", "hasCompletedOnboarding: true a .claude.json-ban"),
    ("Select login method", "bejelentkezés", "a unit nem lát credentialt — `fleet auth <ágens>`"),
    ("Enable Remote Control?", "Remote Control", "remoteDialogSeen: true a .claude.json-ban"),
)


def dialog_in(text: str | None) -> tuple[str, str] | None:
    """Pure: (ablak neve, mi előzi meg), ha a pane egy ismert ablaknál áll."""
    if not text:
        return None
    for pattern, name, fix in DIALOGS:
        if pattern in text:
            return name, fix
    return None


def capture(session: str, run=run_cmd, tmux: str = "tmux") -> str | None:
    """A pane látható szövege, vagy None, ha nincs ilyen session / nincs tmux."""
    r = run([tmux, "capture-pane", "-p", "-t", f"={session}:"])
    return r.stdout if r.returncode == 0 else None


def pane_dialog(session: str, run=run_cmd, tmux: str = "tmux") -> str | None:
    """Emberi sor, ha a pane ablaknál áll; különben None."""
    d = dialog_in(capture(session, run, tmux))
    if d is None:
        return None
    return f"a claude a(z) „{d[0]}” ablaknál áll a tmux-ban — nem dolgozik (megelőzés: {d[1]})"
