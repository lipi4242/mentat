"""Bejelentkezés a UNIT szemével (elfogadási mérés 2026-10-15, 06-flotta).

Ami eddig történt: a precheck a telepítő shelljének környezetével futtatta a
`claude auth status`-t. Egy shellben élő CLAUDE_CODE_OAUTH_TOKEN mellett ez
zöld, közben a unit nem látja a tokent; token nélküli shellben piros, és a
felhasználónak kellett kitalálnia, hogyan jut a token a unitba.

Itt: a unit környezete = a shell környezete a unit által törölt kulcsok
nélkül, a fiók CLAUDE_CONFIG_DIR-jével, és az ágens env-fájljából (amit a
unit pane-shellje betölt) jövő tokennel. Ha így nincs login, de a telepítő
shelljében vagy a systemd user manager környezetében van token, átadjuk:
a `~/.config/<ágens>/claude-auth.env`-be kerül (0600), sosem a kimenetbe.
Külön fájl, mert az ágens env-fájlját (alapból telegram.env) a híd is
betölti. Ha a telepítendő unit még a régi sablonból jön (nem tölti be a
claude-auth.env-et), a token az env-fájlba megy, figyelmeztetéssel — így a
sorrend (sablon / kód) nem törhet el semmit.
"""
from __future__ import annotations
import os
import subprocess
import tempfile
import time
from pathlib import Path

from fleet.registry import SHARED_ACCOUNT
from fleet.txn import run_cmd

TOKEN_VAR = "CLAUDE_CODE_OAUTH_TOKEN"
UNIT_UNSETS = ("ANTHROPIC_API_KEY", "CLAUDE_API_KEY", TOKEN_VAR, "CLAUDE_CONFIG_DIR")


def run_env(cmd: list[str], env: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    """A token környezetben megy, nem argv-ben (a /proc/<pid>/cmdline látszik)."""
    try:
        return subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60, cwd=cwd)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 127, "", str(e))


AUTH_FILE = "claude-auth.env"


def systemd_token(run=None) -> str | None:
    """A felhasználói systemd-manager környezetében élő token (ha a gép így kapta),
    idézőjelek nélkül; a shell env-jében ilyenkor nincs. Sosem íródik ki."""
    run = run or (lambda c: subprocess.run(c, capture_output=True, text=True, timeout=10))
    try:
        r = run(["systemctl", "--user", "show-environment"])
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    for line in r.stdout.splitlines():
        if line.startswith(TOKEN_VAR + "="):
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def env_file(entry: dict, home: Path) -> Path:
    return home / ".config" / entry["agent"] / entry["env_file"]


def auth_file(entry: dict, home: Path) -> Path:
    return home / ".config" / entry["agent"] / AUTH_FILE


def unit_loads_auth_file(entry: dict, unit_text: str | None = None) -> bool:
    """A telepítendő unit betölti-e a claude-auth.env-et (sablon #9 óta)."""
    if unit_text is None:
        from fleet import install
        try:
            unit_text = install.unit_text_for(entry)
        except (OSError, ValueError):
            return False
    return f"%h/.config/{entry['agent']}/{AUTH_FILE}" in unit_text


def token_file(entry: dict, home: Path, unit_text: str | None = None) -> Path:
    """Ahová a token kerül: a claude-auth.env, ha a unit betölti; különben az env-fájl."""
    return auth_file(entry, home) if unit_loads_auth_file(entry, unit_text) else env_file(entry, home)


def read_env_value(path: Path, key: str) -> str | None:
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return None
    val = None
    for ln in lines:
        s = ln.strip()
        if s.startswith("export "):
            s = s[7:].lstrip()
        if s.startswith(key + "="):
            val = s[len(key) + 1:].strip().strip("'\"") or None
    return val


def unit_env(entry: dict, home: Path, base: dict | None = None) -> dict:
    env = {k: v for k, v in (os.environ if base is None else base).items() if k not in UNIT_UNSETS}
    env["HOME"] = str(home)
    acc = entry.get("claude_account") or SHARED_ACCOUNT
    if acc != SHARED_ACCOUNT:
        env["CLAUDE_CONFIG_DIR"] = str(home / f".claude-{acc}")
    # a pane-shell sorrendje: előbb az env-fájl, utána a claude-auth.env (az nyer)
    tok = read_env_value(auth_file(entry, home), TOKEN_VAR) or read_env_value(env_file(entry, home), TOKEN_VAR)
    if tok:
        env[TOKEN_VAR] = tok
    return env


def logged_in(entry: dict, *, claude_bin: Path, home: Path, run=run_env) -> bool:
    return run([str(claude_bin), "auth", "status"], unit_env(entry, home)).returncode == 0


def manager_token(run=run_cmd) -> str | None:
    r = run(["systemctl", "--user", "show-environment"])
    for ln in (r.stdout or "").splitlines() if r.returncode == 0 else []:
        if ln.startswith(TOKEN_VAR + "="):
            return ln.split("=", 1)[1].strip("'\"") or None
    return None


def store_token(entry: dict, token: str, home: Path, unit_text: str | None = None) -> Path:
    """Upsert a `CLAUDE_CODE_OAUTH_TOKEN=` sorra, a többi sor marad; 0600."""
    p = token_file(entry, home, unit_text)
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    keep = [ln for ln in (p.read_text().splitlines() if p.exists() else [])
            if not ln.strip().removeprefix("export ").lstrip().startswith(TOKEN_VAR + "=")]
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=f".{p.name}.")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(keep + [f"{TOKEN_VAR}={token.strip()}"]) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, p)
    return p


def proof_path(entry: dict, home: Path) -> Path:
    return home / ".config" / "fleet" / "auth-ok" / (entry.get("claude_account") or SHARED_ACCOUNT)


def ensure_auth(entry: dict, *, claude_bin: Path, home: Path, environ: dict | None = None,
                run=run_env, sysrun=run_cmd) -> tuple[list[str], list[str]]:
    """(problémák, megjegyzések). Siker esetén a bizonyíték időbélyege a
    `proof_path`-ra kerül (authsig: amíg az ágens még nem válaszolt, ez az
    egyetlen bizonyíték, hogy a login él)."""
    environ = os.environ if environ is None else environ
    notes = []
    if not logged_in(entry, claude_bin=claude_bin, home=home, run=run):
        tok, src = environ.get(TOKEN_VAR), "a telepítő shellje"
        if not tok:
            tok, src = manager_token(sysrun), "a systemd user manager környezete"
        if not tok:
            return [f"a claude a unit számára nincs bejelentkezve (se credential, se {TOKEN_VAR}). "
                    f"Egy paranccsal javítható, abban a shellben, ahol a claude be van jelentkezve: "
                    f"`fleet auth {entry['agent']}` — vagy ezen a gépen: `claude auth login`"], notes
        p = store_token(entry, tok, home)
        if not logged_in(entry, claude_bin=claude_bin, home=home, run=run):
            return [f"a {TOKEN_VAR} ({src}) átadva ide: {p}, de a claude így sem lát érvényes logint "
                    f"— lejárt token? Új: `claude setup-token`, utána `fleet auth {entry['agent']}`"], notes
        notes.append(f"auth: a {TOKEN_VAR} ({src}) átadva a unitnak: ~/{p.relative_to(home)} (0600)")
        if p.name != AUTH_FILE:
            notes.append(f"FIGYELEM: a unit-sablon még nem tölti be a {AUTH_FILE}-et — a token az ágens "
                         "env-fájljába került, amit a híd is betölthet; a flotta (fleet/) frissítése után "
                         "futtasd újra a `fleet setup`-ot")
    pp = proof_path(entry, home)
    pp.parent.mkdir(parents=True, exist_ok=True)
    pp.write_text(str(time.time()))
    return [], notes
