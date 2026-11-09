"""The GitHub side of a bug report, through the owner's own `gh` login. Nothing here posts unless
post() is called, and the CLI calls it only after the approval check.

available() -> None or why not (no gh, not logged in). duplicates(repo, title, signature) ->
[{number, title, url, state, score}] best first: a search with the REDACTED words only (the query
itself goes to GitHub), ranked locally by word overlap and similarity. post(repo, kind, title,
body_file, number, dry_run) -> (exit code, the URL or the planned command).
"""
import difflib
import json
import re
import shutil
import subprocess

STOP = set("the a an and or of to in on for with is was not no it this that be at by from as are "
           "error failed fails when after before then out into cannot can't does doesn't".split())


def _gh(args, timeout=30):
    try:
        return subprocess.run(["gh", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(args, 99, "", str(exc))


def available():
    if not shutil.which("gh"):
        return "the gh command is not installed"
    if _gh(["auth", "status"], timeout=15).returncode != 0:
        return "gh is not logged in (gh auth login)"
    return None


def words(text):
    out = []
    for w in re.findall(r"[A-Za-z_][A-Za-z0-9_.-]{2,}", re.sub(r"<[^>]*>", " ", text)):
        w = w.strip(".-").lower()
        if w and w not in STOP and w not in out:
            out.append(w)
    return out


def score(ours, theirs):
    a, b = set(words(ours)), set(words(theirs))
    overlap = len(a & b) / max(1, min(len(a), len(b)))
    return round(max(overlap, difflib.SequenceMatcher(None, ours.lower(), theirs.lower()).ratio()), 2)


SAFE_WORD = re.compile(r"^[a-z][a-z_.-]{2,23}$")  # no digits: a missed secret or id almost always has some


def query_words(title, signature):
    """The search query leaves the machine BEFORE the owner's yes: redacted words only, letters only,
    at most six, from the title and the first line of the signature."""
    first = signature.strip().splitlines()[0] if signature.strip() else ""
    return [w for w in words(title + " " + first) if SAFE_WORD.match(w)][:6]


def duplicates(repo, title, signature, limit=5):
    query = " OR ".join(query_words(title, signature))
    if not query:
        return []
    r = _gh(["search", "issues", "--repo", repo, "--limit", "20", "--json", "number,title,url,state", "--", query])
    try:
        found = json.loads(r.stdout or "[]") if r.returncode == 0 else []
    except ValueError:
        found = []
    ours = title + " " + signature
    ranked = [dict(f, score=score(ours, f.get("title", ""))) for f in found if isinstance(f, dict)]
    return sorted([f for f in ranked if f["score"] >= 0.3], key=lambda f: -f["score"])[:limit]


def post(repo, kind, title, body_file, number=None, dry_run=False):
    if kind == "comment":
        cmd = ["issue", "comment", str(int(number)), "--repo", repo, "--body-file", str(body_file)]
    else:
        cmd = ["issue", "create", "--repo", repo, "--title", title, "--body-file", str(body_file)]
    if dry_run:
        return 0, "gh " + " ".join(json.dumps(c) if " " in c else c for c in cmd)
    r = _gh(cmd, timeout=60)
    if r.returncode != 0:
        return 1, (r.stderr or r.stdout).strip()[:300]
    urls = re.findall(r"https://github\.com/\S+", r.stdout)
    return 0, urls[-1] if urls else r.stdout.strip()[:200]
