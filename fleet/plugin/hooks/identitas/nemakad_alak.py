"""A megtagadott hívás alakja, a modellnek szóló javaslat és a maszkolt napló-előtag.

Tiszta függvények, kivétel nélkül: bármilyen bemenetre (nem szöveg, óriási, fura jelek)
egy alakot és egy rövid, titok-mentes előtagot adnak. Regex csak fix mintákkal, a bemenetből
soha nem épül minta (a kapu korábbi re.error-hibája ebből jött).
"""
import re

MAX_SCAN = 65536  # ennyi karaktert nézünk; a többi nem változtat az alakon
PREFIX = 80

_RM_VAR = re.compile(r"(?:^|[;&|(\s])rm\s[^;&|\n]*\$(?!\{[A-Za-z_][A-Za-z0-9_]*:\?)")
_CD_WRITE = re.compile(r"(?:^|[;&|(\s])cd\s[^;&|\n]*(?:&&|;|\|\|)")
_WRITE = re.compile(r"(?:>|\b(?:rm|mv|cp|tee|mkdir|rmdir|touch|chmod|chown|ln|sed\s+-i|git\s+"
                    r"(?:commit|push|checkout|reset|clean|add|rm|mv|merge|rebase|stash)|npm|pip|make)\b)")

_SECRETS = [
    re.compile(r"(?i)(authorization:\s*(?:bearer|basic)\s+)\S+"),
    re.compile(r"(?i)(\b[\w.-]*(?:token|secret|passw\w*|pwd|api[_-]?key|auth\w*|cookie|session)[\w.-]*"
               r"\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
    re.compile(r"(?i)(--(?:token|password|passwd|secret|api-key|key)[ =])\S+"),
    re.compile(r"(?i)((?:^|\s)(?:-u|--user)(?:\s+|=)?)(?:\"[^\"]*:[^\"]*\"|'[^']*:[^']*'|[^\s:]*:\S+)"),  # curl -u x:y
    re.compile(r"(?i)(\bsshpass\b[^;&|\n]*?\s-p\s*)(?:\"[^\"]*\"|'[^']*'|\S+)"),  # sshpass -p jelszó
    re.compile(r"(?i)(\b(?:mysql\w*|mariadb\w*|psql|pg_\w+)\b[^;&|\n]*?\s-p)(?=\S)(?:\"[^\"]*\"|'[^']*'|\S+)"),  # -p<jelszó>
    re.compile(r"(://)[^/\s:@]+:[^/\s@]+(@)"),
]
# Hosszú, szóköz nélküli jelsor (perjel nélkül, hogy az útvonal olvasható maradjon), és az
# ismert tokenelőtagok perjellel együtt is.
_LONG = re.compile(r"[A-Za-z0-9+_=\-]{24,}|\b(?:gh[pousr]_|github_pat_|sk-|xox[a-z]-|AKIA|eyJ)[A-Za-z0-9+/_=.\-]+")

GENERIC = ("Ehhez emberi jóváhagyás kellene, de most senki nem tudja megadni (a FELHASZNÁLÓ "
           "nincs a gépnél, vagy csak Telegramon/RC-n ér el). Ne próbáld újra ugyanezt a parancsot. "
           "Válassz biztonságosabb utat, vagy hagyd ki, és írd be a reggeli jelentésedbe, mit "
           "hagytál ki és miért.")
HINTS = {
    "rm-valtozo": ("Az `rm` egy ellenőrizetlen változót kap útvonalként (`$D/...`); ha a változó üres, "
                   "a `/`-től törölne. Írd át így: `rm -rf \"${D:?}/x\"` (a `:?` üres változónál "
                   "megáll), vagy írd ki a teljes, abszolút útvonalat literálisan."),
    "cd-iras": ("Egy parancsban `cd` és utána írás: ezt a Claude Code mindig jóváhagyatja. Írd át "
                "abszolút útvonalakra (`git -C /a/repo commit ...`, `make -C /a/dir`, "
                "`/a/dir/fajl`), vagy tedd a `cd`-t külön hívásba."),
}


def _text(tool_input):
    if isinstance(tool_input, dict):
        c = tool_input.get("command")
        if isinstance(c, str):
            return c
        for k in ("file_path", "path", "url", "notebook_path"):
            if isinstance(tool_input.get(k), str):
                return tool_input[k]
        return ""
    return tool_input if isinstance(tool_input, str) else ""


def shape(tool_name, tool_input):
    """'rm-valtozo' | 'cd-iras' | 'egyeb'."""
    if tool_name != "Bash":
        return "egyeb"
    t = _text(tool_input)[:MAX_SCAN]
    if _RM_VAR.search(t):
        return "rm-valtozo"
    m = _CD_WRITE.search(t)
    if m and _WRITE.search(t, m.end()):
        return "cd-iras"
    return "egyeb"


def message(tool_name, tool_input):
    hint = HINTS.get(shape(tool_name, tool_input))
    tool = tool_name if isinstance(tool_name, str) else "?"
    head = "Megtagadva (%s), mert nincs, aki jóváhagyja. " % tool[:60]
    return head + (hint + " " if hint else "") + GENERIC


def mask(text):
    """A titoknak látszó részek helyére ***; utána vágunk, így a vágás nem hagy félig látszó titkot."""
    t = text[:MAX_SCAN] if isinstance(text, str) else ""
    for rx in _SECRETS:
        t = rx.sub(lambda m: m.group(1) + "***" + (m.group(2) if rx.groups > 1 and m.group(2) == "@" else ""), t)
    t = _LONG.sub("***", t)
    t = " ".join(t.split())
    return t[:PREFIX] + ("…" if len(t) > PREFIX else "")


def prefix(tool_input):
    return mask(_text(tool_input))
