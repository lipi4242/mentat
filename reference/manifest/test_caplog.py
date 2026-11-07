"""The capability log is consistent with the catalog and the CHANGELOG, and its generated files are current.

Compatible with pytest and direct execution (stdlib unittest).
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import copy
import json
import pathlib
import tempfile
import unittest

import mentat_caplog as cl
import mentat_caps_index as idx

REL = cl.REL


def change(cid="x-change", cap="brain.due", kind="improved", comp="brain"):
    return {"id": cid, "component": comp, "title": {"en": "T", "hu": "T"}, "summary": {"en": "S", "hu": "S"},
            "capabilities": [{"id": cap, "change": kind}]}


def log_of(*changes, version="9.9.9"):
    return {"schema": 1, "releases": [{"version": version, "date": None, "changes": list(changes)}]}


class Shipped(unittest.TestCase):
    def test_shipped_log_matches_catalog_and_changelog(self):
        self.assertEqual(cl.problems(cl.load(), idx.catalog(), {"brain": REL / "CHANGELOG.md"}), [])

    def test_generated_logs_are_current(self):
        for lang, name in (("en", "CAPABILITY-LOG.md"), ("hu", "CAPABILITY-LOG.hu.md")):
            want = cl.render_md(cl.load(), idx.catalog(), lang) + "\n"
            self.assertEqual((REL / name).read_text(encoding="utf-8"), want,
                             "%s is stale: python3 reference/manifest/mentat_caplog.py render md --lang %s > %s"
                             % (name, lang, name))

    def test_log_reaches_the_release_json_version(self):
        """The newest log entry is the version being prepared: release.json's, or the next one."""
        key = lambda v: tuple(int(x) for x in v.split("."))
        ver = json.loads((REL / "release.json").read_text())["version"]
        self.assertGreaterEqual(max(key(r["version"]) for r in cl.load()["releases"]), key(ver))


class Problems(unittest.TestCase):
    def setUp(self):
        self.catalog = idx.catalog()
        self.dir = pathlib.Path(tempfile.mkdtemp())

    def changelog(self, body):
        p = self.dir / "CHANGELOG.md"
        p.write_text("# Changelog\n\n## 9.9.9\n\n%s\n## 9.9.8\n\n- **Old** — no marker needed\n" % body)
        return {"brain": p}

    def check(self, log, body="- **T** — text <!-- cap: x-change -->\n"):
        return cl.problems(log, self.catalog, self.changelog(body))

    def test_a_good_entry_passes(self):
        self.assertEqual(self.check(log_of(change())), [])

    def test_marker_on_a_continuation_line_counts(self):
        self.assertEqual(self.check(log_of(change()), "- **T** — text\n  more <!-- cap: x-change -->\n"), [])

    def test_unknown_capability(self):
        self.assertTrue(any("not in the catalog" in p for p in self.check(log_of(change(cap="no.such")))))

    def test_unknown_change_kind(self):
        self.assertTrue(any("change must be" in p for p in self.check(log_of(change(kind="tweaked")))))

    def test_private_capability_cannot_be_logged(self):
        self.catalog = self.catalog + [{**self.catalog[0], "id": "x.private", "scope": "private"}]
        self.assertTrue(any("not public" in p for p in self.check(log_of(change(cap="x.private", kind="new")))))

    def test_removed_but_still_active(self):
        self.assertTrue(any("still active" in p for p in self.check(log_of(change(kind="removed")))))

    def test_removed_and_gone_from_the_catalog_is_fine(self):
        self.assertEqual(self.check(log_of(change(cap="gone.cap", kind="removed"))), [])

    def test_change_without_bullet(self):
        found = self.check(log_of(change(), change(cid="y-change")))
        self.assertTrue(any("y-change has no bullet" in p for p in found))

    def test_bullet_without_change(self):
        body = "- **T** <!-- cap: x-change -->\n- **U** <!-- cap: stray -->\n"
        self.assertTrue(any("stray has no change" in p for p in self.check(log_of(change()), body)))

    def test_bullet_without_marker(self):
        body = "- **T** <!-- cap: x-change -->\n- **Unmarked** — text\n"
        self.assertTrue(any("0 markers" in p for p in self.check(log_of(change()), body)))

    def test_missing_language_and_duplicate_id(self):
        bad = change()
        bad["summary"] = {"en": "only"}
        found = self.check(log_of(bad, copy.deepcopy(bad)))
        self.assertTrue(any("summary needs" in p for p in found))
        self.assertTrue(any("duplicate" in p for p in found))

    def test_other_components_are_checked_only_against_their_own_changelog(self):
        self.assertEqual(self.check(log_of(change(), change(cid="eng", cap="engine.core", comp="engine"))), [])


class Render(unittest.TestCase):
    def test_json_feed_has_a_history_per_capability(self):
        feed = json.loads(cl.render_json(cl.load(), idx.catalog()))
        self.assertEqual(feed["schema"], 1)
        self.assertTrue(feed["capabilities"])
        for cap, node in feed["capabilities"].items():
            self.assertTrue(node["history"], cap)
            self.assertIn(node["history"][0]["change"], cl.KINDS)

    def test_markdown_names_kind_in_each_language(self):
        log = log_of(change(kind="new"))
        self.assertIn("(New: `brain.due`)", cl.render_md(log, idx.catalog(), "en"))
        self.assertIn("(Új: `brain.due`)", cl.render_md(log, idx.catalog(), "hu"))

    def test_markdown_groups_follow_the_catalog(self):
        md = cl.render_md(log_of(change(kind="new")), idx.catalog(), "en")
        group = {e["id"]: e for e in idx.catalog()}["brain.due"].get("group")
        label = dict((g[0], g[2]) for g in cl.GROUPS).get(group, "Other")
        self.assertIn("### " + label, md)


if __name__ == "__main__":
    unittest.main()
