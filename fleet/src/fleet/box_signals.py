"""Megszakítás a box-upgrade alatt: a megszakadt ssh (SIGHUP) és a SIGTERM ugyanúgy
KeyboardInterrupt, mint a Ctrl-C — így a visszaállítás, a timerek indítása és a
zár feloldása lefut. Az első jelzés után a többit elnyeljük, amíg a
helyreállítás tart (egy második Ctrl-C ne vágja félbe); a gyerekfolyamatok ezt
örökölik, így a helyreállító `fleet install` sem hal meg egy újabb SIGHUP-tól.
"""
from __future__ import annotations
import contextlib
import signal

SIGNALS = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)


def _handler(signum, _frame):
    for s in SIGNALS:
        signal.signal(s, signal.SIG_IGN)
    raise KeyboardInterrupt(f"jelzés: {signal.Signals(signum).name}")


@contextlib.contextmanager
def interruptible():
    saved = {}
    try:
        for s in SIGNALS:
            saved[s] = signal.signal(s, _handler)
    except ValueError:   # nem a fő szálon fut (teszt): nincs mit beállítani
        pass
    try:
        yield
    finally:
        for s, h in saved.items():
            signal.signal(s, h)
