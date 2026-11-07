"""`status`: the backend, the brain folder, whether the admin is bound AND
answering, and what happens when it does not."""
import urllib.error
import urllib.request

import mentat_manifest as mm

OFFLINE = ("if the admin is down: every case command refuses (exit 3, \"admin unavailable\", nothing written) — "
           "there is no queue and no fall-back to the markdown files; start the admin "
           "(admin/worker: npm run status says why), then rerun")


def answering(url):
    """True when something answers on the admin's URL (any HTTP status), False when nothing does."""
    try:
        urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=2).close()
    except urllib.error.HTTPError:
        return True
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return True


def text(root, brain, backend):
    local = (mm.local(root) or {}).get("admin") or {}
    url = local.get("url")
    lines = ["cases.backend: %s" % backend, "brain: %s/cases" % brain]
    if not url:
        lines.append("admin: not connected")
    else:
        lines.append("admin: connected (%s) — %s" % (url, "answering" if answering(url) else "NOT answering"))
    if backend == "admin" and not url:
        lines.append("ERROR: cases.backend is admin but no admin is connected — case commands will fail")
    if backend == "admin":
        lines.append(OFFLINE)
    return "\n".join(lines)
