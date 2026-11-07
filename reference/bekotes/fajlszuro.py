"""File-tree filters for the inventory: exclusions, doc paths, forbidden globs.

Forbidden globs (bekotes.json source "tiltott": [...]) use our own subset:
`**` any depth, `*` and `?` within one path segment. A path is forbidden if
the glob matches the whole path or any trailing part of it, so
"foto-001.jpg" also forbids "a/b/foto-001.jpg". Matching ignores case, because a
case-insensitive filesystem opens UGYFELEK/x as ugyfelek/x.
"""
import fnmatch
import pathlib
import re

EXCLUDE_DIRS = {"node_modules", ".git", "dist", "build", ".next", ".wrangler", "__pycache__"}
EXCLUDE_NAMES = {"package-lock.json"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tar",
              ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4", ".mov", ".bin", ".exe",
              ".so", ".dylib", ".pyc", ".sqlite", ".db", ".heic"}
# Never read by `olvas`, in any source kind, whatever bekotes.json says.
SECRET_GLOBS = [".env*", "*.pem", "*.key", "id_*", ".npmrc", "credentials*"]


def excluded(path):
    parts = path.split("/")
    name = parts[-1]
    return (bool(EXCLUDE_DIRS & set(parts[:-1])) or name in EXCLUDE_NAMES
            or name.endswith(".lock") or is_binary(name))


def is_binary(path):
    return pathlib.PurePath(path).suffix.lower() in BINARY_EXT


def is_doc(path):
    name = path.split("/")[-1]
    return (path in ("AGENTS.md", "CLAUDE.md") or name == "_meta.md"
            or fnmatch.fnmatch(path, "README*") or
            (path.startswith("docs/") and path.endswith(".md")))


def _regex(glob):
    out, i = [], 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out), re.I)  # case-insensitive filesystems


def tiltott(path, globs):
    """True if any glob matches the path or one of its trailing parts."""
    parts = path.split("/")
    tails = ["/".join(parts[i:]) for i in range(len(parts))]
    return any(_regex(g).fullmatch(t) for g in globs or () for t in tails)


def globs_of(src):
    g = src.get("tiltott")
    if g is None:
        return []
    if not (isinstance(g, list) and all(isinstance(x, str) and x for x in g)):
        raise ValueError("a 'tiltott' globok listája kell legyen: %s" % src.get("name"))
    return g
