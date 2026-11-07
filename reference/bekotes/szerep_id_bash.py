"""F-41, a flotta prototípusának (bash_net.py) átvétele. Bash-parancs hálózati elemzése a F-41 kapuhoz.

    analyse(cmd, cwd, read) -> (net, hosts, text)   text: csak ami kimehet (a hálózati szegmensek)

Csak a parancs-pozícióban álló szót nézi (a `;`, `&&`, `|`, `(` utáni első szó, a
`timeout`/`env`/`sudo` előtagok után), így a heredoc-ba írt próza szavai („host”,
„open”) nem számítanak parancsnak. A heredoc törzse és a hivatkozott helyi fájlok
(`-H @f`, `-K f`, `python f.py`) a keresett szöveg részei. Egy interpreter-kód
(requests, fetch, …) csak akkor hálózat, ha interpreter is fut. Az `ssh gép '…'`,
`bash -c '…'` és `eval '…'` belső parancsát rekurzívan elemzi.
"""
import os
import re
import shlex
import subprocess

URL = re.compile(r"\b(?:https?|wss?|ftp)://(?:[^@/\s'\"]+@)?([A-Za-z0-9.-]+|\[[0-9a-f:]+\])", re.I)
NET_CMDS = {"curl", "wget", "http", "https", "xh", "nc", "ncat", "netcat", "telnet", "ssh", "scp", "sftp",
            "rsync", "ftp", "dig", "nslookup", "host", "ping", "open", "xdg-open", "lynx", "w3m",
            "aria2c", "openssl", "socat", "sendmail", "mail", "mutt", "swaks"}
TRANSPORT = {"ssh", "sftp", "scp", "rsync"}
ACCOUNT_CLIS = {"gh": "api.github.com", "gws": "www.googleapis.com", "wrangler": "api.cloudflare.com"}
INTERP = {"python", "python3", "node", "deno", "bun", "ruby", "perl", "php", "osascript"}
SHELLS = {"bash", "sh", "zsh", "dash"}
PREFIX = {"timeout", "env", "sudo", "command", "nohup", "time", "nice", "exec", "xargs", "npx", "uvx",
          "do", "then", "else", "elif", "if", "while", "until", "!"}  # a loop/if body is still a command
NET_CODE = re.compile(r"\b(requests|urllib|http\.client|httpx|aiohttp|socket|fetch\s*\(|axios|"
                      r"https?\.(get|request)|XMLHttpRequest|WebSocket|net/http|smtplib|"
                      r"file_get_contents\s*\(\s*['\"]https?)", re.I)
FILE_FLAGS = ("-H", "--header", "-d", "--data", "--data-binary", "--data-raw", "--data-urlencode",
              "-F", "--form", "-T", "--upload-file", "--post-file", "--body-file")
SSH_OPTS_WITH_ARG = set("-o -i -p -l -F -J -L -R -D -b -c -E -e -m -O -Q -S -W -w -B -P".split())
SSH_HOST = re.compile(r"^(?:[^@\s]+@)?([A-Za-z0-9.-]+)(?::|$)")
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n(.*?)\n\s*\2\b", re.S)
SEP = {";", "&&", "||", "|", "&", "(", ")", "{", "}", "|&", ";;", "$(", "`"}
MAX = 256 * 1024


def _read(path, cwd, read):
    p = os.path.join(cwd or ".", os.path.expanduser(path))
    try:
        if read and os.path.isfile(p) and os.path.getsize(p) <= MAX:
            with open(p, errors="replace") as f:
                return f.read()
    except OSError:
        pass
    return ""


def _segments(cmd):
    try:
        lex = shlex.shlex(cmd.replace("\\\n", " ").replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        toks = cmd.split()
    seg = []
    for t in toks:
        if t in SEP or set(t) <= set(";&|()"):
            if seg:
                yield seg
            seg = []
        else:
            seg.append(t)
    if seg:
        yield seg


def _strip(seg):
    while seg and (seg[0] in PREFIX or re.match(r"^[A-Za-z_]\w*=", seg[0]) or
                   (seg[0].startswith("-") or seg[0].isdigit()) and len(seg) > 1):
        seg = seg[1:]
    return seg


def _git_hosts(cwd):
    try:
        out = subprocess.run(["git", "-C", cwd or ".", "config", "--get-regexp", r"^remote\..*\.url$"],
                             capture_output=True, text=True, timeout=3).stdout.split()[1::2]
    except (OSError, subprocess.SubprocessError):
        return set()
    return {(URL.findall(u) or [SSH_HOST.match(u.split("@")[-1]).group(1)])[0]
            for u in out if URL.findall(u) or SSH_HOST.match(u.split("@")[-1])}


def analyse(cmd, cwd=None, read=True, depth=0):
    """text = what can go out: network segments, the files they send, network code (ssh: `ssh:<host>`)."""
    bodies = [m.group(3) for m in HEREDOC.finditer(cmd)]
    bare = HEREDOC.sub(" ", cmd)
    net, hosts, generic = False, set(), False
    parts, interp_parts, interp_files = [], [], []
    for seg in _segments(bare):
        seg = _strip(seg)
        if not seg:
            continue
        name, args = os.path.basename(seg[0]), seg[1:]
        seg_net, files = False, []
        if name in TRANSPORT:  # a célgép explicit; a belső parancsot lent rekurzívan nézzük
            seg_net = True
        elif name in NET_CMDS:
            generic = seg_net = True
        if name in ACCOUNT_CLIS:
            seg_net = True
            hosts.add(ACCOUNT_CLIS[name])
            owner = next((args[i + 1].split("/")[0] for i, a in enumerate(args[:-1]) if a in ("-R", "--repo")), "")
            if name == "gh" and owner:  # idegen repóba írt issue/komment: csak a saját fiók első fél
                hosts.add("github:" + owner.lower())
        if name == "git" and set(args) & {"push", "fetch", "pull", "clone", "ls-remote"}:
            seg_net = True
            hosts |= _git_hosts(cwd)
        for i, a in enumerate(args):
            nxt = args[i + 1] if i + 1 < len(args) else ""
            if a in FILE_FLAGS and nxt.startswith("@"):
                files.append(nxt[1:])
            elif a in ("-K", "--config") and name == "curl":
                files.append(nxt)
        inner = []
        if name in ("ssh", "sftp"):
            rest, i = [], 0
            while i < len(args):
                i, rest = (i + 2, rest) if args[i] in SSH_OPTS_WITH_ARG else \
                          (i + 1, rest if args[i].startswith("-") else rest + [args[i]])
            if rest and SSH_HOST.match(rest[0]):
                hosts.add("ssh:" + SSH_HOST.match(rest[0]).group(1))
            inner = rest[1:]
        elif name in ("scp", "rsync"):
            hosts |= {"ssh:" + SSH_HOST.match(a).group(1) for a in args
                      if ":" in a and "://" not in a and SSH_HOST.match(a)}
        elif (name in SHELLS and "-c" in args) or name == "eval":
            inner = args[args.index("-c") + 1:] if "-c" in args else args
        text = " ".join(seg)
        if inner and depth < 3:
            n2, h2, t2 = analyse(" ".join(inner), cwd, read, depth + 1)
            seg_net, generic = seg_net or n2, generic or n2
            hosts |= h2
            if name not in TRANSPORT:  # `bash -c` runs here: only its network part goes out
                text = " ".join(seg[:len(seg) - len(inner)]) + ("\n" + t2 if n2 else "")
        if name.rstrip("0123456789.") in INTERP:
            interp_parts.append(text)
            interp_files += [a for a in args[:1] if not a.startswith("-")] + files
        if seg_net:
            net = True
            parts.append(text + "".join("\n" + _read(f, cwd, read) for f in files))
    code = "\n".join(bodies + interp_parts + [_read(f, cwd, read) for f in interp_files])
    talks = bool(interp_parts and NET_CODE.search(code))
    text = "\n".join(parts + ([code] if talks else []))
    if generic or talks:
        hosts |= set(URL.findall(text))
    return net or talks, hosts, text
