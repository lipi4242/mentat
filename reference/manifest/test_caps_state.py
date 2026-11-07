"""Availability is observed (manifest + cheap probes), never taken from the catalog;
the agent's own work (projects, connectors, procedures, helpers, own concerns) is found too."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import unittest

from _caps_base import CapsBase

MORNING = "minden reggel írd ki, ki nem fizetett"


class Availability(CapsBase):
    def test_no_engine_means_pack_off_and_engine_available(self):
        c = self.by_id(MORNING, "engine.cases")
        self.assertEqual(c["availability"], "off")
        self.assertEqual(c["requires"], [{"id": "engine.core", "availability": "available"}])

    def test_engine_with_the_pack_listed_is_on_and_the_probe_says_what_it_saw(self):
        self.manifest({"components": {"brain": {"root": "agy"},
                                      "engine": {"path": "anytime_engine", "plugins": ["anytime_cases"]}}})
        self.assertEqual(self.by_id(MORNING, "engine.cases")["availability"], "degraded")  # no engine on disk
        self.write("anytime_engine/tick.py")
        c = self.by_id(MORNING, "engine.cases")
        self.assertEqual(c["availability"], "on")
        self.assertIn("anytime_cases", c["probe"])
        self.assertIn("T", c["observed_at"])

    def test_installed_tool_with_a_missing_prerequisite_is_degraded(self):
        self.write(".mentat/bin/web/mentat_cf_access.py")
        self.assertEqual(self.by_id("csak ő lássa az oldalt", "cf.access")["availability"], "degraded")

    def test_manifest_section_probe(self):
        self.assertEqual(self.by_id("milyen szerepben", "roles")["availability"], "available")
        self.manifest({"components": {"brain": {"root": "agy"}}, "roles": {"default": "asszisztens"}})
        self.assertEqual(self.by_id("milyen szerepben", "roles")["availability"], "on")

    def test_vendored_module_is_seen_on_disk(self):
        self.manifest({"components": {"brain": {"root": "agy"}, "engine": {"path": "anytime_engine"}}})
        self.write("anytime_engine/tick.py")
        self.assertEqual(self.by_id("előnézet holnapi üzenet", "engine.preview")["availability"], "available")
        self.write("anytime_engine/preview.py")
        self.assertEqual(self.by_id("előnézet holnapi üzenet", "engine.preview")["availability"], "on")

    def test_bin_tool_and_env_key_without_leaking_the_value(self):
        self.assertEqual(self.by_id("él az oldal", "web.check")["availability"], "available")
        self.write(".mentat/bin/mentat_web.py")
        self.assertEqual(self.by_id("él az oldal", "web.check")["availability"], "on")
        self.write(".env", "CLOUDFLARE_API_TOKEN=sekret-value-123\n")
        r = self.run_where("--find", "cloudflare token", "--json")
        self.assertIn('"availability": "on"', r.stdout)
        self.assertNotIn("sekret-value-123", r.stdout)

    def test_setup_recorded_executor_turns_schedule_on(self):
        self.manifest({"components": {"brain": {"root": "agy"},
                                      "engine": {"exec": "python3 -m anytime_cases.deliver"}}})
        self.write("anytime_engine/tick.py")
        self.assertEqual(self.by_id("időzítő óránként", "engine.schedule")["availability"], "on")


class OwnInventory(CapsBase):
    def test_own_project_is_found_by_its_readme(self):
        self.write("projects/tagdij-figyelo/README.md",
                   "# Tagdíj-figyelő\n\nReggeli lista arról, ki nem fizetett tagdíjat.\n")
        c = self.by_id("ki nem fizetett tagdíjat", "own.project.tagdij-figyelo")
        self.assertEqual((c["provenance"], c["availability"]), ("own", "on"))
        self.assertEqual(c["entry"], "projects/tagdij-figyelo/")

    def test_connectors_procedures_and_helpers(self):
        self.write("agy/connectors/szamlazo.md", "---\ntitle: Számlázó\ntags: [szamla]\n---\n# Számlázó\n")
        self.write("agy/procedures/havi-zaras.md", "---\ntitle: Havi zárás\n---\n# Havi zárás\n")
        self.write("agy/subagentek/_meta.md", "| név | fajta | mire jó | állapot |\n|---|---|---|---|\n"
                   "| jogasz | perszóna | szerződés átnézése | aktív |\n")
        self.assertEqual(self.top("számlázó bekötése"), "own.connector.szamlazo")
        self.assertEqual(self.top("havi zárás"), "own.procedure.havi-zaras")
        self.assertEqual(self.top("nézd át a szerződést"), "own.subagent.jogasz")

    def test_own_concern_pack_is_listed_with_its_concerns(self):
        self.manifest({"components": {"brain": {"root": "agy"},
                                      "engine": {"plugins": ["anytime_cases", "sajat_pack"]}}})
        self.write("sajat_pack/concerns.py", 'register(Concern(name="tagdij_emlekezteto",\n'
                   '    description="Tagdíj emlékeztető péntekenként", triggers=["hourly"]))\n')
        c = self.by_id("tagdíj emlékeztető", "own.concerns.sajat_pack")
        self.assertIn("tagdij_emlekezteto", c["summary"])

    def test_top_level_concerns_folder_without_a_manifest_entry(self):
        self.write("concerns/checkin.py", 'register(Concern(name="napi_becsekkolas", description="Napi kérdés"))\n')
        self.assertEqual(self.top("napi becsekkolás"), "own.concerns.concerns")

    def test_mcp_servers_are_external(self):
        self.write(".mcp.json", '{"mcpServers": {"notion": {"command": "x"}}}')
        c = self.by_id("notion", "external.mcp.notion")
        self.assertEqual(c["provenance"], "external")


if __name__ == "__main__":
    unittest.main()
