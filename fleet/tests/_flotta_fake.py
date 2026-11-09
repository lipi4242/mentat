"""flotta-menedzser tesztsegéd: hamis urlopen — rögzíti a kéréseket, és előre megadott válaszokat ad."""
import io
import json
import urllib.error


class Resp(io.BytesIO):
    def __init__(self, status, body):
        super().__init__(json.dumps(body).encode())
        self.status = status
    def __enter__(self): return self
    def __exit__(self, *a): return False


class Opener:
    def __init__(self, *answers):
        self.answers, self.calls = list(answers), []

    def __call__(self, req, timeout=None):
        self.calls.append({"method": req.get_method(), "url": req.full_url, "headers": dict(req.header_items()),
                           "body": json.loads(req.data) if req.data else None})
        status, body = self.answers.pop(0) if self.answers else (200, {})
        if status is None:
            raise urllib.error.URLError("nincs hálózat")
        if status >= 400:
            raise urllib.error.HTTPError(req.full_url, status, "x", {}, io.BytesIO(json.dumps(body).encode()))
        return Resp(status, body)
