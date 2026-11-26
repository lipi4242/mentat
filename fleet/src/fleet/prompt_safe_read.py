"""Biztonságos fájlolvasás a prompt-hash-hez: a reconcile-kör nem akadhat meg.

A figyelt fájlokat (és az @include-célokat) az ágens repója és konfigja adja,
tehát az olvasás nem bízhat bennük. Egy FIFO-ra mutató include blokkoló
open()-nel megállítaná a teljes 5 perces kört (minden ágensét), egy óriásfájl
vagy egy végtelen skill-fa memóriát és időt enne. Ezért:
  * olvasás előtt os.stat: csak szabályos fájl (S_ISREG); minden más jelölő
  * MAX_BYTES fölött nincs olvasás: a hash helyett méret+mtime jelölő
  * os.open O_NONBLOCK-kal, utána fstat újra (a stat és az open közti csere ellen)
  * a fa-bejárás symlinket nem követ, és MAX_FILES-nál bejárás KÖZBEN áll meg
  * az @include-cél resolve() után csak a megengedett gyökereken belül számít
"""
from __future__ import annotations
import hashlib
import os
import stat
from pathlib import Path

MAX_BYTES = 1024 * 1024


def confined(p: Path, bases: list[Path]) -> Path | None:
    """A feloldott út, ha valamelyik gyökéren belül van; különben None."""
    try:
        r = p.resolve()
    except (OSError, RuntimeError):
        return None
    for b in bases:
        try:
            r.relative_to(b.resolve())
            return r
        except (ValueError, OSError, RuntimeError):
            continue
    return None


def read_bytes(p: Path) -> tuple[str | None, bytes | None]:
    """(jelölő, None) vagy (None, a beolvasott bájtok). Hiányzó fájl: (None, None).
    A hívó EZT a bájtsort használja (hash, JSON): egy második olvasás már mást láthatna."""
    try:
        st = os.stat(p)
    except OSError:
        return None, None
    if not stat.S_ISREG(st.st_mode):
        return f"nem-fajl:{stat.S_IFMT(st.st_mode):o}", None
    if st.st_size > MAX_BYTES:
        return f"nagy:{st.st_size}:{st.st_mtime_ns}", None
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK)
    except OSError:
        return "olvashatatlan", None
    try:
        st2 = os.fstat(fd)
        if not stat.S_ISREG(st2.st_mode) or st2.st_size > MAX_BYTES:
            return f"nem-fajl:{stat.S_IFMT(st2.st_mode):o}", None
        data = os.read(fd, MAX_BYTES + 1)
    except OSError:
        return "olvashatatlan", None
    finally:
        os.close(fd)
    if len(data) > MAX_BYTES:           # az fstat óta nőtt
        return f"nagy:{len(data)}", None
    return None, data


def digest(p: Path) -> tuple[str | None, str | None]:
    """(hash vagy jelölő, szöveg ha kis .md). Hiányzó fájl: (None, None)."""
    mark, data = read_bytes(p)
    if data is None:
        return mark, None
    text = data.decode("utf-8", "replace") if p.suffix == ".md" else None
    return hashlib.sha256(data).hexdigest(), text


def walk(root: Path, limit: int) -> list[Path]:
    """A fa szabályos fájljai rendezve, symlink nélkül; legfeljebb `limit` darab,
    és a bejárás a limitnél megáll (nem utólag vág)."""
    out: list[Path] = []
    try:
        if not stat.S_ISDIR(os.lstat(root).st_mode):
            return out
    except OSError:
        return out
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            p = Path(dirpath) / name
            try:
                if not stat.S_ISREG(os.lstat(p).st_mode):
                    continue          # symlink, FIFO, eszköz: nem prompt
            except OSError:
                continue
            out.append(p)
            if len(out) >= limit:
                return out
    return out
