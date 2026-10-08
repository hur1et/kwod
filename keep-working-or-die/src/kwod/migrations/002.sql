BEGIN IMMEDIATE;
CREATE TABLE checkpoint (
 instance_id TEXT PRIMARY KEY REFERENCES instance(id),
 context_ref TEXT NOT NULL,
 pending_attempt TEXT REFERENCES model_attempt(id),
 objective TEXT NOT NULL,
 activity TEXT NOT NULL DEFAULT 'idle'
);
CREATE TRIGGER trajectory_no_update BEFORE UPDATE ON trajectory_event
BEGIN SELECT RAISE(ABORT,'trajectory is append-only'); END;
CREATE TRIGGER trajectory_no_delete BEFORE DELETE ON trajectory_event
BEGIN SELECT RAISE(ABORT,'trajectory is append-only'); END;
INSERT INTO schema_version VALUES (2);
COMMIT;
