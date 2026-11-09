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


if __name__ == "__main__":
    unittest.main()
