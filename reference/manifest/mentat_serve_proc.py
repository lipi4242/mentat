"""Helpers for mentat_serve.py: private files (state, env), is it ours and alive, status, stop."""
import json
import os
import pathlib
import signal
import subprocess

STATE = pathlib.Path(".mentat", "state", "serve")


def private(path, text):
    """Write a file only its owner can read (the state holds the form's token)."""
    tmp = "%s.%d.tmp" % (path, os.getpid())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def write_env(path, var, value):
    path = pathlib.Path(path)
    old = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    new = "%s=%s" % (var, value)
    if any(ln.startswith(var + "=") for ln in old):  # replace in place, keep the order
        lines = [new if ln.startswith(var + "=") else ln for ln in old]
    else:
        lines = old + [new]
    private(path, "\n".join(lines) + "\n")


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def alive(st):
    """Running, and really ours: the process line names this state file (a reused pid is not)."""
    pid = st.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return False
    if os.name == "nt":  # the command line, not just the pid: a reused pid is someone else's program
        cmd = ["powershell", "-NoProfile", "-Command",
               "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid]
    else:
        cmd = ["ps", "-o", "command=", "-p", str(pid)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True).stdout
    except OSError:
        return False
    return "mentat_serve_run.py" in out and str(st.get("state", "\0")) in out


def _tail(log, n=8):
    try:
        return "\n".join(pathlib.Path(log).read_text(encoding="utf-8", errors="replace").splitlines()[-n:])
    except OSError:
        return ""


def _kill(st):
    pid = st.get("pid")
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)], capture_output=True)
        else:
            os.killpg(pid, signal.SIGTERM)
    except (OSError, TypeError):
        pass


def status(root, name):
    files = sorted((root / STATE).glob((name or "*") + ".json"))
    if not files:
        print("nothing started" + (" as %s" % name if name else ""))
    for f in files:
        st = _load(f)
        run = alive(st)
        extra = " · received" if st.get("received") else (" · waiting for the value" if st.get("mode") == "secret" else "")
        print("%s %s · %s · %s%s" % (st.get("name"), st.get("mode"), "running" if run else "stopped",
                                      (st.get("url") or "-") if run else "-", extra))
    return 0


def stop(root, name):
    for f in sorted((root / STATE).glob((name or "*") + ".json")):
        st = _load(f)
        if alive(st):
            _kill(st)
            print("STOPPED %s" % st.get("name"))
        else:
            print("%s is not running" % st.get("name", f.stem))
    return 0
