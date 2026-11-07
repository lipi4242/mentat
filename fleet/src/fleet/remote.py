"""Egy ágens boxa: helyben vagy ssh-n. A `probe`, `login` közös szállítója.

    resolve("<ágens>")        → (registry-bejegyzés, Target) — a bejegyzés `host`-ja
                                 a boxes.json-ban; ugyanez a box → helyben
    resolve("user@box")       → (None, Target("user@box")) — registry nélkül is megy

Semmi nem vár emberre: BatchMode, ConnectTimeout, minden hívásnak határideje
van (túllépés = 124-es kód, nem várakozás). Értéket a parancssorba nem teszünk:
ami titok lehet (login-kód), az stdin-en megy, mert az argv a /proc-ban látszik.
"""
from __future__ import annotations
import os
import shlex
import subprocess
from dataclasses import dataclass

from fleet import RegistryNotConfigured

#: tesztekben hamis ssh (`FLEET_SSH=/út/fake-ssh`)
SSH_ENV = "FLEET_SSH"
PRELUDE = ('export GIT_TERMINAL_PROMPT=0 PATH="$HOME/.local/bin:$PATH" '
           'XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"; ')


@dataclass(frozen=True)
class Target:
    ssh: str | None          # None = helyben
    label: str

    def argv(self, script: str) -> list[str]:
        if self.ssh is None:
            return ["bash", "-c", PRELUDE + script]
        ssh = shlex.split(os.environ.get(SSH_ENV) or "ssh")
        return ssh + ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15",
                      "--", self.ssh, "bash -c " + shlex.quote(PRELUDE + script)]

    def sh(self, script: str, stdin: str | None = None, timeout: float = 60) -> subprocess.CompletedProcess:
        cmd = self.argv(script)
        try:
            return subprocess.run(cmd, input=stdin, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(cmd, 124, "", f"határidő: {int(timeout)} mp")
        except OSError as e:
            return subprocess.CompletedProcess(cmd, 127, "", str(e))


def ssh_target_of(box: dict) -> str | None:
    """A boxes.json bejegyzésből: `ssh_target`, különben `unix_user@hostname`."""
    if box.get("ssh_target"):
        return box["ssh_target"]
    host = box.get("hostname") or box.get("key")
    if not host:
        return None
    return f"{box['unix_user']}@{host}" if box.get("unix_user") else host


def resolve(name: str, *, ssh: str | None = None, agents: list[dict] | None = None,
            boxes: list[dict] | None = None, here: str | None = None) -> tuple[dict | None, Target]:
    """`ssh` megadva: a cél az, a registry-bejegyzés (ha van) csak adatot ad (fiók, modell)."""
    from fleet import registry as reg, registry_dir
    entry = None
    try:
        entry = reg.get_agent(name, agents)
        if boxes is None and entry is not None:
            boxes = reg.load_boxes()
        if entry is not None and here is None:
            here = reg.local_host(boxes)
    except RegistryNotConfigured:
        entry = None
    if ssh:
        return entry, Target(ssh, ssh)
    if entry is None:
        return None, Target(name, name)
    host = entry.get("host")
    if host is None or host == here:
        return entry, Target(None, f"{host or 'helyi gép'} (helyben)")
    box = next((b for b in boxes or [] if b.get("key") == host), None)
    tgt = ssh_target_of(box) if box else None
    if not tgt:
        raise ValueError(f"{name}: a(z) {host!r} box nincs a boxes.json-ban (vagy nincs hostname/ssh_target)")
    return entry, Target(tgt, f"{host} ({tgt})")
