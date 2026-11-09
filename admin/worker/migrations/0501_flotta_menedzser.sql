-- Flotta-menedzser szerep (flotta-menedzser, 11-08). Előre-csak migráció a 0500 fölé.
-- Az incidens állapotgépe (state + verzió-CAS), az átvétel fencing-tokene, a javító
-- műveletek auditja, az újraindítási keret és a menedzser-lista verziója.
-- Terv: fleet/docs/design/2026-11-08-flotta-menedzser.md

-- Állapotgép. A régi `status` (open/resolved) marad: open = minden nem megoldott állapot.
ALTER TABLE flotta_incident ADD COLUMN state TEXT NOT NULL DEFAULT 'nyitott'
  CHECK (state IN ('nyitott', 'kiosztva', 'atveve', 'javit', 'ellenorzes', 'megoldva', 'atadva', 'ember-kell'));
ALTER TABLE flotta_incident ADD COLUMN version INTEGER NOT NULL DEFAULT 0;      -- CAS: minden átmenet +1
ALTER TABLE flotta_incident ADD COLUMN move_id TEXT;                            -- az utolsó átmenet egyedi jele: a batch további
                                                                                -- sorai CSAK a saját átmenetükre írnak (a vesztes nem)
ALTER TABLE flotta_incident ADD COLUMN state_at TEXT;                           -- mikor lépett ebbe az állapotba
ALTER TABLE flotta_incident ADD COLUMN fence INTEGER NOT NULL DEFAULT 0;        -- monoton fencing-token (generáció)
ALTER TABLE flotta_incident ADD COLUMN claim_hash TEXT;                         -- az átvétel titkának hash-e (a nyílt érték csak a válaszban)
ALTER TABLE flotta_incident ADD COLUMN assigned_at TEXT;
ALTER TABLE flotta_incident ADD COLUMN attempt_until TEXT;                      -- a fix 30 perces kísérleti keret vége
ALTER TABLE flotta_incident ADD COLUMN handovers INTEGER NOT NULL DEFAULT 0;
ALTER TABLE flotta_incident ADD COLUMN tried_json TEXT NOT NULL DEFAULT '[]';   -- akik ebben az incidensben már sorra kerültek
ALTER TABLE flotta_incident ADD COLUMN drain TEXT;                              -- 'handover' | 'human' — futó művelet lezárására vár
ALTER TABLE flotta_incident ADD COLUMN nonce_hash TEXT;                         -- ellenőrző nonce (a fence-hez kötve)
ALTER TABLE flotta_incident ADD COLUMN nonce_fence INTEGER;
ALTER TABLE flotta_incident ADD COLUMN verified_boot_id TEXT;
ALTER TABLE flotta_incident ADD COLUMN human_reason TEXT;                       -- miért ember-kell
ALTER TABLE flotta_incident ADD COLUMN human_by TEXT;                           -- emberi átvétel (e-mail)
UPDATE flotta_incident SET state = 'megoldva' WHERE status = 'resolved';
CREATE INDEX flotta_incident_state ON flotta_incident (fleet_id, state);

-- Egy javító lépés a célboxon (`fleet repair-exec`). A szándék a végrehajtás ELŐTT rögzül:
-- egy összeomlott lépés `intent`-ben marad, és a következő lépés előtt `uncertain` lesz.
CREATE TABLE flotta_repair_op (
  id TEXT PRIMARY KEY NOT NULL,                 -- a végrehajtó műveleti azonosítója
  incident_id TEXT NOT NULL REFERENCES flotta_incident(id),
  fence INTEGER NOT NULL,
  principal_id TEXT NOT NULL,
  step TEXT NOT NULL CHECK (step IN ('doctor', 'doctor-fix', 'bridge-install', 'unquarantine', 'postcheck')),
  target TEXT NOT NULL,                         -- 'agent:<név>' | 'box:<név>'
  state TEXT NOT NULL CHECK (state IN ('intent', 'ok', 'failed', 'uncertain', 'assessed', 'busy', 'refused')),
  created_at TEXT NOT NULL,
  deadline TEXT NOT NULL,                       -- eddig számít futónak (a lépés időkorlátja)
  finished_at TEXT,
  summary TEXT
);
CREATE INDEX flotta_repair_op_incident ON flotta_repair_op (incident_id, created_at);

-- Újraindítási keret: ágensenként óránként 3, műveleti azonosítóval foglalva (idempotens).
CREATE TABLE flotta_restart_budget (
  op_id TEXT PRIMARY KEY NOT NULL,
  fleet_id TEXT NOT NULL,
  agent TEXT NOT NULL,
  reserved_at TEXT NOT NULL
);
CREATE INDEX flotta_restart_budget_agent ON flotta_restart_budget (fleet_id, agent, reserved_at);

-- A menedzser-lista egyetlen kiadótól jön (`fleet managers publish`), verzióval.
ALTER TABLE flotta_fleet ADD COLUMN managers_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE flotta_fleet ADD COLUMN managers_digest TEXT;

-- A gép fajtája (paritás, 11-08): 'box' = always-on szerver (systemd, timer, dead-man);
-- 'desktop' = valakinek a saját gépe (Claude Desktop/Code, nincs always-on processz és híd):
-- csak a futó session jelent, ezért a csendje nem hiba (nincs dead-man), és a box teljes
-- kiesése nem fedetlenségi tartomány (a gép kikapcsolása a normál állapota).
ALTER TABLE flotta_box ADD COLUMN kind TEXT NOT NULL DEFAULT 'box' CHECK (kind IN ('box', 'desktop'));

-- A box javító-próbája (a végrehajtó önellenőrzése) a jelentésből. NULL = nem mért.
ALTER TABLE flotta_box ADD COLUMN repair_ok INTEGER;
ALTER TABLE flotta_box ADD COLUMN repair_detail TEXT;

-- Hatókör új alakja: '*' | 'agent:<név>' | 'box:<név>'. A 0500 csupasz neve átírva, a SAJÁT
-- flottáján belül: box-név → box:, minden más → agent:. Kétértelmű név (ugyanabban a flottában
-- box ÉS ágens is így hívják) nem íródik át csendben: a migráció megáll. Előtte futtasd a
-- preflightot (admin/docs/plugins/flotta/INSTALL.md, „0501 preflight”), és döntsd el kézzel.
CREATE TABLE flotta_0501_guard (ambiguous_scope TEXT CHECK (ambiguous_scope IS NULL));
INSERT INTO flotta_0501_guard
  SELECT m.fleet_id || '/' || m.scope FROM flotta_manager m
  WHERE m.scope <> '*' AND instr(m.scope, ':') = 0
    AND EXISTS (SELECT 1 FROM flotta_box b WHERE b.fleet_id = m.fleet_id AND b.name = m.scope)
    AND EXISTS (SELECT 1 FROM flotta_agent a WHERE a.fleet_id = m.fleet_id AND a.name = m.scope);
DROP TABLE flotta_0501_guard;
UPDATE flotta_manager SET scope = 'box:' || scope
  WHERE scope <> '*' AND instr(scope, ':') = 0
    AND EXISTS (SELECT 1 FROM flotta_box b WHERE b.fleet_id = flotta_manager.fleet_id AND b.name = flotta_manager.scope);
UPDATE flotta_manager SET scope = 'agent:' || scope WHERE scope <> '*' AND instr(scope, ':') = 0;
