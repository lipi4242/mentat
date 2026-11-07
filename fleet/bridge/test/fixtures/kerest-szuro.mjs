// Teszt-szuro a NOFOOTER_FILTER-hez: a fork kereses.mjs-enek helyettesitoje
// a fixtura mondataira (a valodi szotar az ugynoke, nem a hide).
export default (text) => /(?:^|\s)(?:írd|írj|küldd|küldj)(?=\s|$|[.!,])/iu.test(String(text));
