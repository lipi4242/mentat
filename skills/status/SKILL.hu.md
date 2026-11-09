---
name: status
description: Megmondja, mely Mentat-építőelemek tartoznak az ágenshez (agy, motor, flotta, admin), és mely szinergiáik élnek — a mentat.json és a .mentat/local.json alapján.
---

# Skill — `status`

**Hívd meg**, ha a FELHASZNÁLÓ megkérdezi, mi van telepítve vagy bekötve, egy
építőelem telepítése vagy eltávolítása után, vagy ha valami, aminek együtt
kellene működnie (pl. ügyek az adminban), nem működik.

Csak olvas: ez a skill egyik fájlt sem írja.

## 1. lépés — Futtasd a hivatkozó eszközt

Ha a `.mentat/bin/mentat_cli.py` hiányzik, töltsd le (nincs commitolva):

```bash
mkdir -p .mentat/bin
for f in mentat_manifest.py mentat_rules.py mentat_roles.py mentat_cli.py; do curl -fsSL https://raw.githubusercontent.com/lipi4242/mentat/v0.6.1/reference/manifest/$f -o .mentat/bin/$f; done
```

Aztán a repó gyökeréből:

```bash
python3 .mentat/bin/mentat_cli.py status
```

Kilépési kód: 0 = rendben, 1 = hibák, 2 = **csak diagnosztika** (újabb séma
vagy olvashatatlan fájl — amíg nincs javítva, vagy az eszköz frissítve, semmi
nem cselekedhet a manifest alapján).

## 2. lépés — python3 nélkül

Olvasd el magad a `mentat.json`-t és a `.mentat/local.json`-t, és
alkalmazd a `reference/mentat-json.hu.md`-t: egy elem **jelen van**, ha
szerepel a `components` alatt, ezen a gépen telepítve van
(`installed.<elem>`; az adminnál `admin.url`), és a bejegyzése érvényes
(relatív, repón belüli útvonalak, nincs végpont a `mentat.json`-ban, nincs
IP-cím). Egy szinergia akkor él, ha mindkét eleme jelen van; az agy + admin
ehhez még `cases.backend: admin`-t is kér.

## 3. lépés — Mondd el a FELHASZNÁLÓnak

Top-down, köznyelven, JSON nélkül:

1. **Mi tartozik az ágenshez** — építőelemenként egy sor: jelen van /
   bejegyezve, de ezen a gépen nincs telepítve / nincs telepítve / az admin
   nincs bekötve. Ennél az eszköz kiírja, hogy az admin a Mentat teendő- és
   backlog-kezelője (teendők, ügyek, backlog-tételek) — ezt add tovább, ne
   indíts kézzel admint.
2. **Mi működik együtt** — csak az élő szinergiák, soronként, a FELHASZNÁLÓ
   nyelvén („a motor minden reggel átnézi az ügyeidet").
3. **Mi a hiba**, ha van — mindegyikhez az az egy lépés, ami megjavítja. A
   `cases_backend_unavailable` azt jelenti, hogy az ügyekkel való munka áll,
   amíg az admin újra elérhető: mondd ki, és ne válts markdownra.

Hiányzó elem telepítését csak akkor javasold, ha a FELHASZNÁLÓ megkérdezi,
mivel bővíthetné.
