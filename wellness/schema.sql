-- Smart Wellness Wearable database (SQLite)
-- Tables follow the storage column of the Personal Data Map v1.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,  -- Account ID
    display_name           TEXT    NOT NULL,
    email                  TEXT    NOT NULL UNIQUE,
    password_hash          TEXT    NOT NULL,          -- SR1
    birth_year_enc         BLOB    NOT NULL,          -- SR17
    weight_enc             BLOB    NOT NULL,          -- SR17
    contact_id             TEXT    NOT NULL UNIQUE,   -- FR17, SR20
    privacy_notice_version TEXT    NOT NULL,          -- PR2
    privacy_consent_time   TEXT    NOT NULL,          -- PR2
    failed_login_count     INTEGER NOT NULL DEFAULT 0,  -- SR7
    locked_until           TEXT                         -- SR7
);

CREATE TABLE IF NOT EXISTS sessions (               -- SR3-SR6
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    last_seen  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (                -- SR9
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    device_id   TEXT    NOT NULL UNIQUE,
    token_hash  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS readings (               -- FR6, FR7
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type         TEXT    NOT NULL,
    value_enc    BLOB    NOT NULL,                  -- SR17
    recorded_at  TEXT    NOT NULL,                  -- NFR5
    UNIQUE (user_id, type, recorded_at)             -- NFR4
);

CREATE TABLE IF NOT EXISTS alerts (                 -- FR14-FR16
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    content_enc  BLOB    NOT NULL,                  -- SR17
    created_at   TEXT    NOT NULL                   -- NFR5
);

CREATE TABLE IF NOT EXISTS invitations (            -- FR19-FR24
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    wearer_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    contact_user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status           TEXT    NOT NULL,              -- pending / accepted (PR3)
    share_heart_rate INTEGER NOT NULL DEFAULT 0,    -- PR4
    share_steps      INTEGER NOT NULL DEFAULT 0,    -- PR4
    share_sleep      INTEGER NOT NULL DEFAULT 0,    -- PR4
    share_alerts     INTEGER NOT NULL DEFAULT 0,    -- PR4
    created_at       TEXT    NOT NULL,
    UNIQUE (wearer_id, contact_user_id)
);

CREATE TABLE IF NOT EXISTS audit_log (              -- SR21, SR22
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    user_id     TEXT,
    created_at  TEXT NOT NULL
);
