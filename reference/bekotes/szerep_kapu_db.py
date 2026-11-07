"""Direct database writes from the shell (friction log #26), for szerep_kapu.

writes(name, words, cwd) -> True when the command may write a database. Open lists, not
deny lists: under `wrangler d1` only list / info / export and an `execute` whose SQL only
reads; sqlite3 / psql / mysql / mariadb only with SQL that only reads, and sqlite3 dot
commands only from READ_DOT. SQL that cannot be read (none given = interactive or stdin, a
missing file) counts as a write. A keyword in a comment or a string counts too: the gate
errs toward asking. Runners are unwrapped: npx / pnpm / bunx / yarn / `npm exec|x`, and an
`@version` suffix (`wrangler@3`).
"""
import os
import re

WRITE = re.compile(r"\b(INSERT|UPDATE|DELETE|REPLACE|UPSERT|MERGE|DROP|ALTER|CREATE|ATTACH|DETACH|"
                   r"PRAGMA|TRUNCATE|GRANT|REVOKE|VACUUM|REINDEX|COPY|LOAD|RENAME)\b", re.I)
RUNNERS = {"npx", "pnpm", "bunx", "yarn", "pnpx", "npm"}
D1_READ = {"list", "info", "export"}
READ_DOT = {".tables", ".table", ".schema", ".fullschema", ".dump", ".mode", ".headers", ".header",
            ".indexes", ".indices", ".databases", ".help", ".show", ".width", ".timer", ".stats",
            ".eqp", ".explain", ".print", ".quit", ".exit", ".separator", ".nullvalue", ".dbinfo"}
SQL_FLAGS = {"wrangler": ("--command",), "psql": ("-c", "--command"), "mysql": ("-e", "--execute"),
             "mariadb": ("-e", "--execute"), "sqlite3": ("-cmd",)}
FILE_FLAGS = ("--file", "-f")


def _unwrap(name, words):
    """`npx --yes wrangler@3 d1 …`, `npm exec -- wrangler …` -> ("wrangler", [wrangler, d1, …])."""
    if name in RUNNERS:
        rest = words[1:]
        if name == "npm":
            if not rest or rest[0] not in ("exec", "x"):
                return name, words
            rest = rest[1:]
        rest = [w for w in rest if w not in ("exec", "dlx")]
        while rest and rest[0].startswith("-"):
            rest = rest[2:] if rest[0] in ("-p", "--package") else rest[1:]  # -p takes a value
        words = rest
        name = os.path.basename(words[0]) if words else ""
    base = re.sub(r"(?<=.)@[^/]*$", "", name)  # wrangler@3 -> wrangler (not a scope like @org/x)
    return base, ([base] + words[1:] if words else words)


def _read(path, cwd):
    try:
        with open(os.path.join(cwd or ".", os.path.expanduser(path)), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _texts(words, cwd, sql_flags, redirects):
    """(SQL texts, unreadable?) from the flags, the files and (redirects) a bare `x.sql`."""
    texts, bad, i = [], False, 1
    while i < len(words):
        w = words[i]
        key, _, val = w.partition("=")
        if key in sql_flags or key in FILE_FLAGS:
            val = val or (words[i + 1] if i + 1 < len(words) else "")
            i += 1 if "=" in w else 2
            got = _read(val, cwd) if key in FILE_FLAGS else val
            bad, texts = bad or got is None, texts + ([got] if got is not None else [])
            continue
        if redirects and w.endswith(".sql") and not w.startswith("-"):  # `< fix.sql`
            got = _read(w, cwd)
            bad, texts = bad or got is None, texts + ([got] if got is not None else [])
        i += 1
    return texts, bad


def _writes_sql(text):
    for line in text.splitlines():
        s = line.strip()
        if s.startswith(".") and s.split()[0].lower() not in READ_DOT:
            return True  # .import, .restore, .read, .output, … : not on the read list
    return bool(WRITE.search(text))


def writes(name, words, cwd):
    name, words = _unwrap(name, words)
    if name == "wrangler":
        sub = [w for w in words[1:] if not w.startswith("-")]
        if sub[:1] != ["d1"]:
            return False
        if sub[1:2] and sub[1] in D1_READ:
            return False
        if sub[1:2] != ["execute"]:
            return True  # delete, create, time-travel restore, migrations apply, …
    elif name not in SQL_FLAGS:
        return False
    texts, bad = _texts(words, cwd, SQL_FLAGS[name], redirects=name != "wrangler")
    if name == "sqlite3":  # sqlite3 [opts] DB "SQL": the SQL is the second plain argument
        args, skip = [], False
        for w in words[1:]:
            if skip:
                skip = False
            elif w == "-cmd":
                skip = True
            elif not w.startswith("-") and not w.endswith(".sql"):
                args.append(w)
        texts += args[1:]
    return bad or not texts or any(_writes_sql(t) for t in texts)
