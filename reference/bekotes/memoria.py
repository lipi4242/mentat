"""Stage old agent memories (redacted), print an approval list, apply approved ones."""
import hashlib
import json
import pathlib
import re
import os
import subprocess

import fajlszuro as fs
import szuro

LOG, APPROVAL = "kihagyasi-naplo.json", "jovahagyasra.json"


def _sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def _ensure_ignored(stage):
    stage = pathlib.Path(stage).resolve()
    parent = stage.parent
    parent.mkdir(parents=True, exist_ok=True)
    try:
        r = subprocess.run(["git", "-C", str(parent), "rev-parse", "--is-inside-work-tree"],
                           capture_output=True, text=True, env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
        if r.returncode != 0:
            return
        ign = subprocess.run(["git", "-C", str(parent), "check-ignore", "-q", str(stage)], env=dict(os.environ, GIT_NO_LAZY_FETCH="1"))
    except OSError:  # git missing: treat as not in a git tree
        return
    if ign.returncode != 0:
        (parent / ".gitignore").write_text("*\n")


def safe_name(name, used=()):
    """The original name, unless it carries personal data: then a unique, shell-safe placeholder
    (kinds + a short hash of the original), e.g. a@example.com.md -> email-1f3a.md."""
    stem = name[:-3] if name.endswith(".md") else name
    red, hits = szuro.redact(stem)
    if not hits:
        return name
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", re.sub(r"<([a-z]+)>", r"\1", red)).strip("-.") or "nev"
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    for n in (4, 8, 64):
        cand = "%s-%s.md" % (base, digest[:n])
        if cand not in used:
            return cand
    return cand


def stage(src_dir, stage_dir, globs=()):
    """globs: the source's forbidden globs; matching files are never read, only logged."""
    stage_dir = pathlib.Path(stage_dir)
    out = stage_dir / "memoria"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.md"):  # idempotent: nothing stale survives a re-stage
        old.unlink()
    for name in (APPROVAL, LOG):
        (stage_dir / name).unlink(missing_ok=True)
    _ensure_ignored(stage_dir)
    log = []
    for p in sorted(pathlib.Path(src_dir).glob("*.md")):
        if p.name == "MEMORY.md":
            continue
        name = safe_name(p.name, {e["file"] for e in log})  # a file name can carry personal data, too
        if fs.tiltott(p.name, globs):
            log.append({"file": name, "ok": "tiltott"})
            continue
        if p.is_symlink():  # never followed: it could alias a forbidden file
            log.append({"file": name, "ok": "symlink"})
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            log.append({"file": name, "ok": "olvashatatlan"})
            continue
        if szuro.suspicious(text):
            log.append({"file": name, "ok": "gyanus-utasitas"})
            continue
        clean, hits = szuro.redact(text)
        (out / name).write_text(clean, encoding="utf-8")
        log.append({"file": name, "kitakarva": hits})
    (stage_dir / LOG).write_text(json.dumps(log, ensure_ascii=False, indent=1))


def _description(path):
    m = re.search(r"^description:\s*(.+)$", pathlib.Path(path).read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else "-"


def lista(stage_dir):
    stage_dir = pathlib.Path(stage_dir)
    log = json.loads((stage_dir / LOG).read_text())
    lines, hashes, skipped = [], {}, []
    for e in log:
        if "ok" in e:
            skipped.append("  %s — %s" % (e["file"], e["ok"]))
            continue
        p = stage_dir / "memoria" / e["file"]
        full = _sha(p)
        hashes[e["file"]] = full
        k = ", ".join("%s×%d" % kv for kv in sorted(e["kitakarva"].items())) or "-"
        lines.append("[ ] %s %s — %s (kitakarva: %s)" % (e["file"], full[:8], _description(p), k))
    (stage_dir / APPROVAL).write_text(json.dumps(hashes, indent=1))
    if skipped:
        lines += ["", "Kihagyva:"] + skipped
    return "\n".join(lines)


def alkalmaz(stage_dir, approved, dest_dir):
    stage_dir = pathlib.Path(stage_dir)
    ap = stage_dir / APPROVAL
    listed = json.loads(ap.read_text()) if ap.exists() else {}
    for n in approved:
        p = stage_dir / "memoria" / n
        if n != pathlib.Path(n).name or n not in listed or not p.is_file():
            raise ValueError("ismeretlen vagy nem listázott fájl: %s" % n)
        if _sha(p) != listed[n]:
            raise ValueError("a lista óta megváltozott: %s" % n)
        if szuro.redact(p.read_text(encoding="utf-8"))[1] or szuro.suspicious(p.read_text(encoding="utf-8")):
            raise ValueError("a szűrő találatot ad: %s" % n)
    dest = pathlib.Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for n in approved:
        (dest / n).write_bytes((stage_dir / "memoria" / n).read_bytes())
