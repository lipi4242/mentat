"""A checkout cseréje a cél-tagre (docs/migration/boxes.md 2–3. lépés).

Két elrendezés:
  legacy  — `~/fleet-leader` valódi git-checkout (a régi fleet-leader-dev). A publikus
            repó a taggel `~/src/mentat`-ba klónozódik, a régi könyvtár
            `~/fleet-leader.pre-mentat` lesz, a helyére symlink kerül.
  symlink — `~/fleet-leader` → `~/src/mentat/fleet`. `fetch --tags` + `checkout <tag>`.
A reconcile-timerek a cserétől az ELLENŐRZÉS VÉGÉIG állnak: az új kód ne
avatkozzon be (a gyors timer 30 mp-enként fut), mielőtt az ellenőrzés átengedte.
Minden állapotjelző a művelet ELŐTT íródik, hogy egy megszakítás után is
visszaálljon (box_checkout_undo).
"""
from __future__ import annotations
import json
import os

from fleet.box_checkout_undo import rollback, timers  # noqa: F401  (a lépés része)
from fleet.box_ctx import Ctx, SLOW_TIMEOUT_S, TIMERS, WOULD_ACT, StepFailed, git, git_try, sh


def _norm(url: str) -> str:
    u = url.strip().rstrip("/")
    u = u[:-4] if u.endswith(".git") else u
    ssh = "git" + "@github.com:"   # az scp-szerű SSH-forma (szétbontva: a kiadási e-mail-szűrő miatt)
    return "https://github.com/" + u.split(":", 1)[1] if u.startswith(ssh) else u


def _origin_ok(ctx: Ctx) -> None:
    got = git_try(ctx, ctx.src, "remote", "get-url", "origin") or ""
    if _norm(got) != _norm(ctx.url):
        raise StepFailed(f"{ctx.src} originje {got or '(nincs)'}, a --repo-url {ctx.url} — "
                         "nem töltök le más repóból; add meg a helyes --repo-url-t")


def detect(ctx: Ctx) -> None:
    """Csak olvas: elrendezés, előző sha/tag/ág a `ctx.state`-be."""
    link, st = ctx.link, ctx.state
    if link.is_symlink():
        if link.resolve() != (ctx.src / "fleet").resolve():
            raise StepFailed(f"{link} → {os.readlink(link)}: ismeretlen elrendezés (várt: {ctx.src}/fleet)")
        st["layout"], repo = "symlink", ctx.src
        _origin_ok(ctx)
    elif (link / ".git").exists():
        st["layout"], repo = "legacy", link
    else:
        raise StepFailed(f"nincs {link} checkout (se git-könyvtár, se symlink) — ez nem fleet-box")
    st["prev_sha"] = git(ctx, repo, "rev-parse", "HEAD")
    st["prev_tag"] = git_try(ctx, repo, "describe", "--tags", "--exact-match", "HEAD")
    st["target_sha"] = git_try(ctx, ctx.src, "rev-parse", "--verify", "--quiet", f"{ctx.tag}^{{commit}}") \
        if st["layout"] == "symlink" else None
    st["checkout_noop"] = st["layout"] == "symlink" and (
        st["prev_tag"] == ctx.tag or (st["target_sha"] is not None and st["target_sha"] == st["prev_sha"]))


def plan(ctx: Ctx) -> list[str]:
    detect(ctx)
    st = ctx.state
    now = f"{st['prev_tag'] or 'nincs tag'} ({st['prev_sha'][:10]})"
    if st["checkout_noop"]:
        return [f"checkout: {ctx.src} már a {ctx.tag}-en — nincs teendő"]
    tail = "timerek az ellenőrzés után indulnak"
    if st["layout"] == "legacy":
        return [f"checkout: legacy {ctx.link} @ {now}",
                f"  → klón {ctx.url} @ {ctx.tag} ide: {ctx.src}",
                f"  → timerek állnak; {ctx.link} → {ctx.backup}; symlink {ctx.link} → {ctx.src}/fleet; {tail}"]
    return [f"checkout: {ctx.src} @ {now} → {ctx.tag} (fetch --tags + checkout; {tail})"]


def _clean_or_die(ctx: Ctx, repo) -> None:
    dirty = git(ctx, repo, "status", "--porcelain", "--untracked-files=no")
    if dirty:
        raise StepFailed(f"{repo}: kézi módosítás a checkoutban — nem írom felül:\n{dirty}")


def apply(ctx: Ctx) -> None:
    st = ctx.state
    if st["checkout_noop"]:
        return
    if st["layout"] == "legacy" and (ctx.backup.exists() or ctx.backup.is_symlink()):
        raise StepFailed(f"{ctx.backup} már létezik — egy korábbi átállás mentése; kézzel nézd meg")
    if ctx.src.exists() and not (ctx.src / ".git").exists():
        raise StepFailed(f"{ctx.src} létezik, de nem git-checkout — nem nyúlok hozzá")
    # a lassú rész (hálózat) a timerek leállítása ELŐTT: addig minden fut tovább
    if (ctx.src / ".git").exists():
        _origin_ok(ctx)
        _clean_or_die(ctx, ctx.src)
        git(ctx, ctx.src, "fetch", "--quiet", "--tags", "origin")
    else:
        ctx.src.parent.mkdir(parents=True, exist_ok=True)
        st["cloned"] = True                      # előbb a jelző: egy félbehagyott klón is takarítható
        sh(ctx, ["git", "clone", "--quiet", "--branch", ctx.tag, ctx.url, str(ctx.src)], what="git clone")
        st["clone_done"] = True
    st["target_sha"] = git(ctx, ctx.src, "rev-parse", "--verify", f"{ctx.tag}^{{commit}}")
    st["src_prev_sha"] = git_try(ctx, ctx.src, "rev-parse", "HEAD")
    st["src_prev_branch"] = git_try(ctx, ctx.src, "symbolic-ref", "-q", "--short", "HEAD")
    st["timers"] = [t for t in TIMERS
                    if ctx.run(["systemctl", "--user", "is-active", t]).stdout.strip() == "active"]
    st["timers_stopped"] = True
    timers(ctx, "stop")
    st["switched"] = True
    git(ctx, ctx.src, "-c", "advice.detachedHead=false", "checkout", "--quiet", st["target_sha"])
    if st["layout"] == "legacy":
        os.rename(ctx.link, ctx.backup)
        os.symlink(ctx.src / "fleet", ctx.link)
    # a timerek az ellenőrzés végén indulnak (verify)


def verify(ctx: Ctx) -> None:
    """Az ÚJ kód válaszol, a release-tuple az új sha, és a reconcile nem akar
    beavatkozni ott, ahol előtte sem akart — csak UTÁNA indulnak a timerek."""
    st = ctx.state
    if st.get("checkout_noop"):
        return
    sh(ctx, [ctx.new_fleet, "--version"], what="új fleet --version")
    out = sh(ctx, [ctx.new_fleet, "release"], what="új fleet release")
    want = git(ctx, ctx.src, "rev-parse", "--short", "HEAD")
    try:
        got = json.loads(out).get("sha") or ""
    except (ValueError, AttributeError):
        raise StepFailed(f"a `fleet release` kimenete nem JSON: {out[:200]!r}")
    if not got or not (got.startswith(want) or want.startswith(got)):
        raise StepFailed(f"a release-tuple sha-ja {got!r}, a checkout {want!r} — nem az új kód fut")
    obs = ctx.run_t([str(ctx.new_fleet), "reconcile", "--observe"], SLOW_TIMEOUT_S)
    if obs.returncode != 0:
        raise StepFailed(f"az új reconcile --observe → kód {obs.returncode}: {(obs.stderr or '')[-200:]}")
    after = would_act(obs.stdout or "")
    new = sorted(set(after) - set(st.get("observe_before", [])))
    if new:
        raise StepFailed("a reconcile a váltás után beavatkozna, előtte nem: " + "; ".join(after[a] for a in new))
    timers(ctx, "start")
    st["timers_stopped"] = False
    for t in st.get("timers", []):
        if ctx.run(["systemctl", "--user", "is-active", t]).stdout.strip() != "active":
            raise StepFailed(f"{t} nem aktív a csere után")


def would_act(text: str) -> dict[str, str]:
    """ágens → sor, ahol a reconcile --observe beavatkozna."""
    return {ln.split(":", 1)[0]: ln for ln in text.splitlines() if WOULD_ACT in ln and ":" in ln}
