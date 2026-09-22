PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
 id TEXT PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 salt TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('owner','operator','viewer')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
 csrf TEXT NOT NULL, expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS clients (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, website TEXT, notes TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS opportunities (
 id TEXT PRIMARY KEY, title TEXT NOT NULL, source TEXT NOT NULL, source_url TEXT,
 budget_minor INTEGER, currency TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'discovered' CHECK(status IN ('discovered','drafted','approved','converted')),
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS proposals (
 id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
 content TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS projects (
 id TEXT PRIMARY KEY, opportunity_id TEXT NOT NULL UNIQUE REFERENCES opportunities(id),
 client_id TEXT REFERENCES clients(id), title TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
 title TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('todo','done')),
 created_at TEXT NOT NULL, completed_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, actor_id TEXT NOT NULL REFERENCES users(id),
 worker TEXT NOT NULL, skill TEXT NOT NULL, tool TEXT NOT NULL, input_json TEXT NOT NULL,
 output_json TEXT, status TEXT NOT NULL, created_at TEXT NOT NULL, finished_at TEXT
);
CREATE TABLE IF NOT EXISTS evidence (
 id TEXT PRIMARY KEY, run_id TEXT REFERENCES runs(id), subject_type TEXT NOT NULL,
 subject_id TEXT NOT NULL, kind TEXT NOT NULL, data_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
 id TEXT PRIMARY KEY, subject_type TEXT NOT NULL, subject_id TEXT NOT NULL,
 policy TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected')),
 requested_by TEXT NOT NULL REFERENCES users(id), decided_by TEXT REFERENCES users(id),
 reason TEXT, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS one_approval_per_subject ON approvals(subject_type,subject_id);
CREATE TABLE IF NOT EXISTS events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT NOT NULL, actor_id TEXT,
 subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, payload_json TEXT NOT NULL,
 created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_by_subject ON events(subject_type,subject_id,id);
CREATE INDEX IF NOT EXISTS approvals_by_status ON approvals(status,created_at);
