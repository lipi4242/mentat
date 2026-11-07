"""A unit a repó .mentat/model.env-jét (MENTAT_MODEL) követi, ha van — az agy modellváltója
(skills/model) ezt írja. Nélküle a registry modellje marad. A rendert ténylegesen lefuttatjuk:
a sh -c törzsét egy hamis claude-dal, ami csak kiírja, milyen --model-t kapott."""
from __future__ import annotations
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import registry, render, TEMPLATES_DIR  # noqa: E402

TMPL = (TEMPLATES_DIR / "agent.service.tmpl").read_text()


def model_seen(model_env: str | None, registry_model: str = "claude-opus-5-5") -> str:
    home = Path(tempfile.mkdtemp())
    work = home / "agent"
    (work / ".mentat").mkdir(parents=True)
    (home / ".local" / "bin").mkdir(parents=True)
    fake = home / ".local" / "bin" / "claude"
    fake.write_text('#!/bin/sh\nwhile [ $# -gt 0 ]; do [ "$1" = --model ] && echo "$2"; shift; done\n')
    fake.chmod(0o755)
    if model_env is not None:
        (work / ".mentat" / "model.env").write_text(model_env)
    entry = registry.normalize({"agent": "probe", "workdir": str(work), "model": registry_model,
                                "description": "Próba", "proactive": False})
    unit = render.render_unit(entry, template=TMPL)
    body = re.search(r"/bin/sh -c '(.*)'\n", unit).group(1).replace("%h", str(home))
    r = subprocess.run(["/bin/sh", "-c", body], cwd=work, capture_output=True, text=True,
                       env={"PATH": "/usr/bin:/bin", "HOME": str(home)}, timeout=30)
    return r.stdout.strip()


class UnitModelEnv(unittest.TestCase):
    def test_without_model_env_the_registry_model_is_used(self):
        self.assertEqual(model_seen(None), "claude-opus-5-5")

    def test_model_env_overrides_a_full_claude_id(self):
        # e nélkül egy teljes Claude-azonosító az OpenRouteren valódi Claude-ot hívna
        self.assertEqual(model_seen("MENTAT_MODEL=deepseek/deepseek-v4.1-flash-1017\n"),
                         "deepseek/deepseek-v4.1-flash-1017")

    def test_empty_model_env_falls_back_to_registry(self):
        self.assertEqual(model_seen("MENTAT_MODEL=\n", registry_model="opus"), "opus")

    def test_rendered_unit_has_no_systemd_braces_to_expand(self):
        u = render.render_unit(registry.normalize({"agent": "p", "workdir": "/w", "model": "opus",
                                                   "description": "x", "proactive": False}), template=TMPL)
        exec_line = next(l for l in u.splitlines() if l.startswith("ExecStart="))
        self.assertNotIn("${", exec_line)  # a systemd a ${…}-t maga helyettesítené


if __name__ == "__main__":
    unittest.main()
