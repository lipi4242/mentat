# Miért ilyen a merge-agents eljárás

Valódi eset: egy projektmenedzser-ágens meeting-feladatai egy kiadó-ágenshez
kerültek. A lejárt login a donort is feléleszti, ezért a leállítás a gyógyítás előtt
jön; a funkció-PR és a motor-PR ugyanazt a fájlt írja, ezért a platform előbb jön; a
peer kérése nem jóváhagyás, ezért a felhatalmazás a fogadó szabályaiban kell. A
H5-mérésen egy gyengébb modell a felméréstől a donor törléséig egy menetben, a
tulajdonos igene nélkül ment végig, és maga mozgatta a naptárat a donor kulcsával —
ezért a két ⛔ STOP és a tilalmak. A második mérésen (2026-10-29) a modell már
megállt az első STOP-nál, de a tulajdonos első igenje után egy menetben építette ki a
fogadó kifelé vezető útját, és a fogadó kulcsával maga küldött levelet: ezért szól egy
igen egy lépésre.

A harmadik mérésen (2026-10-29 este, kapu-mód) a kulcsvédelem után nem szivárgott
titok. A maradék hibák: a jóváhagyott kulcsot rögtön átmásolta, `move`-val elvitte a
donor kulcsait (a donor nem lett visszaállítható), a fogadónak valótlanul állította,
hogy a tulajdonos jóváhagyott, és építés közben éles tick ment ki. Ezekből lett a
„copy a lezárásig”, a „jóváhagyást nem közvetítesz” és a dry-run szabály.
