"""F-41 kapu, védett fájlok: a parancsonkénti szabályok (find, másolás, git -C, interpreter-kód).

Élesben (2026-10-24, Mac): a `find ~ …` és más olvasó parancsok tiltást kaptak, mert az ős-mappa
szabály olvasó parancsra is lefutott. Az ős-mappa csak törlő vagy mozgató parancsnál számít;
minden más csak akkor tilt, ha a feloldott írási cél maga a védett fájl vagy mappa.
"""
import os
import sys
import pathlib
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from test_vedett import Base  # noqa: E402


class Find(Base):
    """2026-10-24, élesben: `find ~ -maxdepth 4 -type d -name …` tiltás lett, mert a `find` az
    ős-mappa szabály alá esett. A `find` csak törléssel, író -exec-kel vagy -fprint-tel ír."""

    def test_olvaso_find_szabad(self):
        for cmd in ("find ~ -maxdepth 4 -type d -name 'minta*' 2>/dev/null | head", "find ~ -name x",
                    "find ~/.mentat -name '*.txt'", "find ~ -name '*.md' -exec grep -l kapu {} +",
                    "find $HOME -type f -print | wc -l", "chmod 700 ~", "rsync -a ~/ /tmp/mentes/"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)

    def test_masolas_forraskent_olvasas_celkent_iras(self):
        os.makedirs(os.path.join(self.home, ".mentat"), exist_ok=True)
        for cmd in ("cp ~/.mentat/identitas.txt /tmp/mentes.txt", "rsync -a ~/.mentat/ /tmp/mentes/",
                    "cp ~/notes.md ~/.mentat/", "ln -s ~/.mentat/elsofel.txt ~/link.txt", "cp -r ~ /tmp/teljes"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)
        for cmd in ("cp /tmp/x/identitas.txt ~/.mentat/", "cp /tmp/x/identitas.txt ~/.mentat",
                    "mv ~/.mentat /tmp/el", "mv /tmp/x ~/.mentat/elsofel.txt", "install -m 600 /tmp/y ~/.mentat/identitas.txt"):
            self.assertTrue(self.w("Bash", command=cmd), cmd)

    def test_olvaso_kod_es_git_a_home_ban(self):
        p = os.path.join(self.home, ".mentat", "identitas-cache.json")
        for cmd in ("python3 -c \"import json; d=json.load(open('%s')); print(str(d).replace('a','b'))\"" % p,
                    "python3 -c \"import copy, os; print(os.path.exists(os.path.expanduser('~/.mentat/identitas.txt')))\"",
                    "git -C ~ checkout -- notes.md", "git -C ~ pull"):
            self.assertIsNone(self.w("Bash", command=cmd), cmd)
        self.assertTrue(self.w("Bash", command="git -C ~ clean -fdx"))
        self.assertTrue(self.w("Bash", command="python3 -c \"import os; os.replace('/tmp/x', '%s')\"" % p))

    def test_rekurziv_masolas_os_celra(self):
        self.assertTrue(self.w("Bash", command="cp -r /tmp/fa ~"))
        self.assertTrue(self.w("Bash", command="rsync -a /tmp/fa/ ~/.mentat/"))
        self.assertIsNone(self.w("Bash", command="cp /tmp/egy.txt ~"))
        self.assertIsNone(self.w("Bash", command="cp -r ~/projekt /tmp/mentes"))

    def test_iro_find_tilt(self):
        for cmd in ("find ~/.mentat -delete", "find ~ -name identitas.txt -delete",
                    "find ~/.mentat -type f -exec rm {} \\;", "find . -fprint ~/.mentat/identitas.txt",
                    "find /tmp/x -exec cp {} ~/.mentat/identitas.txt \\;", "rsync -a --delete /tmp/ures/ ~/"):
            self.assertTrue(self.w("Bash", command=cmd), cmd)


if __name__ == "__main__":
    unittest.main()
