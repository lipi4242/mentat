"""Shared test fixture (tests only): a brain with an approved contract, a Google token and the fake."""
import json
import os
import subprocess
import sys
import tempfile

from _contract_fixture import GOOD_CSV, HERE, PROPOSAL, approved, brain, write  # noqa: F401
from _google_fake import Fake

FUTURE = "2099-01-01T00:00:00Z"


def token(root, fake, expiry=FUTURE, value="a-good"):
    d = root / ".secrets" / "google"
    d.mkdir(parents=True, exist_ok=True)
    (d / "token.json").write_text(json.dumps({
        "token": value, "refresh_token": "r-1", "token_uri": fake.base + "/token",
        "client_id": "cid", "client_secret": "csecret", "expiry": expiry}))
    return d / "token.json"


def setup(proposal=None, lang="en"):
    fake = Fake()
    root = brain(lang)
    approved(root, proposal or PROPOSAL)
    token(root, fake)
    return fake, root


def run(root, fake, *args, tool="mentat_google.py", extra_env=None):
    env = dict(os.environ, HOME=tempfile.mkdtemp(), MENTAT_GOOGLE_API=fake.base if fake else "http://127.0.0.1:9")
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(HERE / tool), "--repo", str(root), *args],
                          capture_output=True, text=True, env=env)
