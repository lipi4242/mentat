"""Titok-kapu, az ágens-interjúk (11-09) téves tiltásai: ps, a híd naplója, az átirat-tiltás oka.
A javítás nélkül minden „szabad" eset tilt, és az átirat-tiltás nem ad kiutat.
Futtatás: python3 -I -m unittest discover -s plugin/hooks/identitas -p 'test_titok_interju.py' -q
"""
import io
import json
import os
import pathlib
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import titok_kapu as K  # noqa: E402
from test_titok_kapu import Base  # noqa: E402


class PsNemKornyezet(Base):
    """a `-e` minden processz, a `-o` utáni szó formátum; csak a valódi env-kiírás tilt."""

    def test_szabad_ps_alakok(self):
        for cmd in ("ps -eo pid,etimes,args | grep bridge", "ps -o pid,etime -p 123", "ps -ef", "ps aux",
                    "ps -p 1 -o pid,command", "ps axo pid,etime,args", "ps -opid,etimes", "ps -A",
                    "ps -e -o pid,user,etimes,args --sort=etimes"):
            self.assertIsNone(self.bash(cmd), cmd)

    def test_kornyezet_kiiro_ps_tilt(self):
        for cmd in ("ps e", "ps eww", "ps auxe", "ps aux e", "ps -E", "ps -axE", "ps -eE -o pid,command",
                    "ps axoe", "ps -o pid,environ", "ps -e e", "ps -ef | cat; ps eww 1"):
            self.assertTrue(self.bash(cmd), cmd)


class HidNaplo(Base):
    """a híd üzenetnaplója (*.jsonl) olvasható, a mellette álló token/env fájl nem."""

    def setUp(self):
        super().setUp()
        for d in (".config/vilma/sub-etha", ".config/vilma/telegram-inbox"):
            os.makedirs(os.path.join(self.home, d))
        self.put(".config/vilma/telegram.env", "TELEGRAM_BOT_TOKEN=%s\n" % "HAMIS")
        self.put(".config/vilma/sub-etha/send.mjs", "// kod\n")
        self.put(".config/vilma/telegram-inbox/delivery-2026-11-09.jsonl", '{"type":"inbound","text":"szia"}\n')
        self.put(".config/vilma/telegram-inbox/events-2026-11-09.jsonl", '{"update_id":1}\n')

    def test_napló_olvashato(self):
        for cmd in ("tail ~/.config/vilma/sub-etha/*.jsonl",
                    "tail -n 50 ~/.config/vilma/telegram-inbox/*.jsonl",
                    "tail -n 50 ~/.config/vilma/telegram-inbox/delivery-*.jsonl",
                    "grep szia ~/.config/vilma/telegram-inbox/delivery-2026-11-*.jsonl",
                    "tail ~/.config/vilma/telegram-inbox/delivery-2026-11-1?.jsonl"):
            self.assertIsNone(self.bash(cmd), cmd)

    def test_token_es_env_marad_tiltva(self):
        self.put(".config/vilma/sub-etha/bot.token", "HAMIS\n")
        for cmd in ("cat ~/.config/vilma/telegram.env", "cat ~/.config/vilma/*.env",
                    "cat ~/.config/vilma/sub-etha/*.env", "cat ~/.config/vilma/sub-etha/*token*.jsonl",
                    "cat ~/.config/vilma/sub-etha/*", "cat ~/.config/vilma/sub-etha/*.token",
                    "cat ~/.config/vilma/sub-etha/../*.env",
                    "cat ~/.config/vilma/telegram-inbox/*.json", "cat ~/.config/vilma/x/telegram-inbox/*.jsonl"):
            self.assertTrue(self.bash(cmd), cmd)


class AtiratIndoklas(Base):
    """a saját átirat greppelése TILTOTT marad, de az ok megmondja, miért, és hová menjen."""

    def reason(self, data):
        out = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO(json.dumps(data))), mock.patch.object(sys, "stdout", out):
            self.assertEqual(K.main(["--hook"]), 0)
        d = json.loads(out.getvalue())["hookSpecificOutput"]
        self.assertEqual(d["permissionDecision"], "deny")
        return d["permissionDecisionReason"]

    def test_grep_az_atiraton_tilt_es_kiutat_ad(self):
        self.put(".claude/projects/y/s1.jsonl", "{}\n")
        for data in ({"tool_name": "Grep", "cwd": self.home,
                      "tool_input": {"pattern": "x", "path": os.path.join(self.home, ".claude/projects/y")}},
                     {"tool_name": "Bash", "cwd": self.home,
                      "tool_input": {"command": "grep -n hiba ~/.claude/projects/y/s1.jsonl"}},
                     {"tool_name": "Read", "cwd": self.home,
                      "tool_input": {"file_path": os.path.join(self.home, ".claude/projects/y/s1.jsonl")}}):
            r = self.reason(data)
            self.assertIn("szándékosan zárt", r, data["tool_name"])
            self.assertIn("memory/", r)
            self.assertIn("anytime-tick.log", r)

    def test_mas_tiltas_nem_kapja_az_atirat_szoveget(self):
        r = self.reason({"tool_name": "Bash", "cwd": self.home, "tool_input": {"command": "cat vilma/.env"}})
        self.assertNotIn("szándékosan zárt", r)


if __name__ == "__main__":
    unittest.main()
