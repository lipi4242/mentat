"""Which token permissions THIS project's deploy needs, read from its wrangler.toml (stdlib).

probes(path) -> [(permission row, probe path)]: Workers Scripts and Access always (the product
protects every page with Access), plus one row per binding kind the file declares: D1
(d1_databases), Workers KV Storage (kv_namespaces), Workers R2 Storage (r2_buckets), Queues
(queues). mentat_cf_token.py --check --for wrangler.toml probes each and names every missing
row at once, before the deploy (mentat_web.py deploy runs it first). A GET probe proves the
token can see the resource; a Read-only row instead of Edit still shows only at the deploy.
"""
import pathlib
import re

BASE = [("Account · Workers Scripts · Edit", "/accounts/{a}/workers/scripts"),
        ("Account · Access: Apps and Policies · Edit", "/accounts/{a}/access/apps")]
KINDS = {"d1_databases": ("Account · D1 · Edit", "/accounts/{a}/d1/database"),
         "kv_namespaces": ("Account · Workers KV Storage · Edit", "/accounts/{a}/storage/kv/namespaces"),
         "r2_buckets": ("Account · Workers R2 Storage · Edit", "/accounts/{a}/r2/buckets"),
         "queues": ("Account · Queues · Edit", "/accounts/{a}/queues")}


def declared(text):
    """Binding kinds in a wrangler.toml: [[d1_databases]] tables or `d1_databases = [...]` keys."""
    try:
        import tomllib
        doc = tomllib.loads(text)
        found = {k for k in KINDS if doc.get(k)}
        for env in (doc.get("env") or {}).values():
            found |= {k for k in KINDS if isinstance(env, dict) and env.get(k)}
        return found
    except (ImportError, ValueError):
        return {k for k in KINDS if re.search(r"^\s*(\[\[(env\.\w+\.)?%s\]\]|%s\s*=)" % (k, k), text, re.M)}


def probes(path):
    p = pathlib.Path(path)
    kinds = declared(p.read_text(encoding="utf-8")) if p.is_file() else set()
    return BASE + [KINDS[k] for k in KINDS if k in kinds]
