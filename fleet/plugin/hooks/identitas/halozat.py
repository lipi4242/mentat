"""Megy-e ki valami a hálózatra egy eszközhívással, és hova (F-41).

    outbound(tool, inp, cwd) -> Out(net, hosts, text)
      net   : a hívás hálózatra írhat
      hosts : a felismert célhostok (üres = ismeretlen cél)
      text  : a hívás szövege, plusz a hivatkozott helyi fájlok (`-H @f`, `-d @f`, `-K f`,
              `python f.py`, `node f.mjs`) tartalma, max. 256 KB fájlonként

Heurisztika: a parancs szövegéből dolgozik, a futás közben összerakott értéket
(változó, összefűzés, hálózatról letöltött szkript) nem látja. Ezt a határt a
visszamenőleges szkenner és az ágens-identitás zárja (lásd a F-41 tervet).
"""
import pathlib
import sys
from dataclasses import dataclass, field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import bash_net  # noqa: E402
import ident  # noqa: E402

BROWSER_HINT = ("chrome", "browser", "playwright", "puppeteer", "cua", "navigate", "fetch", "http", "web")
URL = bash_net.URL
READ_FILES = True  # a visszamenőleges szkenner kikapcsolja: a fájl ma már mást tartalmazhat


@dataclass
class Out:
    net: bool = False
    hosts: set = field(default_factory=set)
    text: str = ""


def outbound(tool, inp, cwd=None):
    out = Out()
    flat = " ".join(str(v) for v in (inp or {}).values())
    if tool == "Bash":
        cmd = str((inp or {}).get("command", ""))
        out.net, out.hosts, out.text = bash_net.analyse(cmd, cwd, READ_FILES)
        if out.net:  # `E=$(git config user.email); curl -d "$E" …`: the value is read locally, sent out
            out.text += "".join("\n" + m.group(0) for m in ident.SOURCE_EXPR.finditer(cmd))
    elif tool == "WebFetch":
        out.net, out.text = True, str((inp or {}).get("url", ""))  # a prompt az Anthropicnál marad
        out.hosts |= set(URL.findall(out.text))
    elif tool == "WebSearch":
        out.net, out.text, out.hosts = True, flat, {"<keresomotor>"}
    elif tool.startswith("mcp__"):
        out.net, out.text = True, flat
        out.hosts |= set(URL.findall(flat))
        if not any(h in tool.lower() for h in BROWSER_HINT):
            out.hosts.add("<mcp:%s>" % tool.split("__")[1])  # a szerver maga is címzett
    else:
        out.text = flat
    return out
