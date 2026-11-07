"""`fleet ask <ágens> --file kérdések.md` — kérdéssor egy ágensnek a saját boxán, Telegram és RC nélkül.

2026-10-29 (ágens-összeolvasztás): a fogadó ágens MÁS Claude-fiókon futott, a kérdező
session ListAgents-e nem látta, Remote Control sem volt. Ami működött: a kérdésfájl
ssh-n a boxra, egy egysoros mutató a tmux-pane-be („[X üzenete, nem Telegram] …"), a
válasz egy fájlba, az utolsó sora `KÉSZ`. Ehhez csak ssh kell a boxra.

Nem ír a pane-be, ha ott engedélykérő ablak áll (a beírt szöveg + Enter a felhasználó
nevében válaszolna — ugyanaz a szabály, mint a híd pane-őrében), ha egy indítási ablak
vagy lejárt login látszik (a válasz sosem jönne), vagy ha nincs ilyen tmux-session.
A dolgozó (foglalt) pane-be beír: a Claude Code a beírt sort sorba állítja.
"""
from __future__ import annotations
import re
import shlex
import time

from fleet.pane import dialog_in

DONE = "KÉSZ"
TAIL_LINES = 40                         # a pane alja számít (bridge/lib/pane-guard.mjs)
QUESTION = re.compile(r"Do you want to [^\n]{0,200}\?")
YES_OPTION = re.compile(r"^[\s│|]*(?:❯\s*)?1\.\s+Yes\b", re.M)
LOGIN = re.compile(r"Login expired|Please run /login|authentication_failed|OAuth token has expired", re.I)
BUSY = re.compile(r"esc to interrupt", re.I)


def pane_block(text: str | None) -> str | None:
    """Pure: miért NEM szabad most a pane-be írni (None = szabad)."""
    if text is None:
        return "nincs ilyen tmux-session (vagy nincs tmux) — fut az ágens? `fleet probe`"
    tail = "\n".join(text.splitlines()[-TAIL_LINES:])
    if QUESTION.search(tail) and YES_OPTION.search(tail):
        return "engedélykérő ablak áll a pane-ben — a beírt sor a felhasználó nevében válaszolna"
    d = dialog_in(tail)
    if d:
        return f"a claude a(z) „{d[0]}” ablaknál áll (megelőzés: {d[1]})"
    if LOGIN.search(tail):
        return "lejárt login látszik a pane-ben — előbb `fleet login <ágens>`, különben válasz sosem jön"
    return None


def pointer(sender: str, questions: str, answer: str) -> str:
    """Pure: az EGY sor, ami a pane-be kerül (sortörés nélkül: az Enter küldené el félúton)."""
    line = (f"[{sender} üzenete, nem Telegram] Kérdések: {questions} — olvasd el, és a válaszodat "
            f"írd ebbe a fájlba: {answer} ; az utolsó sora pontosan ez legyen: {DONE} . "
            f"Telegramra ne válaszolj erről.")
    return " ".join(line.split())


def answer_done(text: str | None) -> bool:
    """Pure: kész-e a válasz — az utolsó nem üres sor pontosan `KÉSZ`."""
    lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
    return bool(lines) and lines[-1] == DONE


def paths(ask_id: str, answer_path: str | None) -> tuple[str, str]:
    d = f"$HOME/.cache/fleet-ask/{ask_id}"
    return f"{d}/kerdesek.md", answer_path or f"{d}/valasz.md"


def _q(path: str) -> str:
    """A `$HOME/` előtagot a box shellje bontja ki; a többi idézve."""
    return '"$HOME"/' + shlex.quote(path[6:]) if path.startswith("$HOME/") else shlex.quote(path)


def put_script(qpath: str, apath: str) -> str:
    return (f"set -e; umask 077; q={_q(qpath)}; a={_q(apath)}; "
            f'if [ -e "$a" ]; then echo "VAN-MAR: $a" >&2; exit 17; fi; '
            f'mkdir -p "$(dirname "$q")" "$(dirname "$a")"; cat > "$q"; '
            f'printf "%s\\n%s\\n" "$q" "$a"')


def send_script(session: str, line: str) -> str:
    t = shlex.quote(f"={session}:")
    return f"tmux send-keys -t {t} -l {shlex.quote(line)} && sleep 0.3 && tmux send-keys -t {t} Enter"


def capture_script(session: str) -> str:
    return f"tmux capture-pane -p -t {shlex.quote(f'={session}:')}"


def ask(tgt, session: str, questions_text: str, *, sender: str, ask_id: str,
        answer_path: str | None = None, send: bool = True) -> dict:
    """Kérdésfájl a boxra + mutató a pane-be. Visszaad: {ok, answer_path (abszolút), notes}."""
    qpath, apath = paths(ask_id, answer_path)
    if not send:
        r = tgt.sh(f"echo {_q(apath)}", timeout=20)
        return {"ok": r.returncode == 0, "answer_path": r.stdout.strip() or apath, "notes": []}
    cap = tgt.sh(capture_script(session), timeout=20)
    why = pane_block(cap.stdout if cap.returncode == 0 else None)
    if why:
        return {"ok": False, "notes": [f"nem írok a(z) {session} pane-jébe: {why}"]}
    put = tgt.sh(put_script(qpath, apath), stdin=questions_text, timeout=30)
    if put.returncode != 0:
        return {"ok": False, "notes": [f"a kérdésfájl nem jutott a boxra (kód {put.returncode}): "
                                       f"{put.stderr.strip()[-300:]}"]}
    q_abs, a_abs = (put.stdout.strip().splitlines() + [qpath, apath])[:2]
    s = tgt.sh(send_script(session, pointer(sender, q_abs, a_abs)), timeout=20)
    if s.returncode != 0:
        return {"ok": False, "notes": [f"send-keys hiba (kód {s.returncode}): {s.stderr.strip()[-300:]}"]}
    notes = ["a pane dolgozik — a sor sorba áll, a válasz később jön"] if BUSY.search(cap.stdout or "") else []
    return {"ok": True, "answer_path": a_abs, "questions_path": q_abs, "notes": notes}


def wait_answer(tgt, answer_path: str, wait: float, *, every: float = 10,
                sleep=time.sleep, clock=time.time) -> tuple[bool, str]:
    """Pollozza a válaszfájlt, amíg az utolsó sora `KÉSZ` vagy lejár a `wait`. (kész?, szöveg)"""
    t0 = clock()
    while True:
        r = tgt.sh(f"cat {_q(answer_path)} 2>/dev/null || true", timeout=30)
        text = r.stdout if r.returncode == 0 else ""
        if answer_done(text) or clock() - t0 >= wait:
            return answer_done(text), text
        sleep(every)
