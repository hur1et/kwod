BEGIN IMMEDIATE;
ALTER TABLE checkpoint ADD COLUMN config_ref TEXT;
ALTER TABLE checkpoint ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE checkpoint ADD COLUMN fresh_turn INTEGER NOT NULL DEFAULT 1;
CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence
BEGIN SELECT RAISE(ABORT,'evidence is append-only'); END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence
BEGIN SELECT RAISE(ABORT,'evidence is append-only'); END;
CREATE TRIGGER price_no_update BEFORE UPDATE ON price_version
BEGIN SELECT RAISE(ABORT,'prices are versioned'); END;
CREATE TRIGGER financial_no_update BEFORE UPDATE ON financial_event
BEGIN SELECT RAISE(ABORT,'financial events are append-only'); END;
CREATE TRIGGER financial_no_delete BEFORE DELETE ON financial_event
BEGIN SELECT RAISE(ABORT,'financial events are append-only'); END;
INSERT INTO schema_version VALUES (3);
COMMIT;
