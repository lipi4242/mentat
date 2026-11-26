"""Audit: leletenként egy todo-tétel, stabil kulccsal (idempotens). A sink cserélhető."""
from __future__ import annotations
import hashlib
import subprocess
from typing import Protocol

from fleet.fleet_map import Finding


class TodoSink(Protocol):
    def emit(self, key: str, title: str, description: str) -> None: ...


def stable_key(f: Finding) -> str:
    return "fleet-map-audit-" + hashlib.sha256(f"{f.code}|{f.agent or ''}|{f.subject}".encode()).hexdigest()[:16]


class MentatTodoSink:
    """Az éles sink: `mentat-todo item new --idem <kulcs>` (ugyanaz a kulcs nem duplikál)."""

    def __init__(self, project: str, pm: str, binary: str = "mentat-todo"):
        self.project, self.pm, self.binary = project, pm, binary

    def emit(self, key: str, title: str, description: str) -> None:
        subprocess.run([self.binary, "item", "new", "--project", self.project, "--pm", self.pm,
                        "--title", title, "--description", description, "--idem", key],
                       check=True, capture_output=True, text=True, timeout=60)


def file_todos(findings: list[Finding], sink: TodoSink) -> int:
    n = 0
    for f in findings:
        if f.severity == "error":
            sink.emit(stable_key(f), f"fleet map audit: {f.code}" + (f" ({f.agent})" if f.agent else ""), f.message)
            n += 1
    return n
