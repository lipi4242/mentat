"""What differs per OS for the install: the shell the hooks run in, and how to get git or Python.

system() -> "windows" | "mac" | "linux"
hook_shell(env) -> argv prefix that runs a hook command the way Claude Code does, or None
script(path) -> argv that runs a bash script (through Git Bash on Windows)
hint(tool) -> the official one-line install of git or python3 for this system
ensure_tzdata(lang) -> Windows: puts the tzdata package next to this Python; one line, or None

Claude Code runs a hook `command` with `sh -c` on macOS and Linux and with Git Bash on
Windows (PowerShell only when Git Bash is missing; the guard hook is POSIX shell).
"""
import os
import pathlib
import re
import shutil
import subprocess
import sys

_WINGET = " --accept-package-agreements --accept-source-agreements"
HINTS = {
    "git": {
        "windows": "winget install --id Git.Git -e --source winget" + _WINGET
                   + " (utána a Claude-ot zárd be és nyisd újra, hogy a Git Bash látszódjon)",
        "mac": "xcode-select --install (egy ablak: Telepítés; ez hozza a python3-at is)",
        "linux": "sudo apt install git (Fedora: sudo dnf install git)",
    },
    "python3": {
        # the Python install manager: it brings `python3`; Python.Python.3.x does not, and
        # there `python3` is the Microsoft Store stub
        "windows": "winget install 9NQ7512CXL7T -e" + _WINGET + " (Python install manager, ad python3-at)",
        "mac": "xcode-select --install",
        "linux": "sudo apt install python3 (Fedora: sudo dnf install python3)",
    },
}


def system():
    if os.name == "nt":
        return "windows"
    return "mac" if sys.platform == "darwin" else "linux"


def hook_shell(env=None):
    if system() != "windows":
        return ["/bin/sh", "-c"]
    env = os.environ if env is None else env
    configured = env.get("CLAUDE_CODE_GIT_BASH_PATH")
    if configured and pathlib.Path(configured).is_file():
        return [configured, "-c"]
    # git.exe is …\Git\cmd\ from Windows, …\Git\mingw64\bin\ inside Git Bash (Claude Code's
    # Bash tool); a bash.exe on PATH may be WSL's, never that
    git = shutil.which("git")
    tops = list(pathlib.Path(git).parents)[1:3] if git else []
    tops += [pathlib.Path(env[k]) / "Git" for k in ("ProgramFiles", "ProgramW6432") if env.get(k)]
    for top in tops:
        for cand in (top / "bin" / "bash.exe", top / "usr" / "bin" / "bash.exe"):
            if cand.is_file():
                return [str(cand), "-c"]
    return None


def script(path):
    if system() != "windows":
        return [str(path)]
    shell = hook_shell()
    return [shell[0], str(path)] if shell else [str(path)]


def hint(tool):
    return HINTS[tool][system()]


# Windows Python has no IANA time-zone database: zoneinfo needs the tzdata package there.
NOT_WRITABLE = re.compile(r"Defaulting to user installation|site-packages is not writeable|"
                          r"WinError 5|Access is denied|Permission denied", re.I)
TZ_PROBE = "import zoneinfo; zoneinfo.ZoneInfo('Europe/Budapest')"
TZ_MSG = {
    "hu": ("Időzóna-adatok: feltettem a tzdata csomagot (a Windows-os Python nem hozza magával).",
           "FIGYELEM: a tzdata csomagot nem sikerült feltenni (nincs net vagy pip?); enélkül nem megy a "
           "helyi idő szerinti ütemezés és a határidők számolása. Pótlás, ha lesz net: %s",
           "FIGYELEM: ez a Python minden felhasználónak van telepítve (Program Files), oda csak "
           "rendszergazda írhat, így a tzdata nem került fel; enélkül nem megy a helyi idő szerinti "
           "ütemezés és a határidők számolása. Pótlás: nyiss egy rendszergazdaként futtatott "
           "PowerShellt, és futtasd: %s"),
    "en": ("Time-zone data: installed the tzdata package (Windows Python does not ship it).",
           "WARNING: could not install the tzdata package (no network or pip?); without it local-time "
           "scheduling and deadlines do not work. To add it when online: %s",
           "WARNING: this Python is installed for all users (Program Files), which only an "
           "administrator can write, so tzdata was not installed; without it local-time scheduling "
           "and deadlines do not work. To add it: open PowerShell as administrator and run: %s"),
}


def ensure_tzdata(lang="hu", run=subprocess.run, py=None):
    """Windows only: install tzdata into THIS Python (not --user: the tools run with -I, which hides
    the user site). Never raises and never stops the install: a failure is one line with the command."""
    if system() != "windows":
        return None
    py = py or sys.executable
    msg = TZ_MSG.get(lang, TZ_MSG["en"])

    def present():
        return run([py, "-I", "-c", TZ_PROBE], capture_output=True, timeout=60).returncode == 0

    admin = False
    try:
        if present():
            return None
        r = run([py, "-m", "pip", "install", "--disable-pip-version-check", "tzdata"], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=300)
        if r.returncode == 0 and present():
            return msg[0]
        # an all-users Python: pip falls back to the user site (hidden by -I) or is refused
        admin = bool(NOT_WRITABLE.search((r.stdout or "") + (r.stderr or "")))
    except (OSError, subprocess.SubprocessError):
        pass
    return msg[2 if admin else 1] % ('"%s" -m pip install tzdata' % py)
