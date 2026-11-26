"""11-07: a hidas ágens unitja MINDIG betölti a híd env-fájlját (telegram.env), akkor is, ha az
ágensé más (paul-cfo: agent.env) — különben a send.mjs-nek nincs tokenje, és az ágens némán nem
tud írni a tulajdonosnak. Több env-fájl: `env_files`; a régi `env_file` változatlanul működik."""
from __future__ import annotations
import _hermetic  # noqa: F401  (első import: HOME → tmp)
import unittest

from fleet import registry, render, TEMPLATES_DIR

TMPL = (TEMPLATES_DIR / "agent.service.tmpl").read_text()
BRIDGE = {"unit": "probe-telegram-bridge.service"}


def _entry(**kw):
    base = {"agent": "probe", "workdir": "/home/x/probe", "model": "sonnet", "description": "Próba"}
    return registry.normalize({**base, **kw})


class EnvFiles(unittest.TestCase):
    def lines(self, u):
        return [ln for ln in u.splitlines() if ln.startswith("EnvironmentFile=")]

    def test_hidas_agens_sajat_env_fajllal_a_tokent_is_betolti(self):
        u = render.render_unit(_entry(env_file="agent.env", bridge=BRIDGE), template=TMPL)
        self.assertEqual(self.lines(u), ["EnvironmentFile=-%h/.config/probe/telegram.env",
                                         "EnvironmentFile=-%h/.config/probe/agent.env"])
        tg, own = u.index(". %h/.config/probe/telegram.env;"), u.index(". %h/.config/probe/agent.env;")
        self.assertLess(tg, own, "az ágens saját fájlja tölt be utoljára (az írja felül a közös kulcsot)")

    def test_a_hid_sajat_env_fajlnevet_kap(self):
        u = render.render_unit(_entry(env_file="agent.env", bridge={**BRIDGE, "env_file": "bot.env"}), template=TMPL)
        self.assertIn("EnvironmentFile=-%h/.config/probe/bot.env", u)

    def test_env_files_lista(self):
        u = render.render_unit(_entry(env_files=["a.env", "b.env"]), template=TMPL)
        self.assertEqual(self.lines(u), ["EnvironmentFile=-%h/.config/probe/a.env",
                                         "EnvironmentFile=-%h/.config/probe/b.env"])

    def test_regi_egyfajlos_unit_bajtra_ugyanaz(self):
        """A meglévő telegram.env-es hidas ágens unitja nem változik (nincs duplikált sor)."""
        u = render.render_unit(_entry(bridge=BRIDGE), template=TMPL)
        self.assertEqual(self.lines(u), ["EnvironmentFile=-%h/.config/probe/telegram.env"])
        self.assertIn("set -a; if [ -r %h/.config/probe/telegram.env ]; then . %h/.config/probe/telegram.env; fi; if", u)
        self.assertNotIn("@@", u)

    def test_hid_nelkul_nincs_telegram_env(self):
        u = render.render_unit(_entry(env_file="agent.env"), template=TMPL)
        self.assertEqual(self.lines(u), ["EnvironmentFile=-%h/.config/probe/agent.env"])

    def test_tiltott_fajlnev_a_listaban(self):
        with self.assertRaises(ValueError):
            render.render_unit(_entry(env_files=["../x.env"]), template=TMPL)


class ExtraEnvFiles(unittest.TestCase):
    """`extra_env_files`: további env-fájlok (pl. egy projekt wrangler-tokenje), amiket CSAK a
    pane-shell tölt be — őrzötten, a saját env-fájlok után, a claude-auth.env előtt."""

    # A mező bevezetése ELŐTTI renderelő pontos kimenete a set -a … claude-auth szakaszra.
    LEGACY_SOURCES = ("set -a; if [ -r %h/.config/probe/telegram.env ]; then . %h/.config/probe/telegram.env; fi;"
                      " if [ -r %h/.config/probe/claude-auth.env ]; then . %h/.config/probe/claude-auth.env; fi;")

    def test_mezo_nelkul_a_unit_bajtra_ugyanaz(self):
        base = render.render_unit(_entry(bridge=BRIDGE), template=TMPL)
        self.assertIn(self.LEGACY_SOURCES, base)
        for v in ([], None):
            self.assertEqual(render.render_unit(_entry(bridge=BRIDGE, extra_env_files=v), template=TMPL), base)
        self.assertNotIn("extra_env_files", registry.normalize({"agent": "probe"}),
                         "a normalize nem tölti ki: a registry-bejegyzés alakja sem változik")

    def test_minden_mintaagens_bajtra_ugyanaz(self):
        """A példa-registry minden template-es ágense: a mező hiánya és az üres lista azonos unitot ad."""
        from fleet import REPO_ROOT
        agents = registry.load_agents(REPO_ROOT / "examples" / "registry" / "agents.json")
        self.assertTrue(agents)
        for a in agents:
            if a.get("unit_source") != "template" or render.validate_for_render(a):
                continue
            self.assertEqual(render.render_unit({**a, "extra_env_files": []}, template=TMPL),
                             render.render_unit(a, template=TMPL), a["agent"])

    def test_sorrend_es_orzott_forma(self):
        u = render.render_unit(_entry(bridge=BRIDGE, extra_env_files=[
            "%h/projekt/.env", "/srv/x/cf.env", "config/wrangler.env"]), template=TMPL)
        want = ["%h/.config/probe/telegram.env", "%h/projekt/.env", "/srv/x/cf.env",
                "/home/x/probe/config/wrangler.env", "%h/.config/probe/claude-auth.env"]
        idx = [u.index(f"if [ -r {p} ]; then . {p}; fi;") for p in want]
        self.assertEqual(idx, sorted(idx), "telegram.env → extra (megadott sorrend) → claude-auth.env")
        self.assertLess(u.index("set -a;"), idx[0])
        self.assertLess(idx[-1], u.index("set +a;"))

    def test_nem_lesz_environmentfile_sor(self):
        u = render.render_unit(_entry(bridge=BRIDGE, extra_env_files=["%h/projekt/.env"]), template=TMPL)
        self.assertEqual([ln for ln in u.splitlines() if ln.startswith("EnvironmentFile=")],
                         ["EnvironmentFile=-%h/.config/probe/telegram.env"])

    def test_a_hid_unitja_nem_kapja(self):
        from fleet import bridge
        e = _entry(bridge=BRIDGE, extra_env_files=["%h/projekt/.env"])
        u = bridge.render_unit(e, env_file="%h/.config/probe/telegram.env", state_dir="/tmp/s")
        self.assertNotIn("projekt", u)

    def test_tiltott_elemek(self):
        bad = ["a b.env", "x;rm -rf ~", "$HOME/.env", "`id`.env", "'q'.env", '"q".env',
               "../x.env", "%h/../x.env", "a/../../b", "%t/x.env", "~/x.env", "dir/", "", 5, None]
        for f in bad:
            probs = render.validate_for_render(_entry(extra_env_files=[f]))
            self.assertTrue(any("extra_env_files" in p for p in probs), f"át kellett volna szűrni: {f!r}")
            with self.assertRaises(ValueError):
                render.render_unit(_entry(extra_env_files=[f]), template=TMPL)

    def test_nem_lista(self):
        for v in ("%h/x.env", {"a": 1}, 3):
            self.assertTrue(any("nem lista" in p for p in render.validate_for_render(_entry(extra_env_files=v))))

    def test_engedett_elemek(self):
        ok = ["%h/projekt/.env", "/home/u/projekt/.env.production", "config/cf_token.env", ".env"]
        self.assertEqual(render.validate_for_render(_entry(extra_env_files=ok)), [])

    def test_fleet_validate_jelzi(self):
        import json, tempfile
        from pathlib import Path
        from fleet.validate import validate
        with tempfile.TemporaryDirectory() as d:
            rd = Path(d)
            (rd / "boxes.json").write_text(json.dumps({"boxes": []}))
            (rd / "agents.json").write_text(json.dumps([
                {"agent": "probe", "workdir": "/home/x/probe", "extra_env_files": ["x;y"]},
                {"agent": "masik", "workdir": "/home/x/masik", "extra_env_files": "nem-lista"},
                {"agent": "jo", "workdir": "/home/x/jo", "extra_env_files": ["%h/p/.env"]}]))
            probs = [p for p in validate(rd)[1] if "extra_env_files" in p]
        self.assertEqual(len(probs), 2, probs)
        self.assertTrue(probs[0].startswith("probe: ") and probs[1].startswith("masik: "), probs)


if __name__ == "__main__":
    unittest.main()
