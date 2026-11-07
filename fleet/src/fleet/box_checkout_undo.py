"""A checkout-csere visszaállítása. Az ÁLLAPOTOT nézi (létezik-e a mentés, symlink-e
a link), nem azt, hogy melyik művelet futott le: egy megszakítás bármelyik két
lépés között érkezhet. Minden művelet külön őrzött; ami bukik, a
`rollback_errors`-ba kerül, és a futás eredménye akkor `rollback-failed`.

A visszaállt kóddal újra települ minden ágens, amelynek unitját az új kód írta
(vagy írhatta: egy megszakított `fleet install` nem áll vissza magától) — ez a
felügyeleti unitokat is visszaírja a régi útra.
"""
from __future__ import annotations
import os
import shutil

from fleet.box_ctx import Ctx, git, sh


def timers(ctx: Ctx, verb: str) -> None:
    if ctx.state.get("timers"):
        sh(ctx, ["systemctl", "--user", verb, *ctx.state["timers"]], what=f"timerek {verb}")


def guard(ctx: Ctx, label: str, fn) -> bool:
    try:
        fn()
        return True
    except (Exception, KeyboardInterrupt) as e:  # noqa: BLE001 — a következő művelet még fusson
        ctx.state.setdefault("rollback_errors", []).append(f"{label}: {e}")
        ctx.not_rolled_back.append(f"{label}: BUKOTT ({e})")
        return False


def _restore_legacy(ctx: Ctx) -> None:
    if ctx.link.is_symlink():
        ctx.link.unlink()
    if ctx.backup.is_dir() and not ctx.link.exists():
        os.rename(ctx.backup, ctx.link)


def _restore_src(ctx: Ctx) -> None:
    st = ctx.state
    git(ctx, ctx.src, "-c", "advice.detachedHead=false", "checkout", "--quiet",
        st.get("src_prev_branch") or st["src_prev_sha"])


def _reinstall(ctx: Ctx, agent: str) -> None:
    r = ctx.run([str(ctx.link / "bin" / "fleet"), "install", agent])
    if r.returncode not in (0, 3):
        raise RuntimeError(f"kód {r.returncode} — `fleet install {agent}` kézzel")


def rollback(ctx: Ctx) -> list[str]:
    st, notes = ctx.state, []
    if st.get("cloned") and not st.get("clone_done") and ctx.src.exists():
        if guard(ctx, "a félbehagyott klón törlése", lambda: shutil.rmtree(ctx.src)):
            notes.append(f"félbehagyott klón törölve: {ctx.src}")
    if not (st.get("switched") or st.get("timers_stopped")):
        return notes
    if not st.get("timers_stopped"):
        guard(ctx, "timerek leállítása", lambda: timers(ctx, "stop"))
    if st.get("switched"):
        if st["layout"] == "legacy":
            if guard(ctx, "a régi könyvtár visszaállítása", lambda: _restore_legacy(ctx)):
                notes.append(f"checkout visszaállítva: {ctx.backup} → {ctx.link} ({st['prev_sha'][:10]})")
        elif st.get("src_prev_sha"):
            if guard(ctx, "a checkout visszaállítása", lambda: _restore_src(ctx)):
                notes.append(f"checkout visszaállítva: {ctx.src} → "
                             f"{st.get('src_prev_branch') or st['prev_tag'] or st['src_prev_sha'][:10]}")
    if guard(ctx, "timerek indítása", lambda: timers(ctx, "start")):
        st["timers_stopped"] = False
    if st.get("switched"):
        st["switched"] = False
        guard(ctx, "a release-tuple újraírása",
              lambda: sh(ctx, [ctx.link / "bin" / "fleet", "release"], what="régi fleet release"))
        for a in list(dict.fromkeys(st.pop("dirty", []))):   # az új kóddal írt unit vissza a régire
            if guard(ctx, f"{a}: újratelepítés a visszaállt kóddal", lambda a=a: _reinstall(ctx, a)):
                notes.append(f"{a}: unit (és felügyelet) újra a visszaállt kóddal telepítve")
    if st.get("clone_done") and st["layout"] == "legacy":
        ctx.not_rolled_back.append(f"{ctx.src} megmaradt (a klón; törölhető)")
    return notes
