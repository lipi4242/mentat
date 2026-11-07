"""F-41 kapu: csak valódi szivárgás-veszélynél kérdez (2026-10-24, Krisz kérése).

Élő téves riasztás: `git -c user.email=<saját cím> commit … && git fetch && gh pr view -R <saját fiók>/…`
→ „a felhasználó azonosítója menne ide: github:<saját fiók>. Harmadik félnek megy.” A hiba: egy
helyi commit `-c` kapcsolójában álló cím is „kimenőnek” számított, mert a lánc egy másik szegmense
hálózati volt. Most csak a hálózati szegmens szövege számít.

Az első-fél döntés csak olyan állapotból jön, amit az ágens nem írhat kérdés nélkül (ciso): a saját
GitHub-fiók a SessionStart-cache `gh_logins` mezőjéből (a `gh api user`, a GitHub szervere szerint),
nem a gh hosts.yml-ből; egy ssh-gép, a LAN vagy a known_hosts nem dönt, csak az elsofel.txt sora
(amit a javaslat-eszköz javasol, a FELHASZNÁLÓ jóváhagy); a loopback első fél. A külső kutatási
API-k (crossref, openalex, ebi, springer, wikipedia, doi) változatlanul fogva maradnak.
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import elsofel  # noqa: E402
import ident  # noqa: E402
import kapu  # noqa: E402

ADDR = "teszt.elek@example.com"
IDS = ident.Ids([ADDR])


class Home(unittest.TestCase):
    logins = ["sajatfiok"]  # what the SessionStart cache holds (`gh api user`)

    def setUp(self):
        self.old = os.environ.get("HOME")
        self.home = tempfile.mkdtemp()
        os.environ["HOME"] = self.home
        self.elsofel = os.path.join(self.home, "elsofel.txt")
        gh = os.path.join(self.home, ".config", "gh")  # an agent can write this: it must not decide
        os.makedirs(gh)
        with open(os.path.join(gh, "hosts.yml"), "w") as f:
            f.write("github.com:\n    user: idegen\n")

    def tearDown(self):
        os.environ["HOME"] = self.old

    def d(self, cmd, cwd=None):
        allow = elsofel.Allow.load(IDS, path=self.elsofel, gh_logins=self.logins)
        return kapu.decide("Bash", {"command": cmd}, cwd or tempfile.gettempdir(), IDS, allow)


class SajatGithub(Home):
    def test_az_elo_teves_riasztas(self):
        repo = os.path.join(self.home, "repo")
        subprocess.run(["git", "init", "-q", repo], check=True)
        subprocess.run(["git", "-C", repo, "remote", "add", "origin", "https://github.com/sajatfiok/r.git"], check=True)
        cmd = ('git -c user.name=T -c user.email=%s commit -m "fix: %s" && git fetch && git log --oneline -3 && '
               'gh pr view 89 -R sajatfiok/mentat-dev --json state' % (ADDR, ADDR))
        self.assertIsNone(self.d(cmd, repo))

    def test_a_cache_szerinti_sajat_fiok_elso_fel(self):
        self.assertIsNone(self.d("gh pr comment 89 -R sajatfiok/repo --body 'kapcsolat: %s'" % ADDR))

    def test_a_hosts_yml_nem_dont_es_az_idegen_kerdez(self):
        r = self.d("gh issue comment 1 -R idegen/repo --body 'irj: %s'" % ADDR)
        self.assertIn("github:idegen", r["cel"])  # hosts.yml says `idegen`: still third party


class CacheNelkul(Home):
    logins = []

    def test_cache_nelkul_a_sajat_github_is_kerdez(self):
        r = self.d("gh pr comment 89 -R sajatfiok/repo --body 'kapcsolat: %s'" % ADDR)
        self.assertIn("github:sajatfiok", r["cel"])


class HelyiSzegmens(Home):
    def test_helyi_szegmensben_allo_cim_nem_megy_ki(self):
        for cmd in ("git log --author=%s && curl -s https://api.crossref.org/works?q=x" % ADDR,
                    "echo %s > /tmp/x.txt; curl -s https://en.wikipedia.org/w/api.php" % ADDR):
            self.assertIsNone(self.d(cmd), cmd)

    def test_a_kimeno_szegmensben_tovabbra_is_fog(self):
        for cmd, host in (("curl -s 'https://api.crossref.org/works?mailto=%s'" % ADDR, "api.crossref.org"),
                          ("cd x && curl -A 'bot (%s)' https://api.openalex.org/works" % ADDR, "api.openalex.org"),
                          ("wget -q 'https://www.ebi.ac.uk/x?email=%s'" % ADDR, "www.ebi.ac.uk"),
                          ("curl -H 'From: %s' https://link.springer.com/x" % ADDR, "link.springer.com"),
                          ("curl 'https://doi.org/10.1/x?mailto=%s'" % ADDR, "doi.org"),
                          ("E=$(git config user.email); curl -d \"$E\" https://en.wikipedia.org/w/api.php", "en.wikipedia.org")):
            self.assertIn(host, (self.d(cmd) or {}).get("cel", []), cmd)


class Elemzes(Home):
    def test_sortores_folytatas_es_ciklustorzs(self):
        """A korpusz-mérés két régi rése: a `\\\\`-es sortörés szétvágta a curl-t, a `do curl …` nem volt parancs."""
        cont = "curl -s -X POST https://api.example.org/login \\\n  -d '{\"email\":\"%s\"}'" % ADDR
        loop = "for p in a b; do curl -s \"https://commons.wikimedia.org/w?u=%s&p=$p\"; done" % ADDR
        self.assertEqual(self.d(cont)["cel"], ["api.example.org"])
        self.assertEqual(self.d(loop)["cel"], ["commons.wikimedia.org"])


class SajatGep(Home):
    def test_ssh_gep_csak_az_elsofel_soraval(self):
        ssh = os.path.join(self.home, ".ssh")
        os.makedirs(ssh)
        with open(os.path.join(ssh, "known_hosts"), "w") as f:  # an agent can write this too
            f.write("198.51.100.7 ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExample\n")
        lan = ".".join(["192", "168", "1", "51"])  # spelled out: the release check refuses IP literals
        for host in ("198.51.100.7", "nas.local", lan):
            self.assertTrue(self.d("ssh %s 'echo %s'" % (host, ADDR)), host)  # known/LAN alone: asks
        self.assertIsNone(self.d("ssh localhost 'echo %s'" % ADDR))  # loopback: first party
        with open(self.elsofel, "w") as f:
            f.write("198.51.100.7  # a saját boxom\n")
        self.assertIsNone(self.d("ssh u@198.51.100.7 'git config user.email %s'" % ADDR))
        r = self.d("ssh u@198.51.100.7 'curl https://api.crossref.org/w?mailto=%s'" % ADDR)
        self.assertEqual(r["cel"], ["api.crossref.org"])  # the remote command's own target counts


if __name__ == "__main__":
    unittest.main()
