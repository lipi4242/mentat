"""F-41 identitás-kapu (szerep_kapu_id): a 2026-10-10-i eset mintája, az első fél, a kódolások,
az ismert korlátok és a Codex-review esetei. A flotta prototípusának tesztjei átvéve."""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import os
import tempfile
import unittest

import szerep_id as ident
import szerep_id_elsofel as elsofel
import szerep_kapu_id as kapu

ADDR = "teszt.elek@example.com"
IDS = ident.Ids([ADDR])
ALLOW = elsofel.Allow(elsofel.BASE_HOSTS + ["example.com", "*.example.com", "*.pelda.workers.dev"],
                      elsofel.BASE_TOOLS)


def d(tool, **inp):
    return kapu.decide(tool, inp, tempfile.gettempdir(), IDS, ALLOW)


class Elkapja(unittest.TestCase):
    def test_polite_pool_user_agent(self):  # a 10-10-i eset alakja
        r = d("Bash", command='curl -s -A "Mozilla/5.0 (kutato; mailto:%s)" "https://api.openalex.org/works?x=1"' % ADDR)
        self.assertEqual(r["cel"], ["api.openalex.org"])

    def test_mailto_param_python(self):
        r = d("Bash", command="python3 -c \"import urllib.request as u; u.urlopen('https://api.crossref.org/works?mailto=%s')\"" % ADDR)
        self.assertIn("api.crossref.org", r["cel"])

    def test_url_kodolt_es_base64(self):
        self.assertTrue(d("WebFetch", url="https://wiki.example/api?from=" + ADDR.replace("@", "%40"), prompt="x"))
        import base64
        b = base64.b64encode(("hello " + ADDR).encode()).decode()
        self.assertTrue(d("Bash", command="curl -H 'X-U: %s' https://tracker.example/c" % b))

    def test_hash_elt_email(self):
        import hashlib
        h = hashlib.sha256(ADDR.encode()).hexdigest()
        self.assertTrue(d("Bash", command="curl -d em=%s https://capi.example/events" % h))

    def test_fajlbol_olvasott_header(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            f.write("From: " + ADDR)
        try:
            self.assertTrue(d("Bash", command="curl -H @%s https://api.example.org/x" % f.name))
        finally:
            os.unlink(f.name)

    def test_szkript_fajl_halozattal(self):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write("import requests\nrequests.get('https://api.example.org', headers={'From': '%s'})\n" % ADDR)
        try:
            self.assertTrue(d("Bash", command="python3 " + f.name))
        finally:
            os.unlink(f.name)

    def test_futas_kozbeni_forras(self):
        r = d("Bash", command='curl -A "bot (mailto:$(git config user.email))" https://api.example.org')
        self.assertIn("forras-kifejezes", r["azonosito"])

    def test_bongeszo_urlap_es_kereso(self):
        self.assertEqual(d("mcp__claude-in-chrome__form_input", ref="r1", value=ADDR)["cel"], ["<ismeretlen cel>"])
        self.assertTrue(d("WebSearch", query='"%s"' % ADDR))
        self.assertTrue(d("mcp__valami_szerver__lookup", q=ADDR))

    def test_ismeretlen_cel(self):
        self.assertTrue(d("Bash", command="ssh -i ~/.ssh/k root@example.net 'echo %s'" % ADDR))


class TriazsEsetek(unittest.TestCase):
    """A 2026-10-24-i Mac-mérés hamis pozitívjaiból és egy rejtett útjából."""

    def test_heredoc_proza_nem_parancs(self):
        doc = "cat > jegyzet.md <<'EOF'\nA host open mail: %s, fetch( itt csak szöveg.\nEOF" % ADDR
        self.assertIsNone(d("Bash", command=doc))

    def test_ssh_kapcsolo_ertekkel_es_belso_curl(self):
        allow = elsofel.Allow(ALLOW.hosts + ["example.net"], ALLOW.tools)
        box = "timeout 60 ssh -o ConnectTimeout=15 u@example.net 'git log --format=%%ae -1; echo %s'" % ADDR
        self.assertIsNone(kapu.decide("Bash", {"command": box}, tempfile.gettempdir(), IDS, allow))
        inner = "ssh -o X=1 u@example.net 'curl -A \"x %s\" https://api.crossref.org/w'" % ADDR
        r = kapu.decide("Bash", {"command": inner}, tempfile.gettempdir(), IDS, allow)
        self.assertEqual(r["cel"], ["api.crossref.org"])

    def test_python_stdin_heredoc(self):
        cmd = "python3 - <<'PY'\nimport urllib.request as u\nu.urlopen('https://api.openalex.org/?mailto=%s')\nPY" % ADDR
        self.assertEqual(d("Bash", command=cmd)["cel"], ["api.openalex.org"])


class Atengedi(unittest.TestCase):
    def test_elso_fel(self):
        self.assertIsNone(d("Bash", command="curl -d email=%s https://admin.example.com/otp" % ADDR))
        self.assertIsNone(d("Bash", command="curl -H 'X: %s' https://api.pelda.workers.dev/x" % ADDR))
        self.assertIsNone(d("Bash", command="gh pr create --body 'by %s' && git push" % ADDR))
        self.assertIsNone(d("mcp__claude_ai_Gmail__send_message", to="x@example.org", body=ADDR))
        self.assertIsNone(d("Bash", command="gh pr create --body '%s · https://claude.com/x'" % ADDR))

    def test_nincs_halozat_vagy_azonosito(self):
        self.assertIsNone(d("Bash", command="git config user.email && git log -1"))
        self.assertIsNone(d("Bash", command="curl https://api.openalex.org/works"))
        self.assertIsNone(d("Edit", file_path="x", old_string=ADDR, new_string="y"))


class IsmertKorlat(unittest.TestCase):
    """Ezeket a kapu NEM fogja meg; a terv a szkennerrel és az ágens-identitással zárja."""

    def test_valtozoban_osszerakott(self):
        self.assertIsNone(d("Bash", command='U=teszt.elek; D=example.com; curl -A "$U@$D" https://x.example'))

    def test_megforditott_szoveg(self):
        self.assertIsNone(d("Bash", command="curl -A %s https://x.example" % ADDR[::-1]))


class CodexReview(unittest.TestCase):
    """2026-10-24, Codex: URL-safe base64, és a GitHub mint szolgáltató nem megbízható címzett."""

    def test_urlsafe_base64(self):
        import base64
        for pre in range(3):
            b = base64.urlsafe_b64encode(b"x" * pre + ("?>~" + ADDR).encode()).decode()
            self.assertTrue(d("Bash", command="curl -H 'X: %s' https://t.example/c" % b))

    def test_gh_idegen_repoba(self):
        allow = elsofel.Allow(ALLOW.hosts + ["github:sajat"], ALLOW.tools)
        own = "gh issue create -R sajat/x --body 'cim: %s'" % ADDR
        alien = "gh issue create -R idegen/x --body 'cim: %s'" % ADDR
        self.assertIsNone(kapu.decide("Bash", {"command": own}, tempfile.gettempdir(), IDS, allow))
        r = kapu.decide("Bash", {"command": alien}, tempfile.gettempdir(), IDS, allow)
        self.assertEqual(r["cel"], ["github:idegen"])

    def test_git_push_a_githubra_elso_fel(self):  # Krisz döntése, 2026-10-24
        repo = tempfile.mkdtemp()
        os.system("git -C %s init -q && git -C %s remote add origin https://github.com/sajat/x.git" % (repo, repo))
        cmd = "git -c user.email=%s commit -qm x && git push origin main" % ADDR
        self.assertIsNone(kapu.decide("Bash", {"command": cmd}, repo, IDS, ALLOW))


class GoogleConnector(unittest.TestCase):
    def test_k3_calls_with_the_users_address_are_first_party(self):  # mentat_google.py (#78)
        man = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manifest")
        cmd = "python3 mentat_google.py calendar create --title T --start 2026-11-06T10:00 --end 2026-11-06T11:00 " \
              "--notify none --guests %s" % ADDR
        self.assertIsNone(kapu.decide("Bash", {"command": cmd}, man, IDS, ALLOW))

if __name__ == "__main__":
    unittest.main()
