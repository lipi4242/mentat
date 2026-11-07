"""Where the todo API is, whose ball we read, and the token (never printed).

First wins, per setting:

    api     TODO_API (the todo base, e.g. https://admin.example/api/todo/v1)
            | .mentat/local.json admin.url + "/api/todo/v1", only when
              mentat.json components.admin.plugins lists "todo"
    handle  TODO_HANDLE | mentat.json components.engine.todo_handle
    token   TODO_TOKEN_FILE (a file holding only the token, mode 0600)
            | the admin connection's token: $<admin.token_env>, or that key
              in the repo's .env (written by the admin's `npm run connect`)
On a fleet box (FLEET_AGENT set by the unit) each setting that is still missing comes
from the box convention `fleet/bin/mentat-todo` also uses: ~/.config/todo/env (TODO_API=),
~/.config/todo/handles ("agent=handle", else the agent name), ~/.config/todo/<handle>.token.

No api or no handle = not configured: the pack stays silent (load() -> None).
Configured but no usable token = TodoConfigError, reported like an API error.
"""
from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from anytime_engine import mentat_manifest as mm

API_PATH = "/api/todo/v1"


class TodoConfigError(Exception):
    """The pack is configured, but cannot authenticate."""


@dataclass(frozen=True)
class Settings:
    api: str
    handle: str
    root: Path
    token_file: str | None = None
    token_env: str | None = None

    def token(self) -> str:
        if self.token_file:
            return _read_token_file(Path(self.token_file))
        if self.token_env:
            tok = os.environ.get(self.token_env) or _dotenv(self.root / ".env", self.token_env)
            if tok:
                return tok
            raise TodoConfigError(f"todo token missing: ${self.token_env} is not set (env or .env)")
        raise TodoConfigError("todo token missing: set TODO_TOKEN_FILE (a 0600 file)")


def _read_token_file(p: Path) -> str:
    try:
        mode = p.stat().st_mode
        text = p.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise TodoConfigError(f"todo token file unreadable: {p} ({e.strerror})") from None
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise TodoConfigError(f"todo token file {p} is readable by others: chmod 600 it")
    if not text or "\n" in text:
        raise TodoConfigError(f"todo token file {p} must hold exactly one token")
    return text


def _dotenv(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        k, sep, v = line.strip().removeprefix("export ").partition("=")
        if sep and k.strip() == key:
            return v.strip().strip("\"'") or None
    return None


def load(root: Path) -> Settings | None:
    try:
        doc = mm.load(root) or {}
        local = mm.local(root) or {}
    except mm.ManifestError:      # the tick refuses such a manifest on its own
        return None
    comps = doc.get("components") or {}
    admin_comp = comps.get("admin") or {}
    admin = local.get("admin") or {}
    api = os.environ.get("TODO_API")
    if not api and admin.get("url") and "todo" in (admin_comp.get("plugins") or []):
        api = str(admin["url"]).rstrip("/") + API_PATH
    handle = os.environ.get("TODO_HANDLE") or (comps.get("engine") or {}).get("todo_handle")
    token_file = os.environ.get("TODO_TOKEN_FILE") or None
    box = _box(handle)
    api, handle = api or box.get("api"), handle or box.get("handle")
    if not token_file and not admin.get("token_env"):
        token_file = box.get("token_file")
    if not api or not handle:
        return None
    return Settings(api=str(api).rstrip("/"), handle=str(handle), root=root,
                    token_file=token_file, token_env=admin.get("token_env") or None)


def _box(handle: str | None) -> dict:
    """The fleet box convention (only under a fleet unit: FLEET_AGENT is set)."""
    agent = os.environ.get("FLEET_AGENT")
    if not agent:
        return {}
    cfg = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "todo"
    if not cfg.is_dir():
        cfg = Path.home() / ".config" / "todo"
    out: dict = {"api": _dotenv(cfg / "env", "TODO_API")}
    if not handle:
        handle = _dotenv(cfg / "handles", agent) or agent
        out["handle"] = handle
    tok = cfg / f"{handle}.token"
    if tok.is_file():
        out["token_file"] = str(tok)
    return out
