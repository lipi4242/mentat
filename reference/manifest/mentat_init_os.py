"""What differs per OS for the install: the shell the hooks run in, and how to get git or Python.

system() -> "windows" | "mac" | "linux"
hook_shell(env) -> argv prefix that runs a hook command the way Claude Code does, or None
script(path) -> argv that runs a bash script (through Git Bash on Windows)
hint(tool) -> the official one-line install of git or python3 for this system

Claude Code runs a hook `command` with `sh -c` on macOS and Linux and with Git Bash on
Windows (PowerShell only when Git Bash is missing; the guard hook is POSIX shell).
"""
import os
import pathlib
import shutil
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
    git = shutil.which("git")  # …\Git\cmd\git.exe; a bash.exe on PATH may be WSL's, never that
    if git:
        top = pathlib.Path(git).parent.parent
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
