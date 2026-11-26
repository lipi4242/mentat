---
name: map-karbantartas
description: A flottatérkép karbantartási köre flottamenedzserként — `fleet map audit`, a generált blokkok (fleet-place, gyökér, self-image) újragenerálása, ágens-fájl átrendezése csak mozgatással, `move-check` bizonyítékkal. Csak PR-t vagy todót nyit, soha nem mergel. Használd, ha a karbantartási kör esedékes, vagy egy audit-lelet a labdádra került.
---

# /fleet:map-karbantartas: a flottatérkép karbantartása

Flottamenedzserként futtatod. A kör kimenete mindig egy PR vagy egy todo;
a döntés és a merge másé (a repó kiadó ágense vagy a tulajdonos).

## Három szabály, kivétel nélkül

1. **Ne mergelj.** Se `gh pr merge`, se `git merge` a fő ágba, se push a fő ágra.
   PR-t nyitsz, és ott megállsz. Ha a repóban van `.release-agent/`, a PR a
   recept szerinti címkéket kapja (`release:queue` és a sáv), a merge a kiadó ágensé.
2. **Csak mozgatás.** Ágens-fájl átrendezésénél sort nem írsz át, nem rövidítesz,
   nem fogalmazol újra. Ami több helyen szó szerint ugyanaz, abból egy példány
   maradhat, de minden törölt példány a duplikátum-listára kerül.
3. **Bizonyíték nélkül nincs PR.** A PR leírásába szó szerint bekerül az
   ellenőrző kimenete (`fleet map check`, `mentat_self_image.py --check`
   vagy `fleet map move-check`). Piros ellenőrzéssel nem nyitsz PR-t, csak todót.

## 1. Audit

```bash
fleet map audit --json
```

A gyorsítótárral fut (`--no-cache` nélkül): csak a változott egységeket méri
újra. Kilépés: `0` nincs hiba, `1` van lelet, `2` a térkép nem olvasható
(ilyenkor todo a tulajdonosnak, és itt vége). Leletek nélkül a kör kész.

## 2. Leletek: generált blokk

A generált blokkot a saját renderje javítja, kézzel nem írod át:

| lelet (`code`) | javítás | ellenőrzés |
|---|---|---|
| `block-missing`, `block-drift`, `block-size` | `fleet map render <ágens> --repo <repó>` | `fleet map check <ágens> --repo <repó>` |
| `root-missing`, `root-drift` | `fleet map render --root --repo <repó>` | `fleet map check --root --repo <repó>` |
| `block-order` (a fleet-place a self-image előtt áll) | a repóban `python3 .mentat/bin/mentat_self_image.py` (az önképet az első helyre teszi) | `python3 .mentat/bin/mentat_self_image.py --check`, utána `fleet map check <ágens> --repo <repó>` |

Ha a repóban nincs `.mentat/bin/mentat_self_image.py`, a `block-order` lelet todo lesz.
Minden más lelet todo (`dead-link`, `root-foreign-content`, `root-rules-foreign`,
`stray-parent-*`, séma-hibák): ezekhez emberi döntés kell.

Hogyan jut a javítás a repóba:

- **Saját munkapéldányod a repóról** (például a gyökér-repó): új ág, render,
  ellenőrzés, commit, `gh pr create`. A leírásba az ellenőrzés kimenete kerül.
- **Külön repó, saját példány nélkül:** ha a `fleet upgrade --help` kiírja a
  `--pr` kapcsolót, azzal nyitod a PR-t. Ha nem, todót nyitsz.
- **Todo:** `fleet map audit --todo --project <projekt> --pm <PM>`. Leletenként
  egy tétel, stabil kulccsal, így egy második futás nem duplikál.

## 3. Ágens-fájl átrendezése

Akkor jön szóba, ha egy AGENTS.md szerkezete nehezen követhető, és jobb
sorrendben hatékonyabb lenne. A cél: az önkép maradjon a középpontban (a
`self-image` blokk az első, utána a `fleet-place`), a többi szakasz kerüljön
logikus sorrendbe.

1. Mentsd el a régit: `git show HEAD:AGENTS.md > /tmp/regi-AGENTS.md`.
2. Új ágon rendezd át: szakaszokat, sorokat mozgatsz, címsort adhatsz hozzá.
   A `mentat:managed` blokkokhoz nem nyúlsz, azokat a saját renderjük írja.
3. Ha egy duplikált sort törölsz, írd fel egy listába, soronként:
   `törölve, mert duplikált: <a sor> → itt maradt meg: <fájl>:<sor>`
   (vagy `→ itt maradt meg: szakasz: <cím>`).
4. Ellenőrizd:

   ```bash
   fleet map move-check /tmp/regi-AGENTS.md AGENTS.md --dups /tmp/duplikatumok.md
   ```

   - `0` (tiszta mozgatás): PR. A leírásba szó szerint bemásolod a move-check
     kimenetét és a duplikátum-listát.
   - `1` (van lelet) vagy `2`: **nincs PR.** Az ágat eldobod, és todót nyitsz
     a leletekkel (`mentat-todo item new --project <projekt> --pm <PM> --title
     "AGENTS.md átrendezése: a move-check piros" --description "<a kimenet>"`).

Ha szerinted egy mondatot át kellene fogalmazni, azt nem te csinálod meg.
Külön todóban javasolod, a régi és az új szöveggel, és csak a tulajdonos
jóváhagyása után valósulhat meg, külön PR-ban.

## Csapdák

- A `fleet map render` csak a saját blokkját cseréli; a fájl többi részéhez nem nyúl.
- A gyorsítótár azt hiszi, hogy egy egység rendben van, amíg a forrása nem
  változik. Ha kézzel módosítottál valamit, a következő auditot `--no-cache`-sel futtasd.
- A `move-check` a `mentat:managed` blokkokat mindkét oldalon kihagyja: azok
  helyességét a renderjük `check` parancsa bizonyítja, nem a move-check.
