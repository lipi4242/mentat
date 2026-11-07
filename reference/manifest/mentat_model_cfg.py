"""Files behind mentat_model.py: the repo's settings.local.json and the OpenRouter key file.

The key never goes to stdout. It is written to ~/.config/mentat/openrouter.env (0600) and
copied into the repo's .claude/settings.local.json (0600, refused unless git ignores it),
because that is the one place Claude Code reads it for this repo only.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

OWNED = ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
         "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL", "ANTHROPIC_DEFAULT_HAIKU_MODEL",
         "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL")
KEY_FILE = pathlib.Path(os.environ.get("MENTAT_KEY_FILE", "~/.config/mentat/openrouter.env")).expanduser()
IGNORE_LINES = (".claude/settings.local.json", ".mentat/model.env")


def settings_path(root):
    return root / ".claude" / "settings.local.json"


def load_settings(root):
    try:
        return json.loads(settings_path(root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(root, data):
    p = settings_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(p), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.chmod(str(p), 0o600)


def ensure_ignored(root):
    """The settings file holds the key: it must never be committable. Adds the .gitignore line
    if missing, then asks git itself. Returns a problem string, or None when safe."""
    if subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode != 0:
        return None  # not a git repo: nothing can commit it
    rel = IGNORE_LINES[0]
    tracked = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch", rel], capture_output=True)
    if tracked.returncode == 0:
        return "%s is already committed - remove it from git first (git rm --cached)" % rel
    gi = root / ".gitignore"
    for line in IGNORE_LINES:  # add a line only where git does not ignore the path already
        if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", line]).returncode != 0:
            text = gi.read_text(encoding="utf-8") if gi.exists() else ""
            gi.write_text(text + ("" if not text or text.endswith("\n") else "\n") + line + "\n")
            print("added   %s to .gitignore" % line)
    if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", rel]).returncode != 0:
        return "git would not ignore %s - fix .gitignore first" % rel
    return None


def read_key():
    try:
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip().removeprefix("export ").strip() == "OPENROUTER_API_KEY" and v.strip():
                return v.strip().strip("'\"")
    except OSError:
        pass
    return None


def write_key(clipboard):
    if clipboard:
        raw = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
    else:
        raw = sys.stdin.readline()
    key = "".join(raw.split())
    if not key.startswith("sk-or-"):
        print("REFUSED that is not an OpenRouter key (it should start with sk-or-); nothing written")
        return 2
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(KEY_FILE), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("OPENROUTER_API_KEY=%s\n" % key)
    os.chmod(str(KEY_FILE), 0o600)
    print("OK    key saved to %s (%d characters, 0600) - it is not printed anywhere" % (KEY_FILE, len(key)))
    return 0


def schedule_restart(agent, delay=20):
    """Restart this always-on agent from OUTSIDE its own session: systemd-run starts
    `fleet restart` (lock, restart, postcheck) as a separate unit, so killing this
    session does not kill the restart. Never `systemctl restart` from inside."""
    fleet = shutil.which("fleet")
    if not fleet or not shutil.which("systemd-run"):
        return ("NEXT  this machine has no `fleet` command: ask the developer agent that "
                "deploys %s to restart it (fleet restart %s)" % (agent, agent))
    unit = "mentat-model-restart-%s-%d" % (re.sub(r"[^A-Za-z0-9_-]", "-", agent), int(time.time()))
    r = subprocess.run(["systemd-run", "--user", "--on-active=%d" % delay, "--unit", unit, fleet,
                        "restart", agent], capture_output=True, text=True)
    if r.returncode != 0:
        return "NEXT  the restart could not be scheduled (%s)" % r.stderr.strip()[:200]
    return ("RESTART in %d s, out-of-band (%s) - tell the USER now; the new session runs on the "
            "new model, and its first answer should say so (mentat_model.py status)" % (delay, unit))
