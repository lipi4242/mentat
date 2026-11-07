"""A server started from the Bash tool blocks the turn (failure class: `python3 -m http.server`
in the foreground or with run_in_background; the USER got no reply).

The guard denies it in both modes with the one command that works (mentat_serve.py start),
like a missing capability receipt: the agent resolves it itself, the USER is not asked.
Builds, tests and the tool itself stay open.
"""
import _tmp_run  # noqa: F401  (first: every temp folder of the run is removed at exit)
import json
import unittest

from test_guard_kint import KintBase

SERVERS = (
    "python3 -m http.server 8000",
    "exec python3 -m http.server 8765 --bind 127.0.0.1",
    "cd site && python -m http.server",
    "setsid nohup python3 -m http.server 8000 > /tmp/x.log 2>&1 &",
    "timeout 3600 python3 -m http.server",
    "python3 -m flask run --port 5000",
    "flask run",
    "uvicorn app:app --reload",
    "python3 manage.py runserver",
    "php -S localhost:8000",
    "npx serve dist",
    "npx --yes http-server .",
    "npm run dev",
    "pnpm dev",
    "yarn start",
    "npx vite",
    "npx wrangler dev",
    "wrangler pages dev ./public",
    "streamlit run app.py",
    "hugo server",
    "bundle exec jekyll serve",
    "python3 -c 'import http.server'; python3 -m http.server",
    # CISO K1: option values, -m glued, runners, wrapper options
    "npx vite --port 3000",
    "vite --host localhost --port 5173",
    "python3 -mhttp.server",
    "uv run uvicorn app:app",
    "poetry run flask run",
    "npm --prefix web run dev",         # its dev runs another script that is a server
    "npm run dev:web",
    "pnpm -C web dev",
    "caffeinate -i python3 -m http.server",
    "nice -n 10 npm run dev",
    "timeout -s KILL 10 python3 -m http.server",
)
FOREGROUND = (  # not a web server, but it never returns either
    "tail -f app.log",
    "journalctl --user -f",
    "watch -n 5 ls",
    "npx tsc --watch",
    "nodemon app.js",
    "docker compose up",
    "ping example.com",
    "node server.js",       # the file listens
    "python3 app.py",       # the file serves forever
    "less README.md",
    "kubectl port-forward svc/web 8080:80",
)
FINE = (
    "python3 .mentat/bin/mentat_serve.py start lap --dir site",
    "python3 .mentat/bin/mentat_serve.py start dev --port 5173 -- npm run dev",
    "python3 .mentat/bin/mentat_serve.py stop lap",
    "npm run build",
    "npm test",
    "npx vite build",
    "python3 -m unittest discover",
    "wrangler deploy",
    "hugo",
    "curl -s http://127.0.0.1:8000/",
    "grep -n http.server notes.md",
    "uvicorn --version",
    "vite --version",
    "npx serve --help",
    "npm --prefix cli start",           # its start script is a command-line tool
    "npm run build && npm run lint",
    "pnpm --filter web dev",            # a workspace package: not decidable here, so open
    "yarn nincs-ilyen",
    "npm install",
    "tail -n 50 app.log",
    "docker compose up -d",
    "ping -c 3 example.com",
    "node build.js",
    "python3 report.py",
    "npx tsc",
    "journalctl --user -n 50",
    "python3 manage.py runserver --help",
)


class Szerver(KintBase):
    roles = False

    def setUp(self):
        super().setUp()
        scripts = {"dev": "vite", "start": "next start", "dev:web": "vite --port 5173",
                   "build": "vite build", "lint": "eslint ."}
        (self.root / "package.json").write_text(json.dumps({"scripts": scripts}))
        for sub, s in (("web", {"dev": "npm run serve", "serve": "python3 -m http.server"}),
                       ("cli", {"start": "node index.js"})):
            (self.root / sub).mkdir()
            (self.root / sub / "package.json").write_text(json.dumps({"scripts": s}))
        files = {"server.js": "require('http').createServer(h).listen(3000)\n", "build.js": "console.log(1)\n",
                 "app.py": "srv = HTTPServer(('', 8000), H)\nsrv.serve_forever()\n", "report.py": "print(1)\n",
                 "app.log": "x\n", "README.md": "x\n"}
        for name, text in files.items():
            (self.root / name).write_text(text)

    def why(self, cmd, **extra):
        r = self.run_guard(self.payload("Bash", dict({"command": cmd}, **extra)), None)
        out = json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else {}
        return out.get("permissionDecision", "allow"), out.get("permissionDecisionReason", "")

    def test_servers_are_denied_in_both_modes_with_the_tool_to_use(self):
        for cmd in SERVERS:
            self.assertEqual(self.bash(cmd), "deny", cmd)
            self.assertEqual(self.bash(cmd, mode="bypassPermissions"), "deny", "headless: " + cmd)
        decision, reason = self.why("python3 -m http.server 8765", run_in_background=True, timeout=3600000)
        self.assertEqual(decision, "deny")
        self.assertIn("mentat_serve.py start", reason)

    def test_foreground_watchers_and_listening_scripts_are_denied_too(self):
        for cmd in FOREGROUND:
            self.assertEqual(self.bash(cmd), "deny", cmd)
        self.assertIn("tail -n", self.why("tail -f app.log")[1])  # the one-shot form to use instead

    def test_the_command_the_tool_wraps_is_still_checked(self):  # CISO K2
        cmd = "python3 .mentat/bin/mentat_serve.py start x --port 5000 -- cp /etc/hosts .claude/settings.json"
        self.assertNotEqual(self.bash(cmd), "allow")

    def test_the_tool_builds_and_tests_stay_open(self):
        for cmd in FINE:
            self.assertEqual(self.bash(cmd), "allow", cmd)


if __name__ == "__main__":
    unittest.main()
