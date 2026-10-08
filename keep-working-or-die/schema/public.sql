-- Separate Datei, keine privaten Tabellen in der oeffentlichen Verbindung.
PRAGMA journal_mode = WAL;
CREATE TABLE public_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 private_event_id INTEGER NOT NULL UNIQUE,
 occurred_at TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('birth','status','activity','asset_update','decision','tool_completed','provider_unavailable','intervention')),
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE public_snapshot (
 singleton INTEGER PRIMARY KEY CHECK(singleton=1),
 as_of TEXT NOT NULL,
 payload_json TEXT NOT NULL CHECK(json_valid(payload_json))
);
CREATE TABLE public_valuation (
 id INTEGER PRIMARY KEY,
 as_of TEXT NOT NULL, net_worth_eur_micro INTEGER,
 quality TEXT NOT NULL CHECK(quality IN ('confirmed','estimated','unknown')),
 unreconciled INTEGER NOT NULL CHECK(unreconciled IN (0,1))
);
-- Nur die validierende Projektion darf schreiben; JSON-gueltig allein ist keine Whitelist.
