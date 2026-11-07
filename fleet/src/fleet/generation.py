"""Az ágens processz-generációja (pid + indulási idő): a `fleet stop` ezt jegyzi
fel leállítás előtt, a `fleet wait-up` ehhez méri, hogy ÚJ processz jött-e."""
from __future__ import annotations
import json
from pathlib import Path

from fleet import maintenance


def _generation(entry: dict) -> dict | None:
    """A futó processz-generáció (a doctor process-jelének mércéje: pid + indulási idő)."""
    from fleet import signals
    sg = signals.process_signal(entry)
    return {"pid": sg.data.get("pid"), "started_s": sg.data.get("started_s")} if sg.state == "up" else None


def _gen_file(agent: str) -> Path:
    return maintenance._root() / ".gen" / agent


def mark_generation(agent: str, gen: dict | None) -> None:
    """A stop előtt futott generáció: a wait-up ehhez képest mondja, hogy ÚJ jött."""
    p = _gen_file(agent)
    if gen is None:
        clear_generation(agent)
        return
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(gen))


def read_generation(agent: str) -> dict | None:
    try:
        d = json.loads(_gen_file(agent).read_text())
        return d if isinstance(d, dict) else None
    except (OSError, ValueError):
        return None


def clear_generation(agent: str) -> None:
    _gen_file(agent).unlink(missing_ok=True)
