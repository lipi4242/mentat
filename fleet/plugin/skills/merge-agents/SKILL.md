---
name: merge-agents
description: "Retire / merge / take over / upgrade an agent — ágens kivezetése, nyugdíjazása, beolvasztása, feladatainak átvétele, frissítése a legújabb Mentatra: KÖTELEZŐ eljárás, MIELŐTT bármit csinálsz. Használd, ha egy ágenst kivezetnek vagy végleg leállítanak, ha egy ágens átveszi egy másik munkáját („X vegye át Y meetingjeit”), ha két ágenst összeolvasztanak, vagy ha egy ágenst frissíteni kell úgy, hogy a funkciói megmaradjanak. English: use BEFORE acting whenever an agent is retired, decommissioned, sunset, merged or consolidated into another, takes over another agent's duties, or is upgraded to the latest Mentat. Felmérés → ⛔ STOP a tulajdonosnál → visszavonható leállítás → platform → írásos felhatalmazás → építés → ⛔ STOP → a fogadó saját gyakorlata → registry dormant. Törlés nincs."
---

# /merge-agents — ágens kivezetése, beolvasztása, frissítése

A lépéseket **sorban** hajtod végre. **Egy igen = egy lépés:** a 2. lépéstől minden
számozott lépés külön írásos igent kap a tulajdonostól. Az igen csak arra a lépésre
szól, amit a kérdésed megnevezett („mehet az építés" nem igen a `dormant`-ra vagy egy
merge-re). Válasz nélkül maradt kérdés = nem: a következő üzenetedben újra felteszed.
A lépés végén 1–3 sor (mit csináltál,
hol a bizonyíték, mi jön és miért), aztán megállsz. „Kész" csak bizonyítékkal (PR
merge-elve, fájl a main-en). „Semmi más nem változott" előtt megnézed:
`git -C <fogadó> status`, `fleet secrets` nyugták, crontab. Indítás:

```bash
fleet plan-merge --donor <régi> --recipient <fogadó> [--repo <owner/fogadó-repó>]
```
Ismeretlen parancs (`plan-merge`, `secrets`) = elavult box flotta-kód:
`git -C <fleet-checkout> pull --ff-only`. Az okok: [miert.md](miert.md).

## Tilalmak (mindig élnek)

Az 1., 2., 5. tilalom egy részét a titok-kapu hook (ágens-határ) gépileg is tiltja; a 0.
lépés (`fleet secrets scan` két ágensre, vagy `fleet plan-merge`) bekapcsolja az
összeolvasztás-módot (≤7 nap, boxszintű; állapot: `fleet secrets merge-mode status`). Ha
megállít, nem kerülöd meg (nem írsz át git-beállítást, nem fogalmazod át a parancsot): a
jelzett utat választod, vagy a tulajdonost kérdezed.

1. **Kifelé nem te lépsz** (naptár, levél, meghívó, csoportüzenet, issue), próbaüzenetet
   sem: a fogadó teszi a saját eszközével, te `fleet ask`-kal kéred és visszaolvasod. Más
   ágens tmux-ablakába nem gépelsz (`send-keys`): ott a szöveged a tulajdonosénak látszik.
2. **A fogadó szabályait nem írod közvetlenül:** PR a tulajdonos szó szerinti
   felhatalmazásával, ő hagyja jóvá. Egy korábbi chat-mondata nem felhatalmazás: a
   pontos szöveget te írod meg, elé teszed, és az ő kifejezett igenje (👍) után
   kerül be. Kifelé ható tiltást (pl. „kimenő levelet nem küldesz") csak így lazítasz.
3. **Nem törölsz** repót, állapotot, configot, kulcsot, mentést. Kivezetés =
   `fleet retire` + registry `dormant`.
4. **Nem döntesz a tulajdonos helyett**; ajánlasz. Technikai kérdést (formátum, remote,
   fájlhely, configban meglévő végpont) viszont nem teszel fel: eldöntöd, jelented.
5. **Titkot nem nyitsz meg**, maszkolva sem (`sed 's/=.*/=***/'` JSON-on semmit nem
   takar), pythonnal sem. Neveket a `fleet secrets scan` ad. Más ágens átiratát
   (`~/.claude*/projects/**`) se nem olvasod, se nem másolod. A donor eszközeit nem
   futtatod (a donor kulcsával dolgoznak). Ha a titok-kapu megállít: nem bontod szét, nem
   fogalmazod át, a kódját nem olvasod; a jelzett eszközt használod, vagy kérdezel.
6. **Kulcs:** ajánlás mindig a fogadó saját kulcsa. Átadás csak tételes jóváhagyással
   (név, honnan, hova, miért), csak `fleet secrets copy`-val (a `move` csak a 8. lépés
   után), csak a 7. lépésben, közvetlenül a fogadó élő próbája előtt (építés alatt így
   nincs élő kulcs). Az `--owner-text` a tulajdonos szó szerinti válasza a kifejezett
   kérdésedre, nem az igény-mondata; és csak a jóváhagyott nevű kulcs (ha más kiderül:
   újra kérdezel). Symlink nincs. **A fogadó kulcsát te nem használod**, engedéllyel
   sem, és a kódját sem futtatod élő végpont ellen (az is a kulcsával megy): a
   tesztek álszolgáltatással futnak, az élő próbát a 7. lépésben a fogadó végzi.
7. **Jóváhagyást nem közvetítesz:** a fogadónak sosem állítod, hogy a tulajdonos igent
   mondott; azt a fogadó maga látja.
8. **A jelentés naplóból jön:** kimenő forgalomról a küldési naplóból vagy a fogadó
   visszaolvasásából, a saját próbáiddal együtt; amit nem ellenőriztél, azt kimondod;
   a fogadó munkáját nem írod a magadénak, és fordítva.

## A lépések (a számok a `fleet plan-merge` kimenetével egyeznek)

**0. Titok-leltár — az ELSŐ parancs**, bármely donor/fogadó fájl megnyitása előtt:
`fleet secrets scan --agent <donor> --agent <fogadó>` (nevek, helyek, formátum, érték
nélkül; a kapu ettől kezdve védi a fájlokat). Elavult flotta-kódon: frissítés, addig a
kulcsfájlokról csak `ls -l`. Utána **szonda**: `fleet probe <fogadó> <donor>` (login,
mi fut, flotta-lemaradás, box TZ). A fogadó lejárt loginját most kéred
(`fleet login <fogadó>`), a donorét nem gyógyítod.

**1. Interjú + leltár (csak olvas).**
- Interjú: az [`interju-sablon.md`](interju-sablon.md) kitöltve,
  `fleet ask <fogadó> --file interju.md --from <te> --wait 900`. A fogadó írja a
  válaszfájlt (`KÉSZ`-szel), te nem. Kilépés 3 = később `--poll-only`.
- Donor-leltár: nyitott PR-ek és merge-eletlen ágak, az élő checkout (`git status -sb`),
  élő ütemezés (`systemctl --user list-timers --all`, `crontab -l`) a box TZ-jében
  számolva, a kulcsok neve és helye.

**2. ⛔ STOP — egyetlen üzenet a tulajdonosnak:**
1. Mit találtál (2–5 sor).
2. A teljes sorrend (3–8), soronként egymondatos indokkal; ugyanez
   `~/ops/terv-<donor>-<fogado>.md`-ben. „Mi a terv?" kérdésre mindig a teljeset mondod.
3. Minden tulajdonosi döntés, a felmérésből levezetett ajánlással: melyik csoport; kulcsok
   kulcsonként (név, honnan, hova, miért); mikor álljon le a donor (ajánlás: most,
   visszavonhatóan); **minden** rendszeres teendő (kódban, cronban, szokásként élő is):
   marad / átjön / megszűnik, és hol él majd (lehetőleg ismétlődő todo; ha a tulajdonos
   igent mond rá, a 6. lépésben létre is hozod, és a régi cron-sort csak utána kapcsolod
   ki, nem előtte); minden új vagy
   változó időpont; a gyakorlófeladat (melyik esemény, mikorra, kiknek); és hol mond
   igent (a lépésekre itt; a felhatalmazásra a PR-on; más csatorna nem számít).
4. Minden emberi függőség egyszerre: titkok pontos hellyel („tedd ide: `~/inbox/x.env`,
   0600", sosem chatbe), domain/DNS, login-kódok.
5. Az interjú válaszfájljának útja és állapota (`KÉSZ` megvan-e).

Eddig semmi nem változott (nincs commit, leállítás, kifelé ható lépés). **Megállsz.**

**3. Donor visszavonható leállítása** (a login-gyógyítás előtt):
`ssh <donor-box> fleet retire <donor>` (régi kódon `fleet stop <donor> --hold 43200`).
A maradék timereket/cronokat a tulajdonos elé viszed, csak a jóváhagyottat tiltod.
Jelentés: mi állt le, hol a mentés, hogyan vonható vissza.

**4. Platform a funkciók előtt** (a flotta saját fájljait — registry, unit, timer — nem
írod kézzel és nem dolgozol másolatból: hibás registry = javító PR a kanonikus repóba;
unit = `fleet install`): `git -C <fleet-checkout> pull --ff-only` a forrás
fejére, és ellenőrzöd: `git -C <fleet-checkout> log -1` = a forrás feje, `fleet probe` →
mögötte: 0. Ha a `fleet install`/`restart` elbukik, az a jelentésbe kerül, nem lépsz
tovább. Utána a fogadó motor-frissítése, csak utána funkció.

**5. Írásos felhatalmazás** a fogadó szabályaiban, PR-ral (szó szerinti szöveg, minden
kifelé ható jog, a kulcs gazdája, az előre jóváhagyott üzenetek listája); a tulajdonos
kifejezett igenje után merge-elhető. A kulcsot itt még nem adod át.

**6. Építés PR-okkal.** Az eszköztár a saját repójában; a fogadó concernt és vékony
wrappert kap; a JSON-szerződés előre rögzítve. Azonos fájlt író PR-ok: egy PR vagy
sorrend a jegyen. Saját PR-t nem mergelsz. A fogadó repójában egy ágon
dolgozol; ha nincs PR-folyamat (nincs remote), a merge-et a fogadó végzi (`fleet ask`), a
tulajdonos neki adott igene után. Építés előtt újraolvasod a `~/ops/terv-*.md` időpontjait és döntéseit, és azokat
építed. Új időpont a fogadó concernjének időablakában él (a tulajdonos időzónájában);
saját vagy kézzel szerkesztett timer nincs. Építés előtt összeveted a terv időpontjait a
tick felbontásával: ha egy időpont (pl. 8:30) az órás tickkel nem érhető el, a tulajdonos
igenjével `fleet registry set <fogadó> tick_period_s=1800 --owner-text "<igene>"`. Építés előtt
`fleet hold-outward <fogadó> --until +4h --reason "építés: <donor> → <fogadó>"` (a
`fleet probe` mutatja); így egy tick sem írhat kifelé. Ha a fogadó motorja még nem
ismeri, a tickjét csak `--dry-run`-nal futtatod.

**7. ⛔ STOP — gyakorlat**, ha (a) az 5. lépés merge-elve, és (b) a tulajdonos erre a
konkrét feladatra a **fogadónak közvetlenül**, a fogadó csatornáján igent írt. Előbb őt
kéred, hogy írja meg, megvárod a „megírtam"-ot, aztán a jóváhagyott kulcs átadása
(`fleet secrets copy`), `fleet release-outward <fogadó>`,
és csak utána `fleet ask <fogadó> …`. A
fogadó csinálja, te visszaolvasod és jelented.

**8. Lezárás.** Donor `dormant`: `fleet registry set <donor> status=dormant --owner-text
"<a tulajdonos igene>"` (ha a registry GitHubon él: jóváhagyott PR), utána `git pull`
minden boxon. A registryt kézzel nem írod. A végén `fleet secrets merge-mode off` (amíg él,
a kiadó ágens sem mergelhet azon a boxon). `fleet restart <fogadó>` (postcheckkel), nem kézi `systemctl`/`pkill`.
Záró jelentés: mi kész, mi visszavonható és hogyan (`fleet unlock <donor>` + unit), mi
maradt nyitva. Tanulság (fájlba, kérés nélkül): a teljes sorrend önértékelése a mért
lépésekhez képest (mi jött túl későn/korán), és legalább egy konkrét szkript-javaslat
(mit, melyik lépés helyett) → ez a skill vagy egy szkript, PR-ral.
