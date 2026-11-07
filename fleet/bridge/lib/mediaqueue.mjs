// lib/mediaqueue.mjs — durable, egyszalu media-feldolgozo sor.
// Az enqueue SZINKRON, STRIKTEN perzisztal (ezert lephet utana az offset):
// ha az iras elhasal, DOB — a hivo poll-ciklus igy nem lepteti az offsetet
// egy sosem letezett sorelem folott. A drain() egyszerre EGY elemet dolgoz
// fel (3.8G box — nincs parhuzamos letoltes). Hibanal az elem a sorban MARAD;
// a kovetkezo drain ujraprobalja.
import { loadJsonQuarantine, saveJsonStrict } from "./jsonfile.mjs";

export class MediaQueue {
  constructor(path, processItem, { onCorrupt = () => {} } = {}) {
    this.path = path;
    this.processItem = processItem;
    this.onCorrupt = onCorrupt;
    this.running = false;
  }
  _items() {
    const items = loadJsonQuarantine(this.path, [], this.onCorrupt);
    return Array.isArray(items) ? items : [];
  }
  depth() { return this._items().length; }
  enqueue(item) {
    const items = this._items();
    items.push(item);
    saveJsonStrict(this.path, items); // dob, ha nem sikerult — lasd fent
  }
  async drain() {
    if (this.running) return;
    this.running = true;
    try {
      let items = this._items();
      while (items.length) {
        try {
          await this.processItem(items[0]);
        } catch {
          break; // marad a sorban; kesobbi drain ujraprobalja
        }
        items = this._items();
        items.shift();
        try {
          saveJsonStrict(this.path, items);
        } catch {
          // A torles nem ment lemezre: az elem ujra elo fog jonni.
          // Duplikacio > vesztes — megallunk, hogy ne porgessunk ravaszul.
          break;
        }
      }
    } finally {
      this.running = false;
    }
  }
}
