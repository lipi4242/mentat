"""Writes a stand-in `google_auth_oauthlib` package into a folder (tests only).

The stand-in records each call to $FAKE_FLOW_LOG as a JSON line. With FAKE_FLOW_TIMEOUT set,
run_local_server fails the way the real one does when nobody signs in before the timeout.
"""
import pathlib

FLOW = '''
import json, os

def _log(**kw):
    with open(os.environ["FAKE_FLOW_LOG"], "a") as f:
        f.write(json.dumps(kw) + "\\n")

class Creds:
    def __init__(self, scopes):
        self.scopes = scopes
    def to_json(self):
        return json.dumps({"token": "a-good", "refresh_token": "r-1", "client_id": "cid",
                           "client_secret": "csecret", "token_uri": "https://oauth2.googleapis.com/token",
                           "scopes": self.scopes, "expiry": "2099-01-01T00:00:00Z"})

class Flow:
    @classmethod
    def from_client_secrets_file(cls, path, scopes, **kw):
        json.load(open(path))["installed"]
        f = cls()
        f.scopes, f.redirect_uri, f.state = scopes, kw.get("redirect_uri"), kw.get("state")
        f.code_verifier = kw.get("code_verifier") or "v-123"
        return f
    def authorization_url(self, **kw):
        _log(call="authorization_url", redirect_uri=self.redirect_uri, **kw)
        return "https://accounts.example.com/o/oauth2/auth?state=s-1", "s-1"
    def fetch_token(self, authorization_response=None, **kw):
        _log(call="fetch_token", url=authorization_response, verifier=self.code_verifier, state=self.state)
        if "code=" not in authorization_response:
            raise ValueError("no code in the address")
        self.credentials = Creds(self.scopes)

class InstalledAppFlow(Flow):
    def run_local_server(self, **kw):
        _log(call="run_local_server", **{k: v for k, v in kw.items() if not k.endswith("message")})
        if os.environ.get("FAKE_FLOW_TIMEOUT"):
            None.replace("http", "https")  # the real flow: no request arrived before the timeout
        return Creds(self.scopes)
'''


def install(folder, broken=False):
    pkg = pathlib.Path(folder) / "google_auth_oauthlib"
    pkg.mkdir(parents=True, exist_ok=True)
    (pkg / "__init__.py").write_text("raise ImportError('not installed')\n" if broken else "")
    (pkg / "flow.py").write_text(FLOW)
    return str(folder)
