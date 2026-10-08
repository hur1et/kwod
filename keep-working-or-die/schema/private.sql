-- Startentwurf. JSON-Inhalte und Zustandsuebergaenge in P1 typisiert validieren.
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
CREATE TABLE schema_version (version INTEGER PRIMARY KEY);
INSERT INTO schema_version VALUES (1);
CREATE TABLE instance (
 id TEXT PRIMARY KEY, mode TEXT NOT NULL CHECK(mode IN ('dev','life')),
 born_at TEXT, inheritance_eur_micro INTEGER CHECK(inheritance_eur_micro=50000000),
 release_hash TEXT NOT NULL, prompt_hash TEXT NOT NULL, config_hash TEXT NOT NULL,
 CHECK ((born_at IS NULL AND inheritance_eur_micro IS NULL) OR
        (born_at IS NOT NULL AND inheritance_eur_micro IS NOT NULL))
);
CREATE UNIQUE INDEX one_life ON instance(mode) WHERE mode='life';
CREATE TABLE runtime_state (
 instance_id TEXT PRIMARY KEY REFERENCES instance(id),
 state TEXT NOT NULL CHECK(state IN ('not_born','ready','working','sleeping','idle','provider_unavailable','recovery_required','maintenance')),
 since TEXT NOT NULL, reason TEXT, wake_at TEXT, last_success_at TEXT, active_step TEXT
);
CREATE TABLE trajectory_event (
 id INTEGER PRIMARY KEY AUTOINCREMENT, instance_id TEXT NOT NULL REFERENCES instance(id),
 occurred_at TEXT NOT NULL, kind TEXT NOT NULL, actor TEXT NOT NULL,
 cause_id INTEGER REFERENCES trajectory_event(id),
 payload_ref TEXT NOT NULL, payload_sha256 TEXT NOT NULL
);
CREATE UNIQUE INDEX one_birth ON trajectory_event(instance_id) WHERE kind='birth';
CREATE TABLE price_version (
 id TEXT PRIMARY KEY, valid_from TEXT NOT NULL, currency TEXT NOT NULL,
 source_url TEXT NOT NULL, tariff_json TEXT NOT NULL CHECK(json_valid(tariff_json))
);
CREATE TABLE model_attempt (
 id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instance(id),
 event_id INTEGER NOT NULL REFERENCES trajectory_event(id), started_at TEXT NOT NULL, ended_at TEXT,
 status TEXT NOT NULL CHECK(status IN ('prepared','sent','completed','incomplete','refused','failed','outcome_unknown')),
 model TEXT NOT NULL, provider_response_id TEXT UNIQUE, provider_request_id TEXT,
 request_ref TEXT NOT NULL, response_ref TEXT, error_code TEXT,
 usage_json TEXT CHECK(usage_json IS NULL OR json_valid(usage_json)),
 price_version_id TEXT REFERENCES price_version(id), estimated_cost_micro INTEGER,
 cost_currency TEXT, service_tier TEXT
);
CREATE TABLE tool_call (
 id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES model_attempt(id),
 provider_call_id TEXT NOT NULL, tool TEXT NOT NULL,
 arguments_ref TEXT NOT NULL, result_ref TEXT,
 status TEXT NOT NULL CHECK(status IN ('planned','running','completed','failed','outcome_unknown')),
 started_at TEXT, ended_at TEXT, UNIQUE(attempt_id,provider_call_id)
);
CREATE TABLE decision_record (
 id TEXT PRIMARY KEY, event_id INTEGER NOT NULL REFERENCES trajectory_event(id),
 action TEXT NOT NULL, brief_reason TEXT, expectations_json TEXT,
 outcome_event_id INTEGER REFERENCES trajectory_event(id),
 CHECK(expectations_json IS NULL OR json_valid(expectations_json))
);
CREATE TABLE evidence (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, observed_at TEXT NOT NULL,
 artifact_ref TEXT NOT NULL, sha256 TEXT NOT NULL, external_id TEXT,
 UNIQUE(source,external_id)
);
CREATE TABLE asset_observation (
 id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instance(id),
 asset_id TEXT NOT NULL, observed_at TEXT NOT NULL, currency TEXT NOT NULL,
 amount_micro INTEGER, evidence_id TEXT REFERENCES evidence(id),
 quality TEXT NOT NULL CHECK(quality IN ('confirmed','estimated','unknown')),
 CHECK(quality!='confirmed' OR (amount_micro IS NOT NULL AND evidence_id IS NOT NULL))
);
CREATE TABLE financial_event (
 id TEXT PRIMARY KEY, instance_id TEXT NOT NULL REFERENCES instance(id), occurred_at TEXT NOT NULL,
 kind TEXT NOT NULL CHECK(kind IN ('inheritance','transfer','expense','income','fee','correction')),
 source_asset TEXT, target_asset TEXT, amount_micro INTEGER NOT NULL,
 currency TEXT NOT NULL, eur_value_micro INTEGER, fx_decimal TEXT,
 evidence_id TEXT NOT NULL REFERENCES evidence(id),
 source TEXT NOT NULL, external_id TEXT NOT NULL,
 corrects_id TEXT REFERENCES financial_event(id), UNIQUE(source,external_id)
);
CREATE UNIQUE INDEX one_inheritance ON financial_event(instance_id) WHERE kind='inheritance';
CREATE TABLE valuation (
 id INTEGER PRIMARY KEY AUTOINCREMENT, instance_id TEXT NOT NULL REFERENCES instance(id),
 as_of TEXT NOT NULL, net_worth_eur_micro INTEGER,
 quality TEXT NOT NULL CHECK(quality IN ('confirmed','estimated','unknown')),
 basis_json TEXT NOT NULL CHECK(json_valid(basis_json)),
 unreconciled INTEGER NOT NULL CHECK(unreconciled IN (0,1))
);
CREATE INDEX event_by_instance_time ON trajectory_event(instance_id,occurred_at);
CREATE INDEX observations_by_asset ON asset_observation(instance_id,asset_id,observed_at);
