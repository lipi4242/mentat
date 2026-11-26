"""A titok-írás közös őrei (move, copy, put): héj-semleges env-érték, a dirfd-láncos írás, és a nyugta,
amelynek hibája kimondja, hogy a cél már megváltozott. Értéket egyik üzenet sem tartalmaz.

write_secret: a HOME-tól (HOME-on kívüli célnál a gyökértől) mappánként `O_DIRECTORY|O_NOFOLLOW`-val
nyitja a célmappát, és az olvasás, az ideiglenes fájl, az fsync és a rename mind ezen a dirfd-n fut.
Ha az ellenőrzés után egy szülőmappa symlinkre cserélődik, az írás hibával megáll, nem megy ki rajta.
"""
from __future__ import annotations
import errno
import json
import os
import re
import secrets
import stat
from pathlib import Path

from fleet import titok_hely as H
from fleet.titok_jovahagy import Refused

# a unit `sh -c '. fájl'`-lal tölti be: ezen kívül minden karakter héj-aktív lehet ($(…), `, szóköz, \x0b)
SAFE_VALUE = re.compile(r"[A-Za-z0-9._+/=:@-]+")  # fullmatch: a `$` sortörés előtt is illeszkedne; `~` = HOME-kiterjesztés


_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_DIR = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | _CLOEXEC


class ReceiptFailed(Exception):
    """A cél megváltozott, de a nyugta nem íródott: az üzenet ezt mondja ki, érték nélkül."""


def check_env_value(name: str, value: str) -> None:
    if not SAFE_VALUE.fullmatch(value):
        raise Refused(f"a(z) {name} értékében nem megengedett karakter van (env-sorba csak A–Z a–z 0–9 "
                      "és . _ + / = : @ - mehet); más értéket egész fájlként vigyél (--name '*')")


def record(home: Path, receipt: dict) -> None:
    try:
        H.append_line(H.receipts_path(home), json.dumps(receipt, ensure_ascii=False))
    except OSError as e:
        raise ReceiptFailed(f"a cél MEGVÁLTOZOTT ({receipt['dest_path']}), de a nyugta NEM íródott "
                            f"({type(e).__name__}); jegyezd fel kézzel: {receipt['op']} {receipt['name']}, "
                            f"hmac {receipt['hmac']}") from None


def _open_dir(part: str, fd: int) -> int:
    try:
        return os.open(part, _DIR, dir_fd=fd)
    except FileNotFoundError:
        os.mkdir(part, 0o700, dir_fd=fd)
        return os.open(part, _DIR, dir_fd=fd)
    except OSError as e:
        if e.errno in (errno.ELOOP, errno.ENOTDIR):
            raise OSError(e.errno, f"az út egy eleme symlink vagy nem mappa: {part} — symlinken át nem írok") from None
        raise


def _open_parent(home: Path, path: Path) -> int:
    """A cél szülőmappájának dirfd-je; a HOME (ill. a gyökér) alatt minden elem O_NOFOLLOW-val nyílik."""
    home = Path(os.path.abspath(home))
    base = home if home in path.parents else Path(path.anchor)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | _CLOEXEC)
    try:
        for part in path.parent.relative_to(base).parts:
            nxt = _open_dir(part, fd)
            os.close(fd)
            fd = nxt
    except BaseException:
        os.close(fd)
        raise
    return fd


def _read_at(dfd: int, name: str) -> str | None:
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | _CLOEXEC, dir_fd=dfd)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "rb") as f:
        return f.read().decode()


def write_secret(home: Path, path: Path, data, mode: int = 0o600) -> Path:
    """0600 (vagy `mode`), atomikus, symlinkre és symlinken át nem ír. `data`: bytes/str, vagy egy
    függvény, ami a cél mostani szövegét (None, ha nincs) kapja a dirfd-n át, és az újat adja vissza."""
    path = Path(os.path.abspath(path))
    name = path.name
    dfd = _open_parent(home, path)
    try:
        try:
            if stat.S_ISLNK(os.stat(name, dir_fd=dfd, follow_symlinks=False).st_mode):
                raise OSError(errno.ELOOP, f"symlinkre nem írok: {path}")
        except FileNotFoundError:
            pass
        if callable(data):
            data = data(_read_at(dfd, name))
        tmp = f".{name}.{secrets.token_hex(6)}"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | _CLOEXEC, 0o600, dir_fd=dfd)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data.encode() if isinstance(data, str) else data)
                f.flush()
                os.fchmod(f.fileno(), mode)
                os.fsync(f.fileno())
            os.replace(tmp, name, src_dir_fd=dfd, dst_dir_fd=dfd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=dfd)
            except FileNotFoundError:
                pass
            raise
        os.fsync(dfd)
    finally:
        os.close(dfd)
    return path
