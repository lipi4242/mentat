"""F-41 follow-up (CISO, #84): the fleet plugin instance also makes the bootstrap gate step back
(only from state outside the repo), and the USER's question about `--write` shows each line's
source, so an injected host is visible as coming from a repo file."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import subprocess
import unittest

from test_guard_kint import KintBase

ADDR = "teszt.elek@example.com"
OPENALEX = "https://api.openalex.org/works?mailto=" + ADDR
HOOK = {"matcher": "*", "hooks": [{"type": "command", "onFailure": "block",
                                   "command": "python3 -I \"${CLAUDE_PLUGIN_ROOT}/hooks/identitas/kapu.py\" --hook --instance plugin"}]}


class PluginStepsBack(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        (self.home / ".mentat").mkdir()
        (self.home / ".mentat" / "identitas.txt").write_text(ADDR + "\n")
        self.base = self.home / ".claude"
        self.plugin = self.base / "plugins" / "cache" / "flotta" / "fleet" / "1.3.0"

    def install(self, enabled=True, block=True, code=True, path=None):
        path = path or self.plugin
        (path / "hooks" / "identitas").mkdir(parents=True, exist_ok=True)
        hook = json.loads(json.dumps(HOOK))
        if not block:
            del hook["hooks"][0]["onFailure"]
        (path / "hooks" / "hooks.json").write_text(json.dumps({"hooks": {"PreToolUse": [hook]}}))
        k = path / "hooks" / "identitas" / "kapu.py"
        k.write_text("#") if code else (k.unlink() if k.exists() else None)
        (self.base / "plugins").mkdir(parents=True, exist_ok=True)
        (self.base / "plugins" / "installed_plugins.json").write_text(json.dumps(
            {"version": 2, "plugins": {"fleet@flotta": [{"scope": "user", "installPath": str(path)}]}}))
        (self.base / "settings.json").write_text(json.dumps({"enabledPlugins": {"fleet@flotta": enabled}}))

    def fetch(self):
        return self.d("WebFetch", {"url": OPENALEX, "prompt": "x"})

    def test_an_enabled_verified_plugin_takes_over(self):
        self.assertEqual(self.fetch(), "ask")
        self.install()
        self.assertEqual(self.fetch(), "allow")

    def test_disabled_unblocking_missing_or_in_repo_plugins_do_not_count(self):
        for kw in ({"enabled": False}, {"block": False}, {"code": False},
                   {"path": self.root / ".plugin-copy"}):
            self.install(**kw)
            self.assertEqual(self.fetch(), "ask", kw)

    def test_another_projects_gated_install_does_not_count(self):  # CISO #88
        self.install(code=False)  # the user-scope install: an old version, no gate in it
        other = self.base / "plugins" / "cache" / "flotta" / "fleet" / "1.4.0"
        self.install(path=other)  # a newer, gated copy …
        doc = {"version": 2, "plugins": {"fleet@flotta": [
            {"scope": "user", "installPath": str(self.plugin)},
            {"scope": "project", "projectPath": "/x/masik-projekt", "installPath": str(other)}]}}
        (self.base / "plugins" / "installed_plugins.json").write_text(json.dumps(doc))  # … for another project
        self.assertEqual(self.fetch(), "ask")


    def test_odd_json_neither_breaks_the_hook_nor_hides_a_valid_entry(self):  # Rilí, #88
        self.install()
        valid = {"scope": "user", "installPath": str(self.plugin)}
        path = self.base / "plugins" / "installed_plugins.json"
        path.write_text(json.dumps({"version": 2, "plugins": {"fleet@flotta": [None, "x", [], 7, valid]}}))
        self.assertEqual(self.fetch(), "allow")  # the valid entry after the odd ones still counts
        import szerep_kapu_id
        for plugins in (None, "x", [], [valid]):
            path.write_text(json.dumps({"version": 2, "plugins": plugins}))
            self.assertFalse(szerep_kapu_id.user_gate_active(self.root), plugins)
            self.assertEqual(self.fetch(), "ask", plugins)  # asked, not every tool denied
        for settings in ({"enabledPlugins": ["fleet@flotta"]}, {"enabledPlugins": None, "hooks": []},
                         {"hooks": "x"}, {"hooks": {"PreToolUse": "x"}}, [1, 2]):
            (self.base / "settings.json").write_text(json.dumps(settings))
            self.assertEqual(self.fetch(), "ask", settings)
        (self.base / "settings.json").write_text(json.dumps({"enabledPlugins": {"fleet@flotta": True}}))
        path.write_text(json.dumps({"version": 2, "plugins": {"fleet@flotta": [valid]}}))
        (self.plugin / "hooks" / "hooks.json").write_text(json.dumps({"hooks": ["x"]}))
        self.assertEqual(self.fetch(), "ask")


class SourceInTheQuestion(KintBase):
    roles = False

    def test_each_line_shows_where_it_was_suggested_from(self):
        subprocess.run(["git", "-C", str(self.root), "init", "-q"], capture_output=True)
        (self.root / "projects" / "app").mkdir(parents=True)
        (self.root / "projects" / "app" / "wrangler.toml").write_text('routes = [{ pattern = "app.example.net/*" }]\n')
        cmd = "python3 .mentat/bin/bekotes/szerep_id_javaslat.py --write app.example.net evil.example.org"
        r = self.run_guard(self.payload("Bash", {"command": cmd}))
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("app.example.net ← projects/app/wrangler.toml", reason)
        self.assertIn("evil.example.org ← NEM JAVASOLT", reason)


if __name__ == "__main__":
    unittest.main()
