"""Titok-kapu: futásidejű értéket ($X, $(…), `…`) tartalmazó út (11-08). Tilt, ha a statikus előtag
titoktárban van; a hétköznapi, változós repó-munka szabad. A futás közben dekódolt út és a fájlból
olvasott útlista ismert korlát (szándékos megkerülés ellen a kapu nem véd; az OS-izoláció igen).
Futtatás: python3 -I -m unittest discover -s security/eszkozok/identitas -q
"""
import os
import pathlib
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import titok_kapu as K  # noqa: E402
import titok_minta as M  # noqa: E402


class FutasidejuUt(unittest.TestCase):
    def setUp(self):
        keys = ("HOME", "CLAUDE_CONFIG_DIR", "CLAUDE_PROJECT_DIR", "FLEET_AGENT", "FLEET_REGISTRY")
        self.old = {k: os.environ.get(k) for k in keys}
        self.home = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, True)
        os.environ["HOME"] = self.home
        for k in keys[1:]:
            os.environ.pop(k, None)
        h = self.home
        self.repo = os.path.join(h, "repo")
        for d in ("repo/.git", "repo/docs", "repo/src", ".claude/projects/-masik", ".config/vilma", ".mentat/titkok"):
            os.makedirs(os.path.join(h, d))
        for rel in ("repo/docs/a.md", "repo/src/app.py", "repo/.env", ".claude/projects/-masik/s.jsonl",
                    ".config/vilma/v.env"):
            with open(os.path.join(h, rel), "w") as f:
                f.write("x\n")
        env = os.path.join(self.repo, ".env")
        st = os.stat(env)
        self.lel = M.Leltar([{"path": env, "dev": st.st_dev, "ino": st.st_ino}])

    def tearDown(self):
        for k, v in self.old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def b(self, cmd):
        return K.decide("Bash", {"command": cmd}, self.repo, self.lel)

    def test_titoktarban_dinamikus_maradek_tilt(self):
        for cmd in ("cat ~/.mentat/titkok/$X", "cat ~/.config/$(ls ~/.config | head -1)/v.env",
                    "cat ~/.config/vilma/$F", "cp ~/.claude/projects/$P/s.jsonl /tmp/x",
                    'cat "$HOME/.claude/projects/${P}/s.jsonl"', "cat ~/$X", "cat ./$X",
                    'F=$(ls ~/.claude/projects/-masik/*.jsonl); cat "$F"',
                    'cat "$(ls ~/.claude/projects/-masik/*.jsonl)"',
                    "ls ~/.claude/projects/-masik/*.jsonl | xargs cat",
                    "find ~/.claude/projects -name '*.jsonl' -exec cat {} \\;",
                    "find ~/.claude/projects -name '*.jsonl' | while read f; do cat \"$f\"; done",
                    "for f in ~/.claude/projects/*/*.jsonl; do cat \"$f\"; done"):
            why = self.b(cmd)
            self.assertTrue(why, cmd)
        self.assertIn("adj meg konkrét útvonalat", self.b("cat ~/.mentat/titkok/$X"))
        for cmd in ('cat "%s/$PWD_X/v.env"' % os.path.join(self.home, ".config"),  # Codex 11-08: $PWD-előtag
                    'cat "%s/$CLAUDE_PROJECT_DIRX/v.env"' % os.path.join(self.home, ".config"),
                    "find . -not -path './.env' -o -exec cat {} \\;",  # Codex 11-08: -o mellett nem globális
                    "find . -not -path ./.env -or -name '*' | xargs cat",
                    "find . -type f ! ! -name .env -exec cat {} +",  # Codex 11-08: kettős tagadás
                    "find . -not ( -not -name .env ) -exec cat {} +",
                    "find . -exec cat {} + -not -name .env", "find . -print -not -name .env | xargs cat",
                    "find . -not -path './.env/*' -print | xargs cat"):  # Codex 11-08: X/* nem zárja ki X-et
            self.assertTrue(self.b(cmd), cmd)

    def test_hetkoznapi_valtozos_repomunka_szabad(self):
        for cmd in ('for f in docs/*.md; do cat "$f"; done', "git ls-files | xargs grep -n foo",
                    'cat "$(git rev-parse --show-toplevel)/docs/a.md"',
                    'REPO=$(git rev-parse --show-toplevel); cat "$REPO/docs/a.md"',
                    'for f in $(git ls-files "*.md"); do wc -l "$f"; done',
                    "find docs -name '*.md' -exec cat {} \\;", 'cat "docs/$X.md"', 'X=a; cat "docs/$X.md"',
                    'cat "$(pwd)/docs/a.md"', 'cat "$PWD/src/app.py"', "diff <(git show HEAD:docs/a.md) docs/a.md",
                    'while read f; do echo "$f"; done < docs/a.md', 'cat "src/${NAME}.py"'):
            self.assertIsNone(self.b(cmd), cmd)

    def test_find_path_kizaras_csak_a_gyokerben(self):  # Codex 11-08: ./.env nem zárja ki a sub/.env-et
        os.remove(os.path.join(self.repo, ".env"))  # csak az al/.env legyen titok
        os.makedirs(os.path.join(self.repo, "al"))
        sub = os.path.join(self.repo, "al", ".env")
        with open(sub, "w") as f:
            f.write("x\n")
        st = os.stat(sub)
        self.lel = M.Leltar([{"path": sub, "dev": st.st_dev, "ino": st.st_ino}])
        self.assertTrue(self.b("find . -not -path ./.env -type f -exec cat {} +"))
        self.assertIsNone(self.b("find . -not -name .env -type f -exec cat {} +"))
        for cmd in ("find . -not -path ./al -print | xargs cat", "find . -not -name al | xargs cat"):
            self.assertTrue(self.b(cmd), cmd)  # Codex 11-08: a mappa tagadása nem metszi le a fát
        self.assertTrue(self.b("find . -name al -prune -o -depth -print | xargs cat"))  # -depth: nincs prune
        self.assertTrue(self.b("find . ! -path './al/.env/' -print | xargs cat"))  # záró `/` nem illik
        self.assertTrue(self.b("find . -path './al/.env/*' -prune -o -print | xargs cat"))  # X/* nem X
        self.assertTrue(self.b("find . -path ./al/.env -prune -o -false | xargs cat"))  # implicit -print
        for cmd in ("find . -path ./al -prune -o -print | xargs cat", "find . -name al -prune -o -print | xargs cat",
                    "find . -not -path './al/*' | xargs cat", "grep -rn x --exclude-dir=al ."):
            self.assertIsNone(self.b(cmd), cmd)

    def test_find_xargs_leltar_mellett_kizarassal(self):
        why = self.b("find . -name '*.py' | xargs grep -n TODO")
        self.assertTrue(why and "-not -path './.env'" in why, why)
        for cmd in ("find . -name '*.py' -not -path './.env' | xargs grep -n TODO",
                    "find . ! -path ./.env -name '*.py' | xargs grep -n TODO",
                    "find . -path ./.env -prune -o -name '*.py' -print | xargs grep -n TODO",
                    "grep -rn TODO --exclude=.env ."):
            self.assertIsNone(self.b(cmd), cmd)

    def test_ismert_korlat_dekodolt_es_fajlbol_olvasott_ut(self):
        """Dokumentált korlát (README): ezek átmennek; ha egyszer tiltanak, a README-t is frissítsd."""
        for cmd in ('F=$(echo eA== | base64 -d); cat "$F"', "cat $(cat lista.txt)"):
            self.assertIsNone(self.b(cmd), cmd)


if __name__ == "__main__":
    unittest.main()
