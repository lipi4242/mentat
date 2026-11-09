-- Flotta-egészség (11-07) owns 0500–0599. A boxok ide jelentik az ágenseik
-- képesség-eredményét; a worker incidenst nyit, a felelős ágensnek feladatot ad,
-- és cronból e-mailt küld a tulajdonosnak. Más plugin táblájára nincs FK: a
-- felelős principal (todo) és a box tokenje (core agent_token) azonosítóként él itt.
-- Időbélyeg: ISO-8601 UTC szöveg (…Z), mint a todo pluginban.

-- Egy flotta beállítása. A legtöbb példányban egy van ('default'); a worker hozza
-- létre az első használatkor, nem a migráció (egy friss példányba a restore üres táblát vár).
CREATE TABLE flotta_fleet (
  id TEXT PRIMARY KEY NOT NULL,
  name TEXT NOT NULL,
  owner_email TEXT,                  -- NULL → az ADMIN_EMAILS első címe
  deadman_min INTEGER NOT NULL DEFAULT 30 CHECK (deadman_min > 0),
  escalate_min INTEGER NOT NULL DEFAULT 60 CHECK (escalate_min > 0),
  debounce_reports INTEGER NOT NULL DEFAULT 2 CHECK (debounce_reports > 0),
  repeat_min INTEGER NOT NULL DEFAULT 360 CHECK (repeat_min > 0),
  -- korlátok (egy elszabadult flotta se árasszon el): felettük egy összegző incidens és egy összegző levél
  max_open_incidents INTEGER NOT NULL DEFAULT 50 CHECK (max_open_incidents > 0),
  max_open_per_box INTEGER NOT NULL DEFAULT 20 CHECK (max_open_per_box > 0),   -- egy box se fogyassza el a flotta keretét
  max_tasks_per_hour INTEGER NOT NULL DEFAULT 20 CHECK (max_tasks_per_hour > 0),
  max_mails_per_hour INTEGER NOT NULL DEFAULT 12 CHECK (max_mails_per_hour > 0),
  updated_at TEXT NOT NULL
);

-- A flotta felelősei (menedzserek), utódlási sorrendben. Egy incidenst a legkisebb rangú olyan
-- menedzser kap, akinek a hatóköre lefedi (`*`, egy box neve vagy egy ágens neve), és aki maga nem
-- alanya nyitott incidensnek (ami le van állva, nem javít — magát sem). Ha nincs ilyen: e-mail.
CREATE TABLE flotta_manager (
  id TEXT PRIMARY KEY NOT NULL,
  fleet_id TEXT NOT NULL REFERENCES flotta_fleet(id),
  principal_id TEXT NOT NULL,        -- todo_principal.id (agent)
  agent TEXT NOT NULL,               -- a menedzser flottabeli ágensneve (a saját incidensei így ismerhetők fel)
  scope TEXT NOT NULL DEFAULT '*',   -- '*' | box neve | ágens neve
  rank INTEGER NOT NULL CHECK (rank > 0),
  created_at TEXT NOT NULL,
  UNIQUE (fleet_id, principal_id, scope)
);
CREATE INDEX flotta_manager_rank ON flotta_manager (fleet_id, rank);

-- Egy gép. A tokenje csak `flotta:report` jogú, és csak ennek a boxnak a nevében jelenthet.
CREATE TABLE flotta_box (
  id TEXT PRIMARY KEY NOT NULL,
  fleet_id TEXT NOT NULL REFERENCES flotta_fleet(id),
  name TEXT NOT NULL UNIQUE,
  token_id TEXT UNIQUE,
  created_at TEXT NOT NULL,
  disabled_at TEXT,
  last_report_at TEXT,               -- az utolsó ELFOGADOTT, teljesen feldolgozott jelentés (a dead-man ezt nézi)
  last_attempt_at TEXT,              -- az utolsó jelentés-kísérlet (a ritmus-korlát ezt nézi), elutasítva is
  rejected_count INTEGER NOT NULL DEFAULT 0,   -- egymás utáni elutasított jelentések
  last_reject TEXT,                  -- az utolsó elutasítás oka, zárt kód (invalid|box-mismatch|cross-box|too-large)
  fleet_version TEXT,
  release_json TEXT
);

-- Az ágens legutóbbi képesség-eredménye (a jelentésből).
CREATE TABLE flotta_agent (
  id TEXT PRIMARY KEY NOT NULL,
  fleet_id TEXT NOT NULL REFERENCES flotta_fleet(id),
  name TEXT NOT NULL,
  box_id TEXT NOT NULL REFERENCES flotta_box(id),
  last_seen_at TEXT NOT NULL,
  measured_at TEXT,
  result_json TEXT NOT NULL,
  UNIQUE (fleet_id, name)
);

-- A nyers jelentések, rövid megőrzéssel (a cron 7 nap után törli).
CREATE TABLE flotta_report (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  box_id TEXT NOT NULL REFERENCES flotta_box(id),
  received_at TEXT NOT NULL,
  body_json TEXT NOT NULL
);
CREATE INDEX flotta_report_box ON flotta_report (box_id, received_at);

-- Incidens: egy nyitott egy (alany, ellenőrzés) párra. Alany: 'agent:<név>' vagy 'box:<név>'.
CREATE TABLE flotta_incident (
  id TEXT PRIMARY KEY NOT NULL,
  fleet_id TEXT NOT NULL REFERENCES flotta_fleet(id),
  box_id TEXT NOT NULL REFERENCES flotta_box(id),
  subject TEXT NOT NULL,
  agent TEXT,                        -- NULL a box-incidensnél (dead-man)
  check_key TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
  detail TEXT,
  opened_at TEXT NOT NULL,
  last_red_at TEXT NOT NULL,
  red_count INTEGER NOT NULL DEFAULT 1,
  resolved_at TEXT,
  resolve_note TEXT,
  todo_task_id TEXT,                 -- a kiosztott menedzser feladata (todo_task.id)
  assigned_principal_id TEXT,        -- kié lett (flotta_manager.principal_id); NULL = senkié → e-mail-út
  claimed_by TEXT,                   -- tartalék a későbbi átvételhez (claim/lease); ma nem írja semmi
  claimed_at TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  first_mail_at TEXT,
  last_mail_at TEXT,
  mail_count INTEGER NOT NULL DEFAULT 0,
  resolved_mail_at TEXT
);
CREATE UNIQUE INDEX flotta_incident_open ON flotta_incident (fleet_id, subject, check_key) WHERE status = 'open';
CREATE INDEX flotta_incident_status ON flotta_incident (status, opened_at);

-- Az incidens története (megnyitás, feladat, e-mail, megoldás).
CREATE TABLE flotta_incident_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  incident_id TEXT NOT NULL REFERENCES flotta_incident(id),
  at TEXT NOT NULL,
  kind TEXT NOT NULL,
  body TEXT
);
CREATE INDEX flotta_incident_event_incident ON flotta_incident_event (incident_id, id);
