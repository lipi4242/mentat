"""F-41 + nemakad (CISO 10-24): a TELJES ~/.mentat/bin/ írása védett (a kapu és a nemakad kódja,
a sha256-jegyzékekkel), a futtatás és az olvasás szabad, a repó saját .mentat/bin-je nem a kapué.
"""
import os
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_vedett import Base  # noqa: E402 - ideiglenes HOME, repó a HOME alatt


class TeljesBin(Base):
    def test_nemakad_kod_es_jegyzek_irasa_vedett(self):
        b = os.path.join(self.home, ".mentat", "bin")
        for cmd in ("echo 'print(1)' > ~/.mentat/bin/nemakad/current/nemakad.py",
                    "chmod 644 ~/.mentat/bin/nemakad/abc123def456.sha256.json",
                    "sed -i '' 's/deny/allow/' ~/.mentat/bin/nemakad/current/nemakad.py",
                    "rm -rf ~/.mentat/bin/nemakad",
                    "cp /tmp/x.py %s/nemakad/current/" % b,
                    "touch ~/.mentat/bin/uj-eszkoz"):
            self.assertTrue(self.w("Bash", command=cmd), cmd)
        for tool, key in (("Write", "file_path"), ("Edit", "file_path")):
            self.assertTrue(self.w(tool, **{key: os.path.join(b, "nemakad", "current", "nemakad.py")}), tool)

    def test_futtatas_olvasas_szabad(self):
        for cmd in ("/usr/bin/python3 -I ~/.mentat/bin/nemakad/current/nemakad.py alszom 08:00",
                    "/usr/bin/python3 -I ~/.mentat/bin/nemakad/current/nemakad_ellenor.py ellenoriz",
                    "cat ~/.mentat/bin/nemakad/abc123def456.sha256.json",
                    "ls -la ~/.mentat/bin/"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_repo_sajat_mentat_bin_nem_vedett(self):
        for cmd in ("echo x > .mentat/bin/sajat.py", "rm -rf .mentat/bin/bekotes"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)


if __name__ == "__main__":
    unittest.main()
