"""flotta-menedzser: a végrehajtó Worker-hívásai (a box tokenjével + az átvétel titkával és fence-ével).

Minden hívás (ok, válasz): ok csak 200-ra. Nem elérhető Worker → (False, {"code": "unreachable"}).
A hívó a `code`-ból dönt (stale, expired, draining, must_assess, budget…); a titok nem kerül ki.
"""
from __future__ import annotations
import urllib.request

from fleet import flotta_http, flotta_report


class Worker:
    def __init__(self, incident: str, claim: dict, cfg: tuple[str, str] | None = None,
                 opener=urllib.request.urlopen):
        self.incident, self.fence, self.secret = incident, claim["fence"], claim["claim"]
        self.cfg = cfg or flotta_report.config()
        self.opener = opener

    def _post(self, path: str, body: dict) -> tuple[bool, dict]:
        if self.cfg is None:
            return False, {"code": "unconfigured"}
        status, res, info = flotta_http.call("POST", self.cfg[0], f"/api/flotta/v1/incidents/{self.incident}{path}",
                                             self.cfg[1], {"fence": self.fence, "claim": self.secret, **body}, self.opener)
        if status is None:
            return False, {"code": "unreachable", "info": info}
        res = dict(res or {})
        res.setdefault("code", "ok" if status == 200 else f"http-{status}")
        return status == 200 and res.get("ok", True) is not False, res

    def check(self, op_id: str, step: str, target: str):
        return self._post("/ops/check", {"op_id": op_id, "step": step, "target": target})

    def intent(self, op_id: str, step: str, target: str):
        return self._post(f"/ops/{op_id}/intent", {"step": step, "target": target})

    def result(self, op_id: str, outcome: str, summary: str, assessment: str | None = None,
               step: str | None = None, target: str | None = None):
        body = {"outcome": outcome, "summary": summary}
        if step and target:   # a szándék nélküli „busy” naplósorhoz (a Worker így tudja, mire várt)
            body.update(step=step, target=target)
        if assessment:
            body["assessment"] = assessment
        return self._post(f"/ops/{op_id}/result", body)

    def verify_start(self):
        return self._post("/verify/start", {})

    def verify_result(self, nonce: str, boot_id: str, green: bool, summary: str):
        return self._post("/verify/result", {"nonce": nonce, "boot_id": boot_id, "green": green, "summary": summary})
