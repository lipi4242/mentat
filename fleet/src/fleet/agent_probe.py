"""`fleet probe` tényfelvétele EGY ágensről, a saját boxán — önálló, csak stdlib, csak olvas.

A hívó helyben futtatja, vagy ssh-n a box `python3 -`-jának stdin-jére küldi. Szándékosan
nem importál a `fleet` csomagból: a régi boxon régi a fleet-kód, és pont azt akarjuk
megmérni (2026-10-29: az egyik box fleet-checkoutja hetek óta elavult volt, ezért nem
volt rajta auth-jel, és senki nem tudta).

    python3 agent_probe.py '{"agent": "x", "account": "shared", "fetch": true}'   → JSON

Amit mér: él-e a login (a transzkript utolsó assistant-rekordja dönt, mint az authsig-ben),
min fut TÉNYLEG (az utolsó valódi válasz `model` mezője, nem a unit), a box fleet-checkoutja
és a registry forrása hány committal van az origin mögött, és honnan jön a registry.
Ami nem mérhető, az `null` és az `errors`-ba kerül — sosem üres eredmény. Értéket env-fájlból,
tokenből nem olvas és nem ír ki.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TS = re.compile(r'"timestamp":"([^"]+)"')
SCAN_BYTES = 8 * 1024 * 1024


def run(*cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
        return r.stdout.strip() if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def claude_home(home, account):
    return home / (".claude" if account in (None, "", "shared") else ".claude-" + account)


def transcript(home, agent, account):
    try:
        sid = (home / ".config" / agent / "session.id").read_text().strip()
    except OSError:
        return None, "nincs session.id"
    m = sorted(claude_home(home, account).glob("projects/*/%s.jsonl" % sid))
    return (m[0], None) if m else (None, "nincs transzkript a session.id-hez")


def tail_lines(p):
    with p.open("rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - SCAN_BYTES))
        return f.read().decode("utf-8", "replace").splitlines()


def assistant_facts(lines):
    """Pure: {auth, auth_since, failed, last_ok_at, model, model_at} — ugyanaz a szabály, mint
    az authsig-ben: az UTOLSÓ assistant-rekord dönt; más API-hiba (túlterhelés) se nem ok, se nem hiba."""
    out = {"auth": None, "auth_since": None, "failed": 0, "last_ok_at": None, "model": None, "model_at": None}
    for line in lines:
        if '"type":"assistant"' not in line:
            continue
        t = TS.search(line)
        if not t:
            continue
        if '"error":"authentication_failed"' in line:
            if out["auth"] != "expired":
                out["auth_since"], out["failed"] = t.group(1), 0
            out["auth"], out["failed"] = "expired", out["failed"] + 1
        elif '"isApiErrorMessage":true' not in line:
            out["auth"], out["last_ok_at"], out["auth_since"], out["failed"] = "ok", t.group(1), None, 0
            try:
                model = (json.loads(line).get("message") or {}).get("model")
            except ValueError:
                model = None
            if model and model != "<synthetic>":
                out["model"], out["model_at"] = model, t.group(1)
    return out


def git_facts(d, fetch):
    top = run("git", "-C", str(d), "rev-parse", "--show-toplevel")
    if not top:
        return None
    g = lambda *a: run("git", "-C", top, *a)  # noqa: E731
    fetched = bool(fetch) and run("git", "-C", top, "fetch", "--quiet", timeout=45) is not None
    behind = g("rev-list", "--count", "HEAD..@{u}")
    ahead = g("rev-list", "--count", "@{u}..HEAD")
    return {"path": top, "branch": g("branch", "--show-current") or None, "head": g("rev-parse", "--short", "HEAD"),
            "upstream": g("rev-parse", "--abbrev-ref", "@{u}"), "fetched": fetched,
            "behind": int(behind) if behind and behind.isdigit() else None,
            "ahead": int(ahead) if ahead and ahead.isdigit() else None,
            "dirty": len((g("status", "--porcelain") or "").splitlines())}


def fleet_checkout(home):
    path = os.environ.get("PATH", "")
    exe = shutil.which("fleet", path=str(home / ".local" / "bin") + os.pathsep + path)
    if not exe:
        return None, None
    real = Path(os.path.realpath(exe))
    return real, (real.parent.parent if real.parent.name == "bin" else real.parent)


def registry_source(home):
    if os.environ.get("FLEET_REGISTRY"):
        return "FLEET_REGISTRY", os.environ["FLEET_REGISTRY"]
    try:
        return "~/.config/fleet/registry", (home / ".config" / "fleet" / "registry").read_text().strip() or None
    except OSError:
        return "~/.config/fleet/registry", None


def probe(spec, home=None):
    home = Path(home or Path.home())
    agent, account = spec["agent"], spec.get("account") or "shared"
    out = {"agent": agent, "account": account, "errors": []}
    tp, why = transcript(home, agent, account)
    facts = {}
    if tp is None:
        out["errors"].append("transzkript: " + why)
    else:
        try:
            facts = assistant_facts(tail_lines(tp))
        except OSError as e:
            out["errors"].append("transzkript nem olvasható: %s" % e)
    out.update({k: facts.get(k) for k in ("auth", "auth_since", "failed", "last_ok_at", "model", "model_at")})
    exe, repo = fleet_checkout(home)
    out["fleet"] = git_facts(repo, spec.get("fetch")) if repo else None
    if out["fleet"] is not None:
        out["fleet"]["version"] = run(str(exe), "--version")
    else:
        out["errors"].append("fleet-checkout: nincs `fleet` a PATH-on (~/.local/bin is)")
    src, raw = registry_source(home)
    reg = {"source": src, "path": raw, "realpath": os.path.realpath(os.path.expanduser(raw)) if raw else None}
    reg["git"] = git_facts(reg["realpath"], spec.get("fetch")) if reg["realpath"] and Path(reg["realpath"]).is_dir() else None
    if not raw:
        out["errors"].append("registry: nincs beállítva (sem FLEET_REGISTRY, sem ~/.config/fleet/registry)")
    out["registry"] = reg
    out["timezone"] = run("timedatectl", "show", "-p", "Timezone", "--value") or os.environ.get("TZ")
    return out


if __name__ == "__main__":
    print(json.dumps(probe(json.loads(sys.argv[1])), ensure_ascii=False))
