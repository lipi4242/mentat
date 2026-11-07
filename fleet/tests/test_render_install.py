"""Renderelés és telepítés: a sablon minden ágensre teljes unitot ad, a
kézzel írt unitok érintetlenek, a drop-in a fleet-leader útvonalára mutat."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp, lásd tests/_hermetic.py)
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fleet import registry, render, install, TEMPLATES_DIR  # noqa: E402

TMPL = (TEMPLATES_DIR / "agent.service.tmpl").read_text()
EXAMPLE_REGISTRY = Path(__file__).resolve().parents[1] / "examples" / "registry"


def _entry(**kw):
    base = {"agent": "probe", "workdir": "/home/x/probe", "model": "sonnet",
            "description": "Próba", "proactive": True,
            "loop_cmd": "/probe:startup", "tick_period_s": 3600}
    base.update(kw)
    return registry.normalize(base)


class TestRender(unittest.TestCase):
    def test_flags_include_rc_and_strict_mcp(self):
        u = render.render_unit(_entry(rc_name="pr"), template=TMPL)
        self.assertIn("--remote-control pr", u)
        self.assertIn("--strict-mcp-config --mcp-config %h/.config/fleet/mcp-empty.json", u)
        self.assertNotIn("@@", u)

    def test_ask_user_question_is_disallowed(self):
        # FL-03 (CISO 10-22): the bridge sends an unconditional Enter after every injected
        # line, so a menu would be answered for the user; the ban must not live only in a prompt.
        self.assertIn("--disallowedTools AskUserQuestion", render.render_unit(_entry(rc_name="pr"), template=TMPL))

    def test_proactive_gets_heartbeat_rm_and_seeded_startup(self):
        u = render.render_unit(_entry(), template=TMPL, fleet_root="%h/fleet-leader")
        self.assertIn("ExecStartPre=/bin/rm -f /home/x/probe/data/state/orchestrator-heartbeat.json", u)
        self.assertIn("ExecStartPost=%h/fleet-leader/bin/agent-startup-seed.sh probe '/probe:startup'", u)

    def test_non_proactive_has_no_pre_post(self):
        u = render.render_unit(_entry(proactive=False, loop_cmd=None), template=TMPL)
        self.assertNotIn("ExecStartPre", u)
        self.assertNotIn("ExecStartPost", u)

    def test_shared_account_has_no_config_dir_but_named_does(self):
        self.assertNotIn("Environment=CLAUDE_CONFIG_DIR", render.render_unit(_entry(), template=TMPL))
        u = render.render_unit(_entry(claude_account="example"), template=TMPL)
        self.assertIn("Environment=CLAUDE_CONFIG_DIR=%h/.claude-example", u)

    def test_unsafe_loop_cmd_is_refused(self):
        with self.assertRaises(ValueError):
            render.render_unit(_entry(loop_cmd="/x'; rm -rf /"), template=TMPL)
        with self.assertRaises(ValueError):
            render.render_unit(_entry(workdir="/home/x/my dir"), template=TMPL)

    def test_account_is_set_inside_the_launcher(self):
        u = render.render_unit(_entry(), template=TMPL)
        self.assertIn("unset CLAUDE_CONFIG_DIR;", u)
        u = render.render_unit(_entry(claude_account="example"), template=TMPL)
        self.assertIn("export CLAUDE_CONFIG_DIR=$HOME/.claude-example;", u)
        self.assertIn("kill-session -t =probe", u)

    def test_env_file_is_per_agent(self):
        u = render.render_unit(_entry(env_file="delta.env"), template=TMPL)
        self.assertIn("EnvironmentFile=-%h/.config/probe/delta.env", u)
        self.assertIn(". %h/.config/probe/delta.env", u)

    def test_every_template_agent_in_example_registry_renders(self):
        for a in registry.load_agents(EXAMPLE_REGISTRY / "agents.json"):
            if a["unit_source"] == "template":
                u = render.render_unit(a, template=TMPL)
                self.assertIn(f"--remote-control {a['rc_name']}", u, a["agent"])

    def test_file_sourced_units_exist(self):
        for a in registry.load_agents(EXAMPLE_REGISTRY / "agents.json"):
            if a["unit_source"] == "file":
                self.assertTrue((EXAMPLE_REGISTRY / "units" / a["unit"]).exists(), a["unit"])


class TestInstall(unittest.TestCase):
    def test_install_writes_unit_dropin_and_backup(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fakebin import FakeBin
        fb = FakeBin()
        try:
            with tempfile.TemporaryDirectory() as d:
                ud, cfg = Path(d) / "u", Path(d) / "cfg"
                e = _entry()
                r1 = install.install_unit(e, unit_dir=ud, config_dir=cfg)
                self.assertTrue(r1["changed"]); self.assertIsNone(r1["backup"])
                self.assertTrue((ud / "probe.service").exists())
                drop = ud / "probe.service.d" / "10-session-gate.conf"
                self.assertTrue(drop.exists())
                self.assertIn("agent-session-gate.sh probe", drop.read_text())
                self.assertNotIn("hub-repo", drop.read_text())
                # második telepítés: változatlan, nincs mentés
                r2 = install.install_unit(e, unit_dir=ud, config_dir=cfg)
                self.assertFalse(r2["changed"])
                # dormant → disable
                r3 = install.install_unit(_entry(status="dormant"), unit_dir=ud, config_dir=cfg)
                self.assertFalse(r3["enabled"])
                self.assertIn("systemctl --user disable probe.service", fb.calls())
                self.assertIn("systemctl --user enable probe.service", fb.calls())
        finally:
            fb.cleanup()


if __name__ == "__main__":
    unittest.main()


class TestBridgeUnit(unittest.TestCase):
    def test_bridge_env_is_telegram_env_not_agent_env(self):
        from fleet import bridge
        e = _entry(env_file="delta.env", bridge={"unit": "delta-telegram-bridge.service"})
        u = bridge.render_unit(e, env_file="%h/.config/probe/telegram.env", state_dir="%h/.config/probe")
        self.assertIn("EnvironmentFile=%h/.config/probe/telegram.env", u)
        # az install a bridge.env_file-t / telegram.env-et adja, sosem az ágens env_file-ját
        import inspect
        src = inspect.getsource(bridge.install_bridge)
        self.assertIn("'telegram.env'", src)
        self.assertNotIn("entry['env_file']", src)
