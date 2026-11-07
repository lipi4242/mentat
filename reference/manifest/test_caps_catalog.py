"""The curated catalog is real: every command and file it names exists, and it ships with the install.

Engine commands are checked against an engine checkout when ENGINE_SRC points at one
(`engine/release` of a dev checkout or `engine/` of a Mentat clone); otherwise that part is skipped.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import os
import pathlib
import re
import unittest

HERE = pathlib.Path(__file__).resolve().parent
REL = HERE.parent.parent  # release/
FILES = sorted((HERE / "capabilities").glob("*.json"))
ENUM = {"provenance": {"suite"}, "lifecycle": {"active", "planned", "deprecated"}, "scope": {"public", "private"}}
GROUPS = ("memoria", "proaktiv", "munka", "kulvilag", "biztonsag", "mukodes")
PROBES = {"which", "bin", "component", "plugin", "engine_cfg", "local", "module", "env_key", "manifest", "doc", "planned"}


def entries():
    return [e for f in FILES for e in json.loads(f.read_text(encoding="utf-8"))]


def texts(e):
    return [e.get("entry") or ""] + list(e.get("enable_steps") or []) + [(e.get("check") or {}).get("cmd", "")]


class Catalog(unittest.TestCase):
    def test_schema(self):
        ids = [e["id"] for e in entries()]
        self.assertEqual(len(ids), len(set(ids)))
        for e in entries():
            for key, allowed in ENUM.items():
                self.assertIn(e[key], allowed, e["id"])
            self.assertEqual(set(e["summary"]), {"hu", "en"}, e["id"])
            self.assertTrue(e["intents"]["hu"] and e["intents"]["en"], e["id"])
            self.assertEqual(len(e["probe"].keys() & PROBES), 1, e["id"])
            self.assertTrue(set(e["requires"]) <= set(ids), e["id"])
            self.assertIn(e["audience"], ("user", "agent"), e["id"])  # who the reference shows it to
            if e["audience"] == "user":
                self.assertEqual(set(e["user_summary"]), {"hu", "en"}, e["id"])
                self.assertTrue(all(e["user_summary"].values()), e["id"])
            self.assertIn(e.get("basic", False), (True, False), e["id"])
            self.assertIn(e["group"], GROUPS, e["id"])  # one MECE group each: exclusive by construction
            if e["lifecycle"] == "planned":
                self.assertEqual(set(e["interim"]), {"hu", "en"}, e["id"])
            else:
                self.assertTrue(e["entry"], e["id"])

    def test_every_bin_tool_named_exists(self):
        for e in entries():
            for t in texts(e) + ([e["probe"]["bin"]] if "bin" in e["probe"] else []):
                t = re.sub(r"\{BASE\}\S*", "", t)  # fetched files: the next test checks those
                for rel in re.findall(r"(?:\.mentat/bin/)?\b((?:web/|bekotes/)?mentat_\w+\.py|bekotes/\w+\.py)", t):
                    name = rel.split("/")[-1]
                    where = {"web": REL / "reference/web", "bekotes": REL / "reference/bekotes"}.get(
                        rel.split("/")[0] if "/" in rel else "", HERE)
                    self.assertTrue((where / name).is_file(), (e["id"], rel))

    def test_every_doc_and_fetched_file_exists(self):
        for e in entries():
            docs = e["docs"] if isinstance(e["docs"], dict) else {"x": e["docs"]}
            for d in docs.values():
                if not d.startswith("http"):
                    self.assertTrue((REL / d.split("#")[0]).is_file(), (e["id"], d))
            for t in texts(e):
                for path, group in re.findall(r"\{BASE\}([\w/.-]*?)\{([^}]+)\}", t):
                    for name in group.split(","):
                        self.assertTrue((REL / path / name).is_file(), (e["id"], path + name))
                for path in re.findall(r"\{BASE\}([\w/.-]+\.(?:md|py|json))", t):
                    self.assertTrue((REL / path).is_file(), (e["id"], path))

    @unittest.skipUnless(os.environ.get("ENGINE_SRC"), "ENGINE_SRC not set: engine commands not checked")
    def test_every_engine_command_exists_in_the_engine(self):
        src = pathlib.Path(os.environ["ENGINE_SRC"]) / "src"
        main = (src / "anytime_engine" / "__main__.py").read_text()
        for e in entries():
            mods = [e["probe"]["module"]] if "module" in e["probe"] else []
            for t in texts(e):
                mods += re.findall(r"python3 -m (anytime_\w+(?:\.\w+)?)", t)
                for cmd in re.findall(r"python3 -m anytime_engine (\w+)", t):
                    self.assertIn('"%s"' % cmd, main, (e["id"], cmd))
            for m in mods:
                pkg, _, mod = m.partition(".")
                self.assertTrue((src / pkg / ((mod or "__main__") + ".py")).is_file(), (e["id"], m))

    def test_the_install_fetches_the_finder_and_the_catalog(self):
        need = {p.name for p in HERE.glob("mentat_caps*.py")}
        cats = {p.name for p in FILES}
        for doc in ("initialization.md", "initialization.hu.md"):
            text = (REL / "reference" / doc).read_text(encoding="utf-8")
            got = set(re.search(r'-o "\.mentat/bin/#1" "[^"]*/manifest/\{([^}]*)\}"', text).group(1).split(","))
            self.assertTrue(need <= got, (doc, need - got))
            m = re.search(r'-o "\.mentat/bin/capabilities/#1" "[^"]*/manifest/capabilities/\{([^}]*)\}"', text)
            self.assertTrue(m and set(m.group(1).split(",")) == cats, doc)

    def test_one_always_loaded_line_and_an_on_demand_guide(self):
        for lang, guide in (("hu", "capabilities.hu.md"), ("en", "capabilities.md")):
            agents = (HERE / ("scaffold-agents.%s.md" % lang)).read_text(encoding="utf-8")
            self.assertEqual(agents.count("where --find"), 1, lang)
            self.assertTrue((REL / "reference" / guide).is_file(), guide)
            self.assertIn(guide, (REL / "reference" / "_index.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
