"""cases.backend: markdown — the frontmatter of <brain>/cases/*.md is the record."""
import sys
from pathlib import Path

import fmwrite
import occurrence as moved
import frontmatter
import recurrence as rec
import series
from common import OPEN, STATUSES, TRACKED, CasesError, NotFound, case, ulid, slug


def scan(root, brain):
    """[(path, frontmatter, text)] of every case file; unreadable ones are reported."""
    folder = root / brain / "cases"
    out = []
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        if f.name.startswith("_"):
            continue
        text = f.read_text(encoding="utf-8")
        try:
            fm = frontmatter.parse(text)
        except frontmatter.FrontmatterError as e:
            raise CasesError("%s: %s" % (f.relative_to(root).as_posix(), e))
        if fm.get("type") == "case":
            out.append((f, fm, text))
    return out


def write(path, text):
    tmp = path.with_name("." + path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def check(c):
    """The admin's cross-field rules, so markdown mode refuses the same things."""
    if not c["title"]:
        raise CasesError("title is required")
    if c["status"] not in STATUSES:
        raise CasesError("status must be one of " + ", ".join(STATUSES))
    for k in ("due_at", "anchor_at"):
        if c[k] is not None and not rec.is_date(c[k]):
            raise CasesError("%s must be a YYYY-MM-DD date" % k)
    if c["recurrence"]:
        if not rec.parse(c["recurrence"]):
            raise CasesError("recurrence must be monthly:<1-31>, quarterly:<1-31>, yearly:<MM-DD> or weekly:<mon..sun>")
        if not c["anchor_at"]:
            raise CasesError("anchor_at is required with a recurrence (the first due date)")


class Markdown:
    name = "markdown"

    def __init__(self, root, brain):
        self.root, self.brain = Path(root), brain

    def _cases(self):
        out = {}
        for path, fm, text in scan(self.root, self.brain):
            rel = path.relative_to(self.root).as_posix()
            c = case(fm, id=str(fm.get("case_id") or rel), brain_ref=rel)
            try:
                c["due_at"] = series.due_of(c, c.get("due_at"))
            except CasesError as e:
                print("skipped %s: %s" % (rel, e), file=sys.stderr)
                continue
            c["context"], c["_path"] = fmwrite.context(text), path
            out[c["id"]] = c
        return out

    def list(self, want):
        return [c for c in self._cases().values() if c["status"] in want]

    def due(self, until):
        return series.due_items(self._cases().values(), until)

    def get(self, cid):
        c = self._cases().get(cid)
        if not c:
            raise NotFound("no case %s" % cid)
        return c

    def put(self, cid, fields, file=None, title=None):
        """Create (cid None) or update; `fields` are tracked keys, None clears."""
        if cid is None:
            path = Path(file) if file else self._new_path(title or fields.get("title") or "")
            text = path.read_text(encoding="utf-8") if path.exists() else ""
            cid = ulid()
            text = fmwrite.set_fields(text, {"type": "case", "case_id": cid})
            old = case({}, id=cid)
        else:
            old = self.get(cid)
            path, text = old["_path"], old["_path"].read_text(encoding="utf-8")
        new = {**old, **fields}
        check(new)
        if new["recurrence"]:
            if not rec.anchor_ok(new["anchor_at"], new["recurrence"]):
                raise CasesError("anchor_at %s is not a date of %s" % (new["anchor_at"], new["recurrence"]))
            new["due_at"] = series.due_of(new, new.get("due_at"), strict="due_at" in fields)
        updates = {k: (fmwrite.DELETE if new.get(k) in (None, [], {}) else new[k])
                   for k in TRACKED if k in fields or k in ("status", "due_at")}
        write(path, fmwrite.set_fields(text, updates))
        return self.get(cid)

    def close(self, cid, day=None, status="done", done_at=None, note=None):
        c = self.get(cid)
        if not c["recurrence"]:
            if c["status"] not in OPEN:
                return c, True
            return self.put(cid, {"status": "done"}), False
        kind, slot = moved.close_slot(c["anchor_at"], c["recurrence"], c["due_at"], day or c["due_at"],
                                      {o["due_at"] for o in c["occurrences"]})
        if kind == "already":
            return c, True
        if c["status"] not in OPEN:
            raise CasesError("the case is %s — reopen it before closing an occurrence" % c["status"])
        if kind == "off":
            raise CasesError(slot)
        if kind == "later":
            raise CasesError("only the earliest open occurrence can be closed: %s" % c["due_at"])
        day = slot
        occ = c["occurrences"] + [{"due_at": day, "status": status, "done_at": done_at, "note": note}]
        return self.put(cid, {"occurrences": occ}), False

    def _new_path(self, title):
        folder = self.root / self.brain / "cases"
        folder.mkdir(parents=True, exist_ok=True)
        base, n = slug(title), 1
        path = folder / (base + ".md")
        while path.exists():
            n += 1
            path = folder / ("%s-%d.md" % (base, n))
        return path
