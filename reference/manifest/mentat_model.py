#!/usr/bin/env python3
"""Which model this agent runs on: Claude (default) or a measured open model via OpenRouter.

    python3 mentat_model.py list                      # recommended models, measured
    python3 mentat_model.py key [--clipboard]         # OpenRouter key: stdin (or pbpaste) -> 0600 file
    python3 mentat_model.py use <model-id>            # switch THIS repo's agent, live probe, rollback on failure
    python3 mentat_model.py use claude                # back to Claude (same as `off`)
    python3 mentat_model.py status

Only this repo's `.claude/settings.local.json` (git-ignored, 0600) and `.mentat/model.env` change;
the shared Claude login (~/.claude) is never touched, so other agents here stay on Claude.
"""
import argparse, json, os, pathlib, subprocess, sys  # noqa: E401

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mentat_model_cfg import (OWNED, KEY_FILE, read_key, settings_path, load_settings,  # noqa: E402
                              save_settings, ensure_ignored, write_key, schedule_restart)

ENDPOINT = "https://openrouter.ai/api"
ALIASES = ("ANTHROPIC_MODEL", "ANTHROPIC_DEFAULT_OPUS_MODEL", "ANTHROPIC_DEFAULT_SONNET_MODEL",
           "ANTHROPIC_DEFAULT_HAIKU_MODEL", "ANTHROPIC_SMALL_FAST_MODEL", "CLAUDE_CODE_SUBAGENT_MODEL")


def recommended():
    return json.loads((HERE / "mentat-models.json").read_text(encoding="utf-8"))["models"]


def current(root):
    env = load_settings(root).get("env", {})
    return env.get("ANTHROPIC_MODEL") if env.get("ANTHROPIC_BASE_URL") == ENDPOINT else None


def probe(root, model):
    """One tiny real call in this repo: the answer must come from `model` and nothing else."""
    claude = os.environ.get("MENTAT_CLAUDE", "claude")
    try:
        r = subprocess.run([claude, "-p", "Reply with just: ok", "--output-format", "json"], cwd=root,
                           capture_output=True, text=True, timeout=180, stdin=subprocess.DEVNULL)
        d = json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.TimeoutExpired) as e:
        return "the probe did not run (%s)" % type(e).__name__
    used = sorted((d.get("modelUsage") or {}).keys())
    if d.get("is_error"):
        return "the probe failed: %s" % str(d.get("result", ""))[:200]
    if used != [model]:
        return "the probe answered from %s, not %s" % (", ".join(used) or "nothing", model)
    return None


def restart_hint():
    """The USER never types a command: an always-on agent restarts itself out-of-band."""
    agent = os.environ.get("FLEET_AGENT")
    if not agent:
        return "NEXT  tell the USER: close this session and open a new one in this folder"
    if os.environ.get("MENTAT_NO_RESTART"):
        return "NEXT  restart skipped (MENTAT_NO_RESTART)"
    return schedule_restart(agent)


def use(root, model, force, no_probe):
    if model == "claude":
        return off(root, no_probe)
    ids = [m["id"] for m in recommended()]
    if model not in ids and not force:
        print("REFUSED %s is not a measured model (%s); add --force to use it anyway"
              % (model, ", ".join(ids)))
        return 2
    key = read_key()
    if not key:
        print("MISSING the OpenRouter key: run `python3 .mentat/bin/mentat_model.py key` first (%s)" % KEY_FILE)
        return 2
    problem = ensure_ignored(root)
    if problem:
        print("REFUSED %s" % problem)
        return 2
    before = settings_path(root).read_text() if settings_path(root).exists() else None
    s = load_settings(root)
    s.setdefault("env", {}).update({"ANTHROPIC_BASE_URL": ENDPOINT, "ANTHROPIC_AUTH_TOKEN": key,
                                    "ANTHROPIC_API_KEY": "", **{a: model for a in ALIASES}})
    save_settings(root, s)
    (root / ".mentat").mkdir(exist_ok=True)
    (root / ".mentat" / "model.env").write_text("MENTAT_MODEL=%s\n" % model)
    err = None if no_probe else probe(root, model)
    if err:
        if before is None:
            settings_path(root).unlink()
        else:
            settings_path(root).write_text(before)
        (root / ".mentat" / "model.env").unlink()
        print("ROLLED BACK %s - this agent stays on its previous model" % err)
        return 1
    print("OK    this agent now runs on %s via OpenRouter%s" % (model, "" if no_probe else " (probe answered)"))
    print("DATA  everything this agent reads (brain, files, conversation) now goes to OpenRouter and the "
          "provider it routes to; set openrouter.ai Settings > Privacy: zero-data-retention endpoints only, "
          "no providers that train on inputs")
    print(restart_hint())
    return 0


def off(root, no_probe=True):
    s = load_settings(root)
    env = {k: v for k, v in s.get("env", {}).items() if k not in OWNED}
    if env:
        s["env"] = env
    else:
        s.pop("env", None)
    if s:
        save_settings(root, s)
    elif settings_path(root).exists():
        settings_path(root).unlink()
    mf = root / ".mentat" / "model.env"
    if mf.exists():
        mf.unlink()
    print("OK    this agent runs on Claude again (the shared Claude login was never changed)")
    print(restart_hint())
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo", default=".")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("list", "status", "off"):
        sub.add_parser(name)
    k = sub.add_parser("key")
    k.add_argument("--clipboard", action="store_true", help="read from pbpaste instead of stdin")
    u = sub.add_parser("use")
    u.add_argument("model")
    u.add_argument("--force", action="store_true", help="allow a model that is not in the measured list")
    u.add_argument("--no-probe", action="store_true")
    a = p.parse_args(argv)
    root = pathlib.Path(a.repo).resolve()
    if a.cmd == "list":
        for m in recommended():
            print("%-36s %s" % (m["id"], m["note"]))
        return 0
    if a.cmd == "status":
        m = current(root)
        print("MODEL %s" % (m + " via OpenRouter" if m else "Claude (default)"))
        print("KEY   %s" % ("present" if read_key() else "missing (%s)" % KEY_FILE))
        return 0
    if a.cmd == "key":
        return write_key(a.clipboard)
    if a.cmd == "off":
        return off(root)
    return use(root, a.model, a.force, a.no_probe)


if __name__ == "__main__":
    sys.exit(main())
