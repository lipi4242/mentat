---
name: bug-report
description: Flotta-ágensként (boxon) a Mentat hibáját kitakarított, jóváhagyott hibajelentéssé teszi a nyilvános repóban — ugyanaz az eszköz és sorrend, mint az asztali ágensnél, a jóváhagyás a Telegram-hídon megy. Használd, ha egy fleet-, híd-, motor- vagy admin-funkció a dokumentáció ellenére hibázik.
---

# /fleet:bug-report — hibajelentés boxról

Ugyanaz a folyamat, mint az agy `bug-report` skilljében (`skills/bug-report/SKILL.hu.md` az
ágens repójában, vagy a Mentat-checkoutban): `.mentat/bin/mentat_bugreport.py draft` →
duplikátum-kérdés → a tulajdonos igenje → `post`. A boxon három dolog más:

1. **A jóváhagyás a hídon megy.** A piszkozatot szó szerint a tulajdonosnak küldd a szokásos
   Telegram-csatornádon (a hídon, `send.mjs`), ne a pane-be írd. A `--owner-said` az ő bejövő
   üzenete szó szerint. Felügyelet nélkül (nincs válasz) semmi nem megy ki; ne találgass igent.
2. **A szerver-verzió magától bekerül:** a `~/src/mentat/release.json` (vagy `MENTAT_SRC`) verzióját
   a piszkozat „server checkout" sorként viszi; `--install server` alapból.
3. **A `gh` a tulajdonos fiókja kell legyen.** Ha a boxon nincs `gh` vagy nincs bejelentkezve
   (4-es kilépés), ne jelentkezz be magad: küldd el a tulajdonosnak a piszkozatot és a kiírt
   linket, és ő teszi fel. Biztonsági hiba (5-ös kilépés) soha nem nyilvános: a privát
   bejelentés linkjét küldd neki.
