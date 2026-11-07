#!/usr/bin/env python3
"""The Cloudflare API token, one step at a time, checked after every step.

    mentat_cf_token.py next      the single next step for the USER (exit 3), or done (exit 0)
    mentat_cf_token.py --check   is the token valid and does it hold every permission? (0/1/2)
    mentat_cf_token.py --check --for wrangler.toml   … every permission THIS project needs, all at once

Run `next`, pass its one STEP line to the USER, wait for "done", run `next` again. The token
lives only in the project's .env (mode 0600, git-ignored); this tool never prints it.
Exit: 0 ready, 1 token invalid, 2 a permission is missing, 3 waiting for the USER.
"""
import os
import pathlib
import sys

from cf_api import CFError, account_id, call, env_value

ENV = pathlib.Path(".env")
# (permission row in the token editor, probe path); {a} = account id
PROBES = [("Account · Workers Scripts · Edit", "/accounts/{a}/workers/scripts"),
          ("Account · D1 · Edit", "/accounts/{a}/d1/database"),
          ("Account · Access: Apps and Policies · Edit", "/accounts/{a}/access/apps")]
CREATE = ("STEP: dash.cloudflare.com → My Profile → API Tokens → Create Token → the "
          "'Edit Cloudflare Workers' template → Use template; set D1 to Edit and add "
          "Account · Access: Apps and Policies · Edit → Create Token. Paste it into the form at the "
          "link I send (it hides the text and keeps it on this computer; never into the chat), and say done.")
FORM = ("DO (you, before passing the step on): python3 .mentat/bin/mentat_serve.py start cf-token "
        "--secret CLOUDFLARE_API_TOKEN — send the USER its URL with the step; `status cf-token` says received.")


def prepare_env():
    if not ENV.exists():
        ENV.touch()
    os.chmod(ENV, 0o600)
    ign = pathlib.Path(".gitignore")
    lines = ign.read_text().splitlines() if ign.exists() else []
    if ".env" not in lines:
        ign.write_text("\n".join(lines + [".env"]) + "\n")


def missing(token, acc, probes=None):
    out = []
    for row, path in probes or PROBES:
        try:
            call(token, "GET", path.format(a=acc))
        except CFError as e:
            if not e.auth():
                raise
            out.append(row)
    return out


def status(token, probes=None):
    """(exit code, message) without printing the token."""
    try:
        call(token, "GET", "/user/tokens/verify")
    except CFError:
        return 1, "the token is invalid or expired"
    acc = account_id(token)
    gap = missing(token, acc, probes)
    if gap and probes:
        return 2, ("missing permission: %s — STEP for the USER: My Profile → API Tokens → … on the token's row → "
                   "Edit → set %s to Edit (add a row only if there is none) → Continue to summary → Update "
                   "token; the token stays the same" % ("; ".join(gap), ", ".join(gap)))
    if gap:
        return 2, "missing permission: %s" % gap[0]
    return 0, "token ok (account %s)" % acc


def record_account(token):
    acc = account_id(token)
    text = ENV.read_text()
    if "CLOUDFLARE_ACCOUNT_ID=" not in text:
        ENV.write_text(text + ("" if text.endswith("\n") or not text else "\n") + "CLOUDFLARE_ACCOUNT_ID=%s\n" % acc)
    return acc


def next_step():
    prepare_env()
    token = env_value("CLOUDFLARE_API_TOKEN")
    if not token:
        print(FORM + "\n" + CREATE)
        return 3
    code, msg = status(token)
    if code == 1:
        print(FORM + "\nSTEP: the token does not work (%s). Create a new one as before and paste it "
              "into the form at the link I send (it replaces the old one), then say done." % msg)
        return 3
    if code == 2:
        row = msg.split(": ", 1)[1]
        print("STEP: My Profile → API Tokens → … on the token's row → Edit → set %s (switch an "
              "existing row, add one only if there is none) → Continue to summary → Update token; "
              "say done." % row)
        return 3
    print("ready: token ok, account %s recorded in .env" % record_account(token))
    return 0


def main(argv):
    if "--check" in argv:
        token = env_value("CLOUDFLARE_API_TOKEN")
        if not token:
            print("no CLOUDFLARE_API_TOKEN in .env: run `mentat_cf_token.py next`")
            return 1
        spec = argv[argv.index("--for") + 1] if "--for" in argv[:-1] else (  # the project here, by default
            "wrangler.toml" if pathlib.Path("wrangler.toml").is_file() else None)
        if spec:
            sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
            import mentat_cf_need
        code, msg = status(token, mentat_cf_need.probes(spec) if spec else None)
        print(msg)
        return code
    if argv[:1] in ([], ["next"]):
        return next_step()
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
