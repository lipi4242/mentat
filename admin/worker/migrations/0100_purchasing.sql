-- Purchasing plugin (band 0100–0199).

CREATE TABLE IF NOT EXISTS purchase_need (
  id                 TEXT PRIMARY KEY NOT NULL,
  case_id            TEXT NOT NULL,
  for_person         TEXT,
  needed_by          TEXT,
  definition_quality TEXT NOT NULL DEFAULT 'vazlat',  -- vazlat | korvonalazott | pontos
  notes              TEXT,
  archived           INTEGER NOT NULL DEFAULT 0,
  created_at         TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (case_id) REFERENCES "case"(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_need_case ON purchase_need (case_id);

CREATE TABLE IF NOT EXISTS need_item (
  id          TEXT PRIMARY KEY NOT NULL,
  need_id     TEXT NOT NULL,
  description TEXT NOT NULL,
  qty_needed  REAL,        -- NULL = unquantified; boolean coverage applies
  unit        TEXT,
  notes       TEXT,
  -- Negative quantities are a data error here, not a real state: returns are
  -- expressed by an intent's status, never by a negative quantity. The
  -- typeof() clause matters because SQLite's REAL affinity is not a
  -- guarantee: an unconvertible string (e.g. 'not-a-number') stores as TEXT
  -- and would otherwise sort above 0 and pass a bare ">= 0" check.
  CHECK (qty_needed IS NULL OR (typeof(qty_needed) IN ('real', 'integer') AND qty_needed >= 0)),
  FOREIGN KEY (need_id) REFERENCES purchase_need(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_need_item_need ON need_item (need_id);

CREATE TABLE IF NOT EXISTS supplier (
  id      TEXT PRIMARY KEY NOT NULL,
  name    TEXT NOT NULL,
  url     TEXT,
  country TEXT,
  notes   TEXT
);

CREATE TABLE IF NOT EXISTS product (
  id    TEXT PRIMARY KEY NOT NULL,
  name  TEXT NOT NULL,
  brand TEXT,
  form  TEXT,
  spec  TEXT,
  notes TEXT
);

-- One row per (supplier, product): checked_at already records price age, and
-- a price-history table is deliberately out of scope until something
-- actually wants a trend. Re-checking a price UPDATEs this row in place; it
-- is a current observation, not a log.
CREATE TABLE IF NOT EXISTS offer (
  id          TEXT PRIMARY KEY NOT NULL,
  supplier_id TEXT NOT NULL,
  product_id  TEXT NOT NULL,
  url         TEXT,
  price       REAL,
  currency    TEXT NOT NULL DEFAULT 'HUF',
  pack_size   TEXT,
  in_stock    INTEGER,
  checked_at  TEXT,
  source      TEXT NOT NULL DEFAULT 'user',   -- user | agent
  FOREIGN KEY (supplier_id) REFERENCES supplier(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id)  REFERENCES product(id)  ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_offer_product ON offer (product_id);
-- No standalone index on supplier_id: it is the leftmost column of the
-- unique index below, so it already serves supplier-only lookups.
CREATE UNIQUE INDEX IF NOT EXISTS idx_offer_supplier_product ON offer (supplier_id, product_id);

CREATE TABLE IF NOT EXISTS purchase_intent (
  id            TEXT PRIMARY KEY NOT NULL,
  title         TEXT NOT NULL,
  supplier_id   TEXT,
  status        TEXT NOT NULL DEFAULT 'tervezett',
  ordered_at    TEXT,
  expected_at   TEXT,
  shipping_cost REAL,
  total         REAL,
  currency      TEXT NOT NULL DEFAULT 'HUF',
  notes         TEXT,
  CHECK (status IN ('tervezett', 'megrendelve', 'uton', 'megerkezett', 'elvetve')),
  FOREIGN KEY (supplier_id) REFERENCES supplier(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_purchase_intent_supplier ON purchase_intent (supplier_id);

CREATE TABLE IF NOT EXISTS intent_item (
  id         TEXT PRIMARY KEY NOT NULL,
  intent_id  TEXT NOT NULL,
  offer_id   TEXT,
  product_id TEXT,
  qty        REAL NOT NULL DEFAULT 1,
  unit       TEXT,
  unit_price REAL,
  notes      TEXT,
  CHECK (qty >= 0),
  FOREIGN KEY (intent_id) REFERENCES purchase_intent(id) ON DELETE CASCADE,
  FOREIGN KEY (offer_id)  REFERENCES offer(id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_intent_item_intent ON intent_item (intent_id);
CREATE INDEX IF NOT EXISTS idx_intent_item_offer ON intent_item (offer_id);

-- The allocation carries the quantity: this is what makes partial coverage
-- expressible, and what preserves why something was bought.
-- RESTRICT on need_item, not CASCADE: an allocation is the record of *why*
-- something was bought. Cascading would let deleting a need item silently
-- destroy that rationale — exactly what "archive, never hard-delete" exists to
-- prevent. A delete attempt must fail loudly instead. (Same reasoning as the
-- core `case_event` trail, which restricts for the same reason.)
CREATE TABLE IF NOT EXISTS allocation (
  id             TEXT PRIMARY KEY NOT NULL,
  intent_item_id TEXT NOT NULL,
  need_item_id   TEXT NOT NULL,
  qty_allocated  REAL,
  unit           TEXT,
  CHECK (qty_allocated IS NULL OR qty_allocated >= 0),
  FOREIGN KEY (intent_item_id) REFERENCES intent_item(id) ON DELETE CASCADE,
  FOREIGN KEY (need_item_id)   REFERENCES need_item(id)   ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_allocation_pair ON allocation (intent_item_id, need_item_id);
-- idx_allocation_pair is (intent_item_id, need_item_id): by the leftmost-
-- prefix rule it cannot serve a lookup on need_item_id alone, which is the
-- direction coverage reads (and the direction the RESTRICT check on
-- need_item delete scans). A dedicated index backs both.
CREATE INDEX IF NOT EXISTS idx_allocation_need_item ON allocation (need_item_id);
