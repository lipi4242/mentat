// lib/notice.mjs — esemeny-sor a kezbesitesi naploba (type:"notice").
// SOSEM dob: a fo folyamot nem allithatja meg.
import { makeRow, appendDelivery } from "./delivery-log.mjs";

export function logNotice(dir, event, fields = {}) {
  if (!dir) return { ok: false, error: "no log dir" };
  try { return appendDelivery(dir, makeRow({ ...fields, type: "notice", event })); }
  catch (e) { return { ok: false, error: e.message }; }
}
